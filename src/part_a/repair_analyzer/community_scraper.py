"""Community forum scraper for repair/AS posts.

Scrapes Korean community forums (Ppomppu, Clien, Naver Cafe) for
posts about product repairs, AS (after-service), and breakdowns.

Each community has different HTML structure, so we use separate
parsing methods per source.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..common.config import Config
from ..common.http_client import HTTPClient
from .models import CommunityPost

logger = logging.getLogger(__name__)


class CommunityScraper:
    """Scraper for Korean community forums.

    Searches for product repair/AS discussion posts across
    Ppomppu, Clien, and Naver Cafe.

    Usage:
        scraper = CommunityScraper()
        posts = scraper.search_all("로보락 S8 Pro Ultra", ["수리", "AS", "고장"])
    """

    SOURCES = {
        "ppomppu": {
            "search_url": "https://www.ppomppu.co.kr/zboard/search_res.php",
            "base_url": "https://www.ppomppu.co.kr",
        },
        "clien": {
            "search_url": "https://www.clien.net/service/search",
            "base_url": "https://www.clien.net",
        },
        "naver_cafe": {
            "search_url": "https://search.naver.com/search.naver",
            "base_url": "https://search.naver.com",
        },
    }

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = HTTPClient(self.config)

    def search_all(
        self,
        product_name: str,
        repair_keywords: list[str],
        max_per_source: int = 20,
    ) -> list[CommunityPost]:
        """Search all community sources for repair/AS posts.

        Args:
            product_name: Product name to search for.
            repair_keywords: Keywords like ["수리", "AS", "고장"].
            max_per_source: Max posts to collect per source.

        Returns:
            Combined list of CommunityPost from all sources.
        """
        all_posts: list[CommunityPost] = []

        for keyword in repair_keywords:
            query = f"{product_name} {keyword}"

            for source in self.SOURCES:
                try:
                    posts = self._search_source(source, query, max_per_source)
                    all_posts.extend(posts)
                    logger.info(
                        "Found %d posts from %s for '%s'",
                        len(posts), source, query,
                    )
                except Exception:
                    logger.warning(
                        "Failed to scrape %s for '%s'", source, query,
                        exc_info=True,
                    )
                    continue

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_posts: list[CommunityPost] = []
        for post in all_posts:
            if post.source_url and post.source_url in seen_urls:
                continue
            if post.source_url:
                seen_urls.add(post.source_url)
            unique_posts.append(post)

        logger.info(
            "Total unique posts collected: %d (from %d raw)",
            len(unique_posts), len(all_posts),
        )
        return unique_posts

    def _search_source(
        self, source: str, query: str, max_results: int
    ) -> list[CommunityPost]:
        """Search a specific community source."""
        if source == "ppomppu":
            return self._search_ppomppu(query, max_results)
        elif source == "clien":
            return self._search_clien(query, max_results)
        elif source == "naver_cafe":
            return self._search_naver_cafe(query, max_results)
        return []

    def _search_ppomppu(self, query: str, max_results: int) -> list[CommunityPost]:
        """Search Ppomppu forums."""
        source_info = self.SOURCES["ppomppu"]
        params = {
            "keyword": query,
            "search_type": "sub_memo",
            "page_num": "20",
        }
        cache_key = f"ppomppu_search_{quote(query)}"

        resp = self._client.get(
            source_info["search_url"], params=params, cache_key=cache_key
        )
        soup = BeautifulSoup(resp.text, "lxml")

        posts: list[CommunityPost] = []
        items = soup.select(
            ".common_list tr, "
            ".search_result .result_row, "
            ".board_list tr"
        )

        for item in items[:max_results]:
            try:
                post = self._parse_ppomppu_item(item, source_info["base_url"])
                if post:
                    posts.append(post)
            except Exception:
                logger.debug("Failed to parse Ppomppu item", exc_info=True)
                continue

        return posts

    def _parse_ppomppu_item(
        self, item: BeautifulSoup, base_url: str
    ) -> CommunityPost | None:
        """Parse a Ppomppu search result item."""
        title_el = item.select_one("a.title, a.baseList-title, td.title a, .title a")
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        url = href if href.startswith("http") else f"{base_url}{href}"

        # Extract body preview if available
        body_el = item.select_one(".baseList-desc, .content_preview, td.desc")
        body = body_el.get_text(strip=True) if body_el else ""

        # Extract date
        date_el = item.select_one(".baseList-time, td.date, .time, time")
        post_date = self._parse_date(date_el.get_text(strip=True) if date_el else "")

        return CommunityPost(
            title=title,
            body=body,
            source="ppomppu",
            source_url=url,
            date=post_date,
        )

    def _search_clien(self, query: str, max_results: int) -> list[CommunityPost]:
        """Search Clien forums."""
        source_info = self.SOURCES["clien"]
        params = {
            "q": query,
            "sort": "recency",
            "p": "0",
            "boardCd": "",
        }
        cache_key = f"clien_search_{quote(query)}"

        resp = self._client.get(
            source_info["search_url"], params=params, cache_key=cache_key
        )
        soup = BeautifulSoup(resp.text, "lxml")

        posts: list[CommunityPost] = []
        items = soup.select(
            ".list_item, "
            ".search_result .item, "
            ".board-list-item"
        )

        for item in items[:max_results]:
            try:
                post = self._parse_clien_item(item, source_info["base_url"])
                if post:
                    posts.append(post)
            except Exception:
                logger.debug("Failed to parse Clien item", exc_info=True)
                continue

        return posts

    def _parse_clien_item(
        self, item: BeautifulSoup, base_url: str
    ) -> CommunityPost | None:
        """Parse a Clien search result item."""
        title_el = item.select_one(
            ".subject_fixed, .list_subject a, a.title"
        )
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        url = href if href.startswith("http") else f"{base_url}{href}"

        body_el = item.select_one(".list_content, .content_desc")
        body = body_el.get_text(strip=True) if body_el else ""

        date_el = item.select_one(".timestamp, .time, time")
        post_date = self._parse_date(date_el.get_text(strip=True) if date_el else "")

        return CommunityPost(
            title=title,
            body=body,
            source="clien",
            source_url=url,
            date=post_date,
        )

    def _search_naver_cafe(self, query: str, max_results: int) -> list[CommunityPost]:
        """Search Naver Cafe via Naver search aggregation."""
        source_info = self.SOURCES["naver_cafe"]
        params = {
            "query": query,
            "where": "article",
        }
        cache_key = f"naver_cafe_search_{quote(query)}"

        resp = self._client.get(
            source_info["search_url"], params=params, cache_key=cache_key
        )
        soup = BeautifulSoup(resp.text, "lxml")

        posts: list[CommunityPost] = []
        items = soup.select(
            ".lst_total .bx, "
            ".sp_article .article_item, "
            ".search_result .item"
        )

        for item in items[:max_results]:
            try:
                post = self._parse_naver_cafe_item(item)
                if post:
                    posts.append(post)
            except Exception:
                logger.debug("Failed to parse Naver Cafe item", exc_info=True)
                continue

        return posts

    def _parse_naver_cafe_item(self, item: BeautifulSoup) -> CommunityPost | None:
        """Parse a Naver Cafe search result item."""
        title_el = item.select_one(
            ".total_tit a, .article_title a, a.api_txt_lines"
        )
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        url = title_el.get("href", "")

        body_el = item.select_one(
            ".total_dsc, .article_content, .api_txt_lines.dsc_txt"
        )
        body = body_el.get_text(strip=True) if body_el else ""

        date_el = item.select_one(".sub_time, .sub_date, .date")
        post_date = self._parse_date(date_el.get_text(strip=True) if date_el else "")

        return CommunityPost(
            title=title,
            body=body,
            source="naver_cafe",
            source_url=url,
            date=post_date,
        )

    @staticmethod
    def _parse_date(text: str) -> date | None:
        """Parse various date formats from community posts."""
        if not text:
            return None

        text = text.strip()

        # Try common formats
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%y.%m.%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

        # Try "YYYY.MM.DD HH:MM" style
        date_match = re.match(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
        if date_match:
            try:
                return date(
                    int(date_match.group(1)),
                    int(date_match.group(2)),
                    int(date_match.group(3)),
                )
            except ValueError:
                pass

        return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CommunityScraper:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
