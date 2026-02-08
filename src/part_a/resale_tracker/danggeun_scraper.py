"""Danggeun Market (당근마켓) completed sale transaction scraper.

Danggeun Market is Korea's largest local secondhand marketplace.
This scraper collects completed (sold) listings to track resale values.

The site uses a React/Remix SPA. Listing data is embedded in
window.__remixContext JSON within the HTML, which we extract directly.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base_scraper import BaseResaleScraper
from .models import ResaleRecord

logger = logging.getLogger(__name__)


class DanggeunScraper(BaseResaleScraper):
    """Scraper for Danggeun Market completed sales.

    Usage:
        scraper = DanggeunScraper()
        records = scraper.search_sold_items("로보락 Q Revo S")
        curve = scraper.calculate_retention_curve(records, original_price=1500000)
    """

    SEARCH_URL = "https://www.daangn.com/kr/buy-sell/"

    # Keywords indicating a listing is sold (fallback for text matching)
    SOLD_INDICATORS = ["거래완료", "판매완료", "sold"]

    def search_sold_items(
        self,
        keyword: str,
        max_results: int = 30,
    ) -> list[ResaleRecord]:
        """Search for completed (sold) listings on Danggeun Market.

        Args:
            keyword: Product search term (e.g., "로보락 Q Revo S").
            max_results: Maximum listings to collect.

        Returns:
            List of ResaleRecord for completed sales only.
        """
        cache_key = f"danggeun_search_{quote(keyword)}"

        params = {"search": keyword}
        resp = self._client.get(self.SEARCH_URL, params=params, cache_key=cache_key)

        listings = self._extract_remix_listings(resp.text)

        records: list[ResaleRecord] = []

        for item in listings:
            if len(records) >= max_results:
                break
            try:
                record = self._parse_remix_listing(item)
                if record:
                    records.append(record)
            except Exception:
                logger.debug("Failed to parse listing item", exc_info=True)
                continue

        logger.info(
            "Found %d sold listings for '%s'", len(records), keyword
        )
        return records

    def _extract_remix_listings(self, html: str) -> list[dict]:
        """Extract listing data from window.__remixContext in the HTML.

        Danggeun embeds search result data as JSON inside a <script> tag.
        We parse the HTML to find this script and extract the listings array.

        Args:
            html: Raw HTML response text.

        Returns:
            List of listing dicts from the remix context.
        """
        # Try regex extraction first (faster)
        match = re.search(
            r"window\.__remixContext\s*=\s*({.+?})\s*;?\s*</script>",
            html,
            re.DOTALL,
        )

        if not match:
            # Fallback: use BeautifulSoup to find the script tag
            soup = BeautifulSoup(html, "lxml")
            for script in soup.find_all("script"):
                text = script.string or ""
                if "window.__remixContext" in text:
                    inner = re.search(
                        r"window\.__remixContext\s*=\s*({.+})",
                        text,
                        re.DOTALL,
                    )
                    if inner:
                        match = inner
                        break

        if not match:
            logger.warning("Could not find window.__remixContext in response")
            return []

        try:
            context = json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.warning("Failed to parse __remixContext JSON")
            return []

        return self._find_listings_in_context(context)

    def _find_listings_in_context(self, context: dict) -> list[dict]:
        """Navigate the remix context structure to find listing objects.

        The structure may vary, so we search recursively for arrays
        containing objects that look like listings (have title + price).
        """
        listings: list[dict] = []

        def _search(obj):
            if isinstance(obj, list):
                # Check if this looks like a listings array
                if obj and isinstance(obj[0], dict) and "title" in obj[0]:
                    listings.extend(obj)
                    return
                for item in obj:
                    _search(item)
            elif isinstance(obj, dict):
                # Check if this dict itself is a listing
                if "title" in obj and "price" in obj:
                    listings.append(obj)
                    return
                for value in obj.values():
                    _search(value)

        _search(context)
        return listings

    def _parse_remix_listing(self, item: dict) -> ResaleRecord | None:
        """Parse a single listing from remix context JSON.

        Returns None if the listing is not a completed sale.
        """
        # Check sold status — Danggeun uses "Closed" for completed sales
        status = item.get("status", "")
        is_sold = status == "Closed"

        # Fallback: check title/content for sold indicators
        if not is_sold:
            text = item.get("title", "") + " " + item.get("content", "")
            is_sold = any(ind in text for ind in self.SOLD_INDICATORS)

        if not is_sold:
            return None

        title = item.get("title", "")
        if not title:
            return None

        # Price is a string like "15000.0" or "1200000"
        price_raw = item.get("price", "0")
        try:
            sale_price = int(float(str(price_raw)))
        except (ValueError, TypeError):
            sale_price = self._parse_price(str(price_raw))

        if sale_price <= 0:
            return None

        # Parse date — ISO format from createdAt field
        listing_date = self._parse_danggeun_date(item.get("createdAt"))

        # Classify condition from title + content
        content = item.get("content", "")
        condition = self._classify_condition(title + " " + content)

        # Extract listing ID
        listing_id = str(item.get("id", ""))

        return ResaleRecord(
            product_name=title,
            platform="danggeun",
            sale_price=sale_price,
            listing_date=listing_date,
            condition=condition,
            product_id=listing_id,
        )

    @staticmethod
    def _parse_danggeun_date(value) -> date | None:
        """Parse Danggeun date from ISO string or relative text."""
        if not value:
            return None

        if isinstance(value, str):
            # Try ISO format first (e.g., "2026-01-15T09:30:00Z")
            try:
                return datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                ).date()
            except ValueError:
                pass

            # Fallback to relative date parsing
            return BaseResaleScraper._parse_relative_date(value)

        return None

    def __enter__(self) -> DanggeunScraper:
        return self
