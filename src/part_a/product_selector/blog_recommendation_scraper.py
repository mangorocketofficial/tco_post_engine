"""Blog recommendation scraper (A-0.1).

- Naver: Naver Blog Search API (openapi.naver.com)
- Google: SerpAPI

Searches for "가성비 {keyword}" and returns structured blog results
for product name extraction.
"""

from __future__ import annotations

import logging
import os
import time

import requests

from .models import BlogSearchResult

logger = logging.getLogger(__name__)

# Naver Blog Search API: max 100 per request, start 1-1000
_NAVER_BLOG_API = "https://openapi.naver.com/v1/search/blog.json"
_NAVER_MAX_DISPLAY = 100
_NAVER_MAX_START = 1000

# SerpAPI: 10 results per page
_SERPAPI_PER_PAGE = 10


class BlogRecommendationScraper:
    """Fetch blog search results from Naver (API) and Google (SerpAPI)."""

    def __init__(
        self,
        *,
        serpapi_key: str | None = None,
        naver_client_id: str | None = None,
        naver_client_secret: str | None = None,
    ):
        self._serpapi_key = serpapi_key or os.getenv("SERPAPI_KEY", "")
        self._naver_id = naver_client_id or os.getenv("NAVER_CLIENT_ID", "")
        self._naver_secret = naver_client_secret or os.getenv("NAVER_CLIENT_SECRET", "")

        if not self._serpapi_key:
            logger.warning("SERPAPI_KEY not set — Google blog search disabled")
        if not self._naver_id or not self._naver_secret:
            logger.warning("NAVER_CLIENT_ID/SECRET not set — Naver blog search disabled")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_all(
        self,
        keyword: str,
        *,
        naver_count: int = 50,
        google_count: int = 50,
    ) -> list[BlogSearchResult]:
        """Search both Naver and Google, return combined results.

        Query: ``"가성비 {keyword}"``.
        """
        query = f"가성비 {keyword}"
        logger.info("Blog search query: '%s' (naver=%d, google=%d)", query, naver_count, google_count)

        results: list[BlogSearchResult] = []
        results.extend(self.search_naver(query, num_results=naver_count))
        results.extend(self.search_google(query, num_results=google_count))

        logger.info("Total blog results collected: %d", len(results))
        return results

    def search_naver(self, query: str, *, num_results: int = 50) -> list[BlogSearchResult]:
        """Search Naver Blog API and return blog results."""
        if not self._naver_id or not self._naver_secret:
            return []

        results: list[BlogSearchResult] = []
        start = 1

        while len(results) < num_results and start <= _NAVER_MAX_START:
            display = min(_NAVER_MAX_DISPLAY, num_results - len(results))
            try:
                items = self._fetch_naver_page(query, start=start, display=display)
                if not items:
                    break
                for i, item in enumerate(items):
                    results.append(BlogSearchResult(
                        title=self._strip_html(item.get("title", "")),
                        snippet=self._strip_html(item.get("description", "")),
                        link=item.get("link", ""),
                        source="naver",
                        rank=start + i,
                    ))
                start += len(items)
            except Exception:
                logger.exception("Naver Blog API failed at start=%d for '%s'", start, query)
                break

            if len(items) < display:
                break  # No more results

            time.sleep(0.5)

        logger.info("Naver Blog API: collected %d results for '%s'", len(results), query)
        return results[:num_results]

    def search_google(self, query: str, *, num_results: int = 50) -> list[BlogSearchResult]:
        """Search Google via SerpAPI and return blog results."""
        if not self._serpapi_key:
            return []

        results: list[BlogSearchResult] = []
        pages_needed = (num_results + _SERPAPI_PER_PAGE - 1) // _SERPAPI_PER_PAGE

        for page in range(pages_needed):
            if len(results) >= num_results:
                break

            start = page * _SERPAPI_PER_PAGE
            try:
                items = self._fetch_google_page(query, start=start)
                if not items:
                    break
                for i, item in enumerate(items):
                    if len(results) >= num_results:
                        break
                    results.append(BlogSearchResult(
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        link=item.get("link", ""),
                        source="google",
                        rank=start + i + 1,
                    ))
            except Exception:
                logger.exception("SerpAPI google page %d failed for '%s'", page, query)
                break

            if page < pages_needed - 1:
                time.sleep(1.0)

        logger.info("SerpAPI google: collected %d results for '%s'", len(results), query)
        return results[:num_results]

    # ------------------------------------------------------------------
    # Internal — Naver Blog Search API
    # ------------------------------------------------------------------

    def _fetch_naver_page(self, query: str, *, start: int, display: int) -> list[dict]:
        """Single request to Naver Blog Search API."""
        headers = {
            "X-Naver-Client-Id": self._naver_id,
            "X-Naver-Client-Secret": self._naver_secret,
        }
        params = {
            "query": query,
            "display": display,
            "start": start,
            "sort": "sim",  # relevance
        }

        resp = requests.get(_NAVER_BLOG_API, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])

    # ------------------------------------------------------------------
    # Internal — Google (SerpAPI)
    # ------------------------------------------------------------------

    def _fetch_google_page(self, query: str, *, start: int) -> list[dict]:
        """Single request to SerpAPI Google search."""
        from serpapi import GoogleSearch

        params = {
            "api_key": self._serpapi_key,
            "engine": "google",
            "q": query,
            "num": _SERPAPI_PER_PAGE,
            "hl": "ko",
            "gl": "kr",
            "start": start,
        }

        search = GoogleSearch(params)
        data = search.get_dict()
        return data.get("organic_results") or []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags from Naver API response."""
        import re
        return re.sub(r"<[^>]+>", "", text)
