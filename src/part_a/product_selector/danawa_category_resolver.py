"""Auto-resolve Danawa category codes from search keywords.

When a category config has no danawa_category_code, this module searches
Danawa and extracts the most relevant category code from the results page.

Usage:
    resolver = DanawaCategoryResolver()
    code = resolver.resolve("벽걸이TV")  # → "10248425"
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from ..common.config import Config
from ..common.http_client import HTTPClient

logger = logging.getLogger(__name__)


class DanawaCategoryResolver:
    """Resolves Danawa category codes by searching the Danawa website."""

    SEARCH_URL = "https://search.danawa.com/dsearch.php"

    def __init__(self, config: Config | None = None) -> None:
        self._client = HTTPClient(config or Config())

    def resolve(self, keyword: str) -> str | None:
        """Search Danawa and extract the most relevant category code.

        Fetches the search results page for *keyword*, collects all
        ``cate=`` values from links, and returns the most frequent one.

        Args:
            keyword: Search term (e.g., "벽걸이TV", "로봇청소기").

        Returns:
            Category code string (e.g., "10248425") or ``None`` on failure.
        """
        try:
            resp = self._client.get(
                self.SEARCH_URL,
                params={"query": keyword},
                cache_key=f"danawa_category_resolve_{keyword}",
            )
        except Exception:
            logger.warning(
                "Failed to fetch Danawa search page for '%s'", keyword, exc_info=True
            )
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        code = self._extract_category_code(soup)

        if code:
            logger.info(
                "Resolved Danawa category code for '%s': %s", keyword, code
            )
        else:
            logger.warning(
                "Could not resolve Danawa category code for '%s'", keyword
            )

        return code

    def _extract_category_code(self, soup: BeautifulSoup) -> str | None:
        """Extract the most frequent cate= code from all links on the page."""
        cate_codes: list[str] = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            codes = self._parse_cate_from_url(href)
            cate_codes.extend(codes)

        if not cate_codes:
            return None

        # Most frequent code = most relevant category
        counter = Counter(cate_codes)
        best_code, count = counter.most_common(1)[0]
        logger.debug(
            "Category code candidates: %s (picked '%s' with %d occurrences)",
            counter.most_common(5),
            best_code,
            count,
        )
        return best_code

    @staticmethod
    def _parse_cate_from_url(url: str) -> list[str]:
        """Extract cate= parameter values from a URL string."""
        codes: list[str] = []

        # Try standard query parameter parsing
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            for val in qs.get("cate", []):
                if val.isdigit() and len(val) >= 3:
                    codes.append(val)
        except Exception:
            pass

        # Fallback: regex for cate=DIGITS patterns (catches JS onclick etc.)
        for match in re.finditer(r"cate=(\d{3,})", url):
            code = match.group(1)
            if code not in codes:
                codes.append(code)

        return codes

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DanawaCategoryResolver:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
