"""Quick resale ratio check from Danggeun Market for product selection.

A lightweight version of the full resale_tracker — samples recent
listing prices to compute avg_used_price / avg_new_price ratio.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..common.config import Config
from ..common.http_client import HTTPClient
from .models import CandidateProduct, ResaleQuickCheck

logger = logging.getLogger(__name__)


class ResaleQuickChecker:
    """Quick resale ratio check from Danggeun Market.

    Usage:
        with ResaleQuickChecker() as checker:
            result = checker.check_resale("로보락 S8 Pro", current_new_price=1490000)
    """

    SEARCH_URL = "https://www.daangn.com/search"

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = HTTPClient(self.config)

    def check_resale(
        self,
        product_name: str,
        current_new_price: int,
        max_listings: int = 15,
    ) -> ResaleQuickCheck:
        """Get quick resale ratio for a product.

        Args:
            product_name: Product name to search on Danggeun.
            current_new_price: Current new retail price (KRW).
            max_listings: Maximum listings to sample.

        Returns:
            ResaleQuickCheck with avg_used_price and resale_ratio.
        """
        url = f"{self.config.danggeun_base_url}/search/{quote(product_name)}"
        cache_key = f"danggeun_resale_quick_{quote(product_name)}"

        try:
            resp = self._client.get(url, cache_key=cache_key)
            soup = BeautifulSoup(resp.text, "lxml")
            prices = self._parse_listings(soup, max_listings)
        except Exception:
            logger.warning(
                "Failed to fetch Danggeun listings for %s", product_name, exc_info=True
            )
            prices = []

        if prices:
            avg_used = sum(prices) // len(prices)
        else:
            avg_used = 0

        result = ResaleQuickCheck(
            product_name=product_name,
            avg_used_price=avg_used,
            avg_new_price=current_new_price,
            sample_count=len(prices),
        )

        logger.info(
            "Resale check for %s: avg_used=%s, new=%s, ratio=%.3f (%d samples)",
            product_name,
            f"{avg_used:,}",
            f"{current_new_price:,}",
            result.resale_ratio,
            len(prices),
        )
        return result

    def check_resale_batch(
        self, candidates: list[CandidateProduct]
    ) -> list[ResaleQuickCheck]:
        """Check resale for all candidates.

        Uses the best price from rankings as current_new_price.

        Args:
            candidates: CandidateProduct list with rankings containing prices.

        Returns:
            List of ResaleQuickCheck, one per candidate.
        """
        results: list[ResaleQuickCheck] = []
        for c in candidates:
            # Get best new price from rankings
            prices = [r.price for r in c.rankings if r.price > 0]
            new_price = min(prices) if prices else 0

            if new_price <= 0:
                results.append(ResaleQuickCheck(
                    product_name=c.name,
                    avg_used_price=0,
                    avg_new_price=0,
                    sample_count=0,
                ))
                continue

            result = self.check_resale(c.name, new_price)
            results.append(result)

        return results

    @staticmethod
    def _parse_listings(soup: BeautifulSoup, max_listings: int) -> list[int]:
        """Parse Danggeun search results and extract prices.

        Returns list of price integers.
        """
        prices: list[int] = []

        # Current: article.card-top or div.article-info
        # Legacy: .search-card, .flat-card
        items = (
            soup.select("article.card-top")
            or soup.select("div.article-info")
            or soup.select(".search-card, .flat-card")
            or soup.select(".article-list article")
        )

        for item in items[:max_listings]:
            price_el = (
                item.select_one(".article-price, .card-price")
                or item.select_one(".price")
                or item.select_one("p.price")
            )
            if not price_el:
                continue

            price = _parse_price(price_el.get_text(strip=True))
            if price > 0:
                prices.append(price)

        return prices

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ResaleQuickChecker:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _parse_price(text: str) -> int:
    """Extract numeric price from Korean price text."""
    # Handle "만원" notation: "150만원" -> 1500000
    man_match = re.search(r"(\d+)\s*만\s*원?", text)
    if man_match:
        return int(man_match.group(1)) * 10_000

    price_part = re.split(r"[원~(]", text)[0]
    digits = re.sub(r"[^\d]", "", price_part)
    return int(digits) if digits else 0
