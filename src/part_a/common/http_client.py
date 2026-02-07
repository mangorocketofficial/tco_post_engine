"""HTTP client with rate limiting, proxy rotation, retry, and raw HTML caching."""

from __future__ import annotations

import hashlib
import itertools
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from fake_useragent import UserAgent

from .config import Config
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class HTTPClient:
    """HTTP client wrapping requests with scraping best practices.

    Features:
    - Rate limiting (token bucket)
    - Proxy rotation (round-robin)
    - Automatic retries with exponential backoff
    - Random User-Agent rotation
    - Raw HTML caching for audit trail
    """

    MAX_RETRIES = 3
    BACKOFF_BASE = 2.0

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._rate_limiter = RateLimiter(self.config.rate_limit_rpm)
        self._session = requests.Session()
        self._ua = UserAgent(fallback="Mozilla/5.0")

        # Proxy rotation
        self._proxy_cycle = (
            itertools.cycle(self.config.proxy_list)
            if self.config.proxy_list
            else None
        )

        # Ensure cache dir exists
        self.config.raw_html_cache_abs_dir.mkdir(parents=True, exist_ok=True)

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cache_key: str | None = None,
    ) -> requests.Response:
        """Send a GET request with rate limiting, retries, and caching.

        Args:
            url: Target URL.
            params: Query parameters.
            headers: Extra headers (merged with defaults).
            cache_key: Optional key for raw HTML caching. If provided,
                       the response body is saved to disk.

        Returns:
            requests.Response object.

        Raises:
            requests.RequestException: After all retries exhausted.
        """
        merged_headers = {"User-Agent": self._ua.random}
        if headers:
            merged_headers.update(headers)

        proxies = None
        if self._proxy_cycle:
            proxy = next(self._proxy_cycle)
            proxies = {"http": proxy, "https": proxy}

        last_exc: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            self._rate_limiter.wait()
            try:
                resp = self._session.get(
                    url,
                    params=params,
                    headers=merged_headers,
                    proxies=proxies,
                    timeout=self.config.request_timeout,
                )
                resp.raise_for_status()

                if cache_key:
                    self._cache_response(cache_key, resp.text)

                return resp

            except requests.RequestException as exc:
                last_exc = exc

                # Don't retry on 4xx client errors (except 429 rate limit)
                # — these are permanent failures, retrying won't help
                if (
                    isinstance(exc, requests.HTTPError)
                    and exc.response is not None
                    and 400 <= exc.response.status_code < 500
                    and exc.response.status_code != 429
                ):
                    logger.warning("Request failed (4xx, no retry): %s", exc)
                    raise

                wait_time = self.BACKOFF_BASE ** attempt
                logger.warning(
                    "Request failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt + 1,
                    self.MAX_RETRIES,
                    exc,
                    wait_time,
                )
                time.sleep(wait_time)

        raise last_exc  # type: ignore[misc]

    def _cache_response(self, cache_key: str, html: str) -> Path:
        """Save raw HTML to cache directory for audit.

        File naming: {cache_key}_{date}_{hash}.html
        """
        date_str = datetime.now().strftime("%Y%m%d")
        content_hash = hashlib.md5(html.encode()).hexdigest()[:8]
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in cache_key)
        filename = f"{safe_key}_{date_str}_{content_hash}.html"
        path = self.config.raw_html_cache_abs_dir / filename
        path.write_text(html, encoding="utf-8")
        logger.debug("Cached HTML: %s", path)
        return path

    def close(self) -> None:
        """Close the underlying session."""
        self._session.close()

    def __enter__(self) -> HTTPClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
