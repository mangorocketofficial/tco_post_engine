"""Bunjang (번개장터) resale transaction scraper.

Bunjang is Korea's largest mobile-first secondhand marketplace.
This scraper uses Bunjang's public JSON API to collect listings
for resale value tracking.

API endpoint: GET https://api.bunjang.co.kr/api/1/find_v2.json
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from urllib.parse import quote

from .base_scraper import BaseResaleScraper
from .models import ResaleRecord

logger = logging.getLogger(__name__)


class BunjangScraper(BaseResaleScraper):
    """Scraper for Bunjang (번개장터) listings via JSON API.

    Usage:
        scraper = BunjangScraper()
        records = scraper.search_sold_items("로보락 Q Revo S")
        curve = scraper.calculate_retention_curve(records, original_price=1500000)
    """

    SEARCH_API_URL = "https://api.bunjang.co.kr/api/1/find_v2.json"

    # Bunjang status codes
    STATUS_SELLING = "0"
    STATUS_RESERVED = "1"
    STATUS_SOLD = "2"

    def search_sold_items(
        self,
        keyword: str,
        max_results: int = 30,
    ) -> list[ResaleRecord]:
        """Search Bunjang for listings matching keyword.

        Collects both sold items (status=2) and active listings
        as asking prices, since sold items may not always appear
        in search results.

        Args:
            keyword: Product search term (e.g., "삼성 김치플러스").
            max_results: Maximum listings to collect.

        Returns:
            List of ResaleRecord for found listings.
        """
        cache_key = f"bunjang_search_{quote(keyword)}"

        # Request more than needed to account for filtering
        request_count = max_results * 2
        params = {
            "q": keyword,
            "order": "date",
            "page": "0",
            "n": str(request_count),
        }

        resp = self._client.get(
            self.SEARCH_API_URL,
            params=params,
            cache_key=cache_key,
        )

        try:
            data = resp.json()
        except Exception:
            logger.warning("Failed to parse Bunjang API response as JSON")
            return []

        items = data.get("list", [])

        records: list[ResaleRecord] = []

        for item in items:
            if len(records) >= max_results:
                break
            try:
                record = self._parse_api_listing(item)
                if record:
                    records.append(record)
            except Exception:
                logger.debug("Failed to parse Bunjang listing", exc_info=True)
                continue

        logger.info(
            "Found %d listings for '%s' on Bunjang", len(records), keyword
        )
        return records

    def _parse_api_listing(self, item: dict) -> ResaleRecord | None:
        """Parse a single Bunjang API listing.

        Returns None if the listing should be skipped.
        """
        title = item.get("name", "")
        if not title:
            return None

        # Parse price (string in API response)
        price_raw = item.get("price", "0")
        try:
            sale_price = int(str(price_raw))
        except (ValueError, TypeError):
            sale_price = self._parse_price(str(price_raw))

        if sale_price <= 0:
            return None

        # Parse date from Unix timestamp
        listing_date = self._parse_bunjang_date(item.get("update_time"))

        # Classify condition from listing name
        condition = self._classify_condition(title)

        # Extract listing ID
        listing_id = str(item.get("pid", ""))

        return ResaleRecord(
            product_name=title,
            platform="bunjang",
            sale_price=sale_price,
            listing_date=listing_date,
            condition=condition,
            product_id=listing_id,
        )

    @staticmethod
    def _parse_bunjang_date(value) -> date | None:
        """Parse Bunjang date from Unix timestamp."""
        if value is None:
            return None

        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value).date()
            if isinstance(value, str) and value.isdigit():
                return datetime.fromtimestamp(int(value)).date()
        except (ValueError, OSError):
            pass

        return None

    def __enter__(self) -> BunjangScraper:
        return self
