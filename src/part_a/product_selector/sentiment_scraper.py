"""Community sentiment scraper for product selection.

Counts negative and positive posts across Korean community platforms
(Ppomppu, Clien, Naver Cafe) to compute complaint_rate and satisfaction_rate.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..common.config import Config
from ..common.http_client import HTTPClient
from .models import SentimentData

logger = logging.getLogger(__name__)


class SentimentScraper:
    """Community sentiment scraper for product selection.

    Searches community platforms for posts mentioning a product with
    negative or positive keywords, then counts results.

    Usage:
        with SentimentScraper() as scraper:
            sentiment = scraper.get_sentiment(
                "로보락 S8 Pro",
                negative_keywords=["고장", "AS", "수리"],
                positive_keywords=["추천", "만족", "최고"],
            )
    """

    SOURCES = {
        "ppomppu": {
            "search_url": "https://www.ppomppu.co.kr/search_bbs.php",
            "param_key": "keyword",
        },
        "clien": {
            "search_url": "https://www.clien.net/service/search",
            "param_key": "q",
        },
        "naver_cafe": {
            "search_url": "https://search.naver.com/search.naver",
            "param_key": "query",
            "extra_params": {"where": "article"},
        },
    }

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = HTTPClient(self.config)

    def get_sentiment(
        self,
        product_name: str,
        negative_keywords: list[str],
        positive_keywords: list[str],
    ) -> SentimentData:
        """Collect sentiment data for a single product.

        Args:
            product_name: Product name to search.
            negative_keywords: Keywords indicating negative sentiment.
            positive_keywords: Keywords indicating positive sentiment.

        Returns:
            SentimentData with post counts.
        """
        negative_count = 0
        positive_count = 0
        total_count = 0
        short_name = self._shorten_name(product_name)

        for source_name, source_config in self.SOURCES.items():
            # Count negative posts
            for kw in negative_keywords:
                query = f"{short_name} {kw}"
                count = self._search_count(source_name, source_config, query)
                negative_count += count
                total_count += count

            # Count positive posts
            for kw in positive_keywords:
                query = f"{short_name} {kw}"
                count = self._search_count(source_name, source_config, query)
                positive_count += count
                total_count += count

        return SentimentData(
            product_name=product_name,
            total_posts=total_count,
            negative_posts=negative_count,
            positive_posts=positive_count,
        )

    @staticmethod
    def _shorten_name(name: str) -> str:
        """Shorten a long product name to a concise search query.

        Naver API returns verbose titles like:
        "LG 식기세척기12인용 오브제컬렉션 엘지식기세척기 빌트인 베이지(25년형)"

        This extracts the first 4 meaningful tokens to keep search URLs short.
        """
        # Remove parenthetical suffixes like (25년형), [무료설치]
        cleaned = re.sub(r"[\(\[（].+?[\)\]）]", "", name).strip()
        tokens = cleaned.split()
        # Take first 4 tokens (usually brand + model)
        short = " ".join(tokens[:4])
        return short if short else name

    def get_sentiment_batch(
        self,
        product_names: list[str],
        negative_keywords: list[str],
        positive_keywords: list[str],
    ) -> list[SentimentData]:
        """Collect sentiment for multiple products.

        Args:
            product_names: Product names to search.
            negative_keywords: Keywords indicating negative sentiment.
            positive_keywords: Keywords indicating positive sentiment.

        Returns:
            List of SentimentData, one per product.
        """
        results: list[SentimentData] = []
        for name in product_names:
            sentiment = self.get_sentiment(name, negative_keywords, positive_keywords)
            results.append(sentiment)
            logger.info(
                "Sentiment for %s: total=%d, neg=%d, pos=%d",
                name,
                sentiment.total_posts,
                sentiment.negative_posts,
                sentiment.positive_posts,
            )
        return results

    def _search_count(
        self,
        source_name: str,
        source_config: dict,
        query: str,
    ) -> int:
        """Search a single source and return post count.

        Args:
            source_name: Source identifier (ppomppu, clien, naver_cafe).
            source_config: Source URL config dict.
            query: Full search query.

        Returns:
            Number of matching posts found.
        """
        url = source_config["search_url"]
        param_key = source_config["param_key"]
        params = {param_key: query}
        params.update(source_config.get("extra_params", {}))

        cache_key = f"sentiment_{source_name}_{quote(query)}"

        try:
            resp = self._client.get(url, params=params, cache_key=cache_key)
            soup = BeautifulSoup(resp.text, "lxml")

            if source_name == "ppomppu":
                return self._parse_ppomppu_count(soup)
            elif source_name == "clien":
                return self._parse_clien_count(soup)
            elif source_name == "naver_cafe":
                return self._parse_naver_cafe_count(soup)
            return 0
        except Exception:
            logger.debug(
                "Failed to search %s for '%s'", source_name, query, exc_info=True
            )
            return 0

    @staticmethod
    def _parse_ppomppu_count(soup: BeautifulSoup) -> int:
        """Parse Ppomppu search results and count items."""
        # Current: tr.common-list0 or tr.common-list1
        # Legacy: .search_result_list li
        items = (
            soup.select("tr.common-list0, tr.common-list1")
            or soup.select(".search_result_list li")
            or soup.select(".board_list tr")
        )
        return len(items)

    @staticmethod
    def _parse_clien_count(soup: BeautifulSoup) -> int:
        """Parse Clien search results and count items."""
        # Current: div.list_item
        # Legacy: .content_list .list_item
        items = (
            soup.select("div.list_item")
            or soup.select(".content_list .list_item")
        )
        return len(items)

    @staticmethod
    def _parse_naver_cafe_count(soup: BeautifulSoup) -> int:
        """Parse Naver Cafe search results and count items."""
        # Try to extract count from result summary
        count_el = soup.select_one(".title_num, .total_count")
        if count_el:
            digits = re.sub(r"[^\d]", "", count_el.get_text())
            if digits:
                return min(int(digits), 100)  # Cap at 100 to avoid skew

        # Fallback: count individual result items
        items = (
            soup.select(".article_item, .total_area li")
            or soup.select(".lst_total li")
        )
        return len(items)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SentimentScraper:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
