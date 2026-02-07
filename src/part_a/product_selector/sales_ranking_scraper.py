"""Sales ranking scrapers for Naver Shopping, Danawa, and Coupang.

Collects the top-selling products from each platform to identify
the candidate pool for product selection.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..common.config import Config
from ..common.http_client import HTTPClient
from .models import SalesRankingEntry

logger = logging.getLogger(__name__)


class NaverShoppingRankingScraper:
    """Scraper for Naver Shopping best/popular product rankings.

    Usage:
        with NaverShoppingRankingScraper() as scraper:
            results = scraper.get_best_products("로봇청소기")
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = HTTPClient(self.config)

    def get_best_products(
        self, keyword: str, max_results: int = 20
    ) -> list[SalesRankingEntry]:
        """Fetch Naver Shopping best/popular products for a keyword.

        Args:
            keyword: Category search term (e.g., "로봇청소기").
            max_results: Maximum rankings to retrieve.

        Returns:
            List of SalesRankingEntry with platform="naver".
        """
        url = f"{self.config.naver_shopping_base_url}/search/all"
        params = {
            "query": keyword,
            "sort": "rel",  # relevance (popularity-weighted)
        }
        cache_key = f"naver_shopping_best_{quote(keyword)}"

        resp = self._client.get(url, params=params, cache_key=cache_key)
        soup = BeautifulSoup(resp.text, "lxml")
        return self._parse_search_results(soup, max_results)

    def _parse_search_results(
        self, soup: BeautifulSoup, max_results: int
    ) -> list[SalesRankingEntry]:
        """Parse Naver Shopping search result page."""
        results: list[SalesRankingEntry] = []

        # Current: div.product_item or li.basicList_item
        # Legacy: div.goods_item
        items = (
            soup.select("div.product_item")
            or soup.select("li.basicList_item")
            or soup.select("div.goods_item")
        )

        for rank, item in enumerate(items[:max_results], start=1):
            entry = self._parse_product_item(item, rank)
            if entry:
                results.append(entry)

        logger.info("Naver Shopping: found %d ranked products", len(results))
        return results

    def _parse_product_item(
        self, item: BeautifulSoup, rank: int
    ) -> SalesRankingEntry | None:
        """Parse a single Naver Shopping product card."""
        try:
            # Product name
            name_el = (
                item.select_one(".product_title, .basicList_title")
                or item.select_one("a.basicList_link__JLQJf")
                or item.select_one(".tit")
            )
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                return None

            # Brand
            brand_el = (
                item.select_one(".product_mall, .basicList_mall")
                or item.select_one(".mall_title")
            )
            brand = brand_el.get_text(strip=True) if brand_el else ""

            # Price
            price_el = (
                item.select_one(".product_price strong, .basicList_price")
                or item.select_one(".price .num")
            )
            price_text = price_el.get_text(strip=True) if price_el else "0"
            price = _parse_price(price_text)

            # Review count
            review_el = (
                item.select_one(".product_etc .etc_count")
                or item.select_one(".basicList_etc .etc_count")
                or item.select_one(".review_count")
            )
            review_text = review_el.get_text(strip=True) if review_el else "0"
            review_count = _parse_count(review_text)

            # Rating
            rating_el = item.select_one(".product_grade, .basicList_grade")
            rating_text = rating_el.get_text(strip=True) if rating_el else "0"
            rating = _parse_rating(rating_text)

            return SalesRankingEntry(
                product_name=name,
                brand=brand,
                platform="naver",
                rank=rank,
                review_count=review_count,
                rating=rating,
                price=price,
            )
        except Exception:
            logger.debug("Failed to parse Naver Shopping item at rank %d", rank, exc_info=True)
            return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> NaverShoppingRankingScraper:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class DanawaRankingScraper:
    """Scraper for Danawa popular product ranking.

    Usage:
        with DanawaRankingScraper() as scraper:
            results = scraper.get_popular_products("10204001")
    """

    POPULAR_URL = "https://prod.danawa.com/list/"

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = HTTPClient(self.config)

    def get_popular_products(
        self, category_code: str, max_results: int = 20
    ) -> list[SalesRankingEntry]:
        """Fetch Danawa popular products for a category code.

        Args:
            category_code: Danawa category code (e.g., "10204001").
            max_results: Maximum rankings.

        Returns:
            List of SalesRankingEntry with platform="danawa".
        """
        params = {
            "cate": category_code,
            "15main_11_02": "",
            "sort": "saleCnt",  # sort by sales
        }
        cache_key = f"danawa_popular_{category_code}"

        resp = self._client.get(self.POPULAR_URL, params=params, cache_key=cache_key)
        soup = BeautifulSoup(resp.text, "lxml")
        return self._parse_ranking_page(soup, max_results)

    def _parse_ranking_page(
        self, soup: BeautifulSoup, max_results: int
    ) -> list[SalesRankingEntry]:
        """Parse Danawa popular ranking page."""
        results: list[SalesRankingEntry] = []

        # Current: li.goods-list__item with id starting with productItem
        # Legacy: .product_list .prod_item
        items = (
            soup.select("li.goods-list__item[id^='productItem']")
            or soup.select(".product_list .prod_item")
            or soup.select(".main_prodlist .prod_item")
        )

        for rank, item in enumerate(items[:max_results], start=1):
            entry = self._parse_ranking_item(item, rank)
            if entry:
                results.append(entry)

        logger.info("Danawa: found %d ranked products", len(results))
        return results

    def _parse_ranking_item(
        self, item: BeautifulSoup, rank: int
    ) -> SalesRankingEntry | None:
        """Parse a single Danawa ranking item."""
        try:
            # Product code
            raw_id = item.get("id", "")
            product_code = raw_id.replace("productItem-", "").replace("productItem", "").strip()

            # Name
            name_el = (
                item.select_one("span.goods-list__title")
                or item.select_one(".prod_name a, .prod_name p")
            )
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                return None

            # Brand
            brand_el = item.select_one(".maker, .brand")
            brand = brand_el.get_text(strip=True) if brand_el else ""

            # Price
            price_el = (
                item.select_one("div.goods-list__price")
                or item.select_one(".box__price-wrap .text__price em")
                or item.select_one(".price_sect .price_wrap .price")
            )
            price_text = price_el.get_text(strip=True) if price_el else "0"
            price = _parse_price(price_text)

            # Review count
            review_el = (
                item.select_one(".goods-list__review-count")
                or item.select_one(".cnt_opinion")
            )
            review_text = review_el.get_text(strip=True) if review_el else "0"
            review_count = _parse_count(review_text)

            return SalesRankingEntry(
                product_name=name,
                brand=brand,
                platform="danawa",
                rank=rank,
                review_count=review_count,
                price=price,
                product_code=product_code,
            )
        except Exception:
            logger.debug("Failed to parse Danawa item at rank %d", rank, exc_info=True)
            return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DanawaRankingScraper:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class CoupangRankingScraper:
    """Scraper for Coupang best seller ranking.

    Usage:
        with CoupangRankingScraper() as scraper:
            results = scraper.get_best_sellers("로봇청소기")
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = HTTPClient(self.config)

    def get_best_sellers(
        self, keyword: str, max_results: int = 20
    ) -> list[SalesRankingEntry]:
        """Fetch Coupang best sellers for a keyword.

        Args:
            keyword: Search term.
            max_results: Maximum rankings.

        Returns:
            List of SalesRankingEntry with platform="coupang".
        """
        url = f"{self.config.coupang_base_url}/np/search"
        params = {
            "q": keyword,
            "sorter": "salesCount",  # sort by sales
        }
        cache_key = f"coupang_best_{quote(keyword)}"

        resp = self._client.get(url, params=params, cache_key=cache_key)
        soup = BeautifulSoup(resp.text, "lxml")
        return self._parse_search_results(soup, max_results)

    def _parse_search_results(
        self, soup: BeautifulSoup, max_results: int
    ) -> list[SalesRankingEntry]:
        """Parse Coupang search result page."""
        results: list[SalesRankingEntry] = []

        # Current: li.search-product
        # Legacy: li.baby-product, ul#productList > li
        items = (
            soup.select("li.search-product")
            or soup.select("li.baby-product")
            or soup.select("ul#productList > li")
        )

        for rank, item in enumerate(items[:max_results], start=1):
            entry = self._parse_product_item(item, rank)
            if entry:
                results.append(entry)

        logger.info("Coupang: found %d ranked products", len(results))
        return results

    def _parse_product_item(
        self, item: BeautifulSoup, rank: int
    ) -> SalesRankingEntry | None:
        """Parse a single Coupang product listing."""
        try:
            # Name
            name_el = (
                item.select_one(".name, .descriptions-inner .name")
                or item.select_one("div.name")
                or item.select_one("a.search-product-link")
            )
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                return None

            # Brand — Coupang often doesn't show brand separately
            brand = ""
            brand_el = item.select_one(".brand, .product-brand")
            if brand_el:
                brand = brand_el.get_text(strip=True)

            # Price
            price_el = (
                item.select_one(".price-value, .price em")
                or item.select_one("strong.price-value")
                or item.select_one(".base-price")
            )
            price_text = price_el.get_text(strip=True) if price_el else "0"
            price = _parse_price(price_text)

            # Review count
            review_el = (
                item.select_one(".rating-total-count, .count")
                or item.select_one(".review-count")
            )
            review_text = review_el.get_text(strip=True) if review_el else "0"
            review_count = _parse_count(review_text)

            # Rating
            rating_el = item.select_one(".rating, .star-rating .rating")
            rating_text = rating_el.get_text(strip=True) if rating_el else "0"
            rating = _parse_rating(rating_text)

            # Product code from data attribute or link
            product_code = ""
            product_id = item.get("id", "")
            if product_id:
                product_code = re.sub(r"[^\d]", "", product_id)
            if not product_code:
                link_el = item.select_one("a[href*='/products/']")
                if link_el:
                    href = link_el.get("href", "")
                    match = re.search(r"/products/(\d+)", href)
                    if match:
                        product_code = match.group(1)

            return SalesRankingEntry(
                product_name=name,
                brand=brand,
                platform="coupang",
                rank=rank,
                review_count=review_count,
                rating=rating,
                price=price,
                product_code=product_code,
            )
        except Exception:
            logger.debug("Failed to parse Coupang item at rank %d", rank, exc_info=True)
            return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CoupangRankingScraper:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


# === Shared parsing helpers ===


def _parse_price(text: str) -> int:
    """Extract numeric price from Korean price text.

    Handles: '1,490,000원', '614,740', '369,000원~'.
    """
    price_part = re.split(r"[원~(]", text)[0]
    digits = re.sub(r"[^\d]", "", price_part)
    return int(digits) if digits else 0


def _parse_count(text: str) -> int:
    """Extract numeric count from text like '리뷰 2,847', '(1,234)', '상품평 567건'."""
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def _parse_rating(text: str) -> float:
    """Extract rating from text like '4.8', '별점 4.5점'."""
    match = re.search(r"(\d+\.?\d*)", text)
    return float(match.group(1)) if match else 0.0
