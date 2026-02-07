"""Danggeun Market (당근마켓) completed sale transaction scraper.

Danggeun Market is Korea's largest local secondhand marketplace.
This scraper collects completed (sold) listings to track resale values.

Key challenges:
- Danggeun is a JS-heavy SPA requiring Playwright for full rendering
- Must filter for completed sales only (sold-out status)
- Variant matching: need to handle different bundle configurations
  (e.g., "로보락 Q Revo S 풀세트" vs "로보락 Q Revo S 본체만")

For MVP, we use the search API/web endpoint with requests first,
falling back to Playwright for JS-rendered content.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from statistics import mean
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..common.config import Config
from ..common.http_client import HTTPClient
from ..database.connection import get_connection
from ..database.models import ResaleTransaction
from .models import ResaleRecord, ResaleCurve

logger = logging.getLogger(__name__)


class DanggeunScraper:
    """Scraper for Danggeun Market completed sales.

    Usage:
        scraper = DanggeunScraper()
        records = scraper.search_sold_items("로보락 Q Revo S")
        curve = scraper.calculate_retention_curve(records, original_price=1500000)
    """

    SEARCH_URL = "https://www.daangn.com/search"

    # Keywords indicating a listing is sold
    SOLD_INDICATORS = ["거래완료", "판매완료", "sold", "예약중"]

    # Condition keywords for classification
    CONDITION_MAP = {
        "미개봉": "new",
        "새상품": "new",
        "거의새것": "like_new",
        "거의 새것": "like_new",
        "S급": "like_new",
        "A급": "used",
        "중고": "used",
        "사용감": "worn",
        "하자": "worn",
    }

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = HTTPClient(self.config)

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

        params = {"query": keyword}
        resp = self._client.get(self.SEARCH_URL, params=params, cache_key=cache_key)
        soup = BeautifulSoup(resp.text, "lxml")

        records: list[ResaleRecord] = []

        # Danggeun search results — try multiple selector patterns
        # as the site structure may vary
        listing_items = soup.select(
            "article[data-gtm], "
            ".cards-wrap article, "
            ".feed-listing-content article, "
            ".search-result-item"
        )

        for item in listing_items:
            if len(records) >= max_results:
                break
            try:
                record = self._parse_listing(item, keyword)
                if record:
                    records.append(record)
            except Exception:
                logger.debug("Failed to parse listing item", exc_info=True)
                continue

        logger.info(
            "Found %d sold listings for '%s'", len(records), keyword
        )
        return records

    def _parse_listing(
        self, item: BeautifulSoup, keyword: str
    ) -> ResaleRecord | None:
        """Parse a single listing item. Returns None if not a completed sale."""
        # Check sold status
        status_el = item.select_one(
            ".badge, .status, .article-status, [class*=sold], [class*=complete]"
        )
        item_text = item.get_text()

        is_sold = False
        if status_el:
            status_text = status_el.get_text(strip=True)
            is_sold = any(ind in status_text for ind in self.SOLD_INDICATORS)

        if not is_sold:
            # Also check full item text for sold indicators
            is_sold = any(ind in item_text for ind in self.SOLD_INDICATORS)

        if not is_sold:
            return None

        # Extract title
        title_el = item.select_one(
            ".article-title, .title, h2, h3, [class*=title]"
        )
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None

        # Extract price
        price_el = item.select_one(
            ".article-price, .price, [class*=price]"
        )
        price_text = price_el.get_text(strip=True) if price_el else "0"
        sale_price = self._parse_price(price_text)

        if sale_price <= 0:
            return None

        # Extract date
        date_el = item.select_one(
            ".article-time, time, .date, [class*=time]"
        )
        listing_date = self._parse_relative_date(
            date_el.get_text(strip=True) if date_el else ""
        )

        # Classify condition
        condition = self._classify_condition(title + " " + item_text)

        # Extract listing ID
        link_el = item.select_one("a[href]")
        listing_id = ""
        if link_el:
            href = link_el.get("href", "")
            id_match = re.search(r"/(\d+)", str(href))
            if id_match:
                listing_id = id_match.group(1)

        return ResaleRecord(
            product_name=title,
            platform="danggeun",
            sale_price=sale_price,
            listing_date=listing_date,
            condition=condition,
            product_id=listing_id,
        )

    def calculate_retention_curve(
        self,
        records: list[ResaleRecord],
        original_price: int,
        release_date: date | None = None,
    ) -> ResaleCurve:
        """Calculate price retention curve from resale records.

        Groups transactions by age (months since release) and computes
        retention percentage at 6, 12, 18, 24 month intervals.

        Args:
            records: Resale transaction records.
            original_price: Original retail price (KRW).
            release_date: Product release date. If None, uses
                          months_since_release from records.

        Returns:
            ResaleCurve with retention percentages.
        """
        if original_price <= 0:
            raise ValueError("original_price must be positive")

        product_name = records[0].product_name if records else "unknown"

        # Calculate months_since_release if release_date is provided
        if release_date:
            for record in records:
                if record.listing_date:
                    delta = record.listing_date - release_date
                    record.months_since_release = delta.days / 30.44

        # Group by age buckets: 0-9mo → 6mo, 9-15mo → 12mo, etc.
        buckets: dict[str, list[int]] = {
            "6mo": [],
            "12mo": [],
            "18mo": [],
            "24mo": [],
        }

        for record in records:
            months = record.months_since_release
            if months is None:
                continue

            if months <= 9:
                buckets["6mo"].append(record.sale_price)
            elif months <= 15:
                buckets["12mo"].append(record.sale_price)
            elif months <= 21:
                buckets["18mo"].append(record.sale_price)
            elif months <= 30:
                buckets["24mo"].append(record.sale_price)

        def calc_retention(prices: list[int]) -> float | None:
            if not prices:
                return None
            avg = mean(prices)
            return round((avg / original_price) * 100, 1)

        curve = ResaleCurve(
            product_name=product_name,
            original_price=original_price,
            retention_6mo=calc_retention(buckets["6mo"]),
            retention_12mo=calc_retention(buckets["12mo"]),
            retention_18mo=calc_retention(buckets["18mo"]),
            retention_24mo=calc_retention(buckets["24mo"]),
            sample_counts={k: len(v) for k, v in buckets.items()},
        )

        logger.info(
            "Retention curve for %s: 6mo=%s%% 12mo=%s%% 18mo=%s%% 24mo=%s%%",
            product_name,
            curve.retention_6mo,
            curve.retention_12mo,
            curve.retention_18mo,
            curve.retention_24mo,
        )
        return curve

    def save_records_to_db(self, records: list[ResaleRecord]) -> int:
        """Save resale records to the database.

        Args:
            records: List of ResaleRecord to save.

        Returns:
            Number of records inserted.
        """
        conn = get_connection(self.config)
        inserted = 0
        try:
            for record in records:
                product_id = self._ensure_product(conn, record)
                conn.execute(
                    """
                    INSERT INTO resale_transactions
                        (product_id, platform, sale_price, months_since_release,
                         condition, listing_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_id,
                        record.platform,
                        record.sale_price,
                        record.months_since_release,
                        record.condition,
                        record.listing_date.isoformat() if record.listing_date else None,
                    ),
                )
                inserted += 1

            conn.commit()
            logger.info("Inserted %d resale records", inserted)
        finally:
            conn.close()

        return inserted

    def _ensure_product(self, conn, record: ResaleRecord) -> int:
        """Get or create a product row, return its ID."""
        row = conn.execute(
            "SELECT id FROM products WHERE name = ?",
            (record.product_name,),
        ).fetchone()

        if row:
            return row["id"]

        cursor = conn.execute(
            "INSERT INTO products (name, brand, category) VALUES (?, ?, ?)",
            (record.product_name, "", ""),
        )
        return cursor.lastrowid  # type: ignore[return-value]

    @staticmethod
    def _parse_price(text: str) -> int:
        """Extract numeric price from Korean price text."""
        # Handle "만원" notation (e.g., "150만원" = 1,500,000)
        man_match = re.search(r"(\d+)\s*만\s*(\d*)\s*원?", text)
        if man_match:
            man = int(man_match.group(1))
            rest = int(man_match.group(2)) if man_match.group(2) else 0
            return man * 10000 + rest

        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else 0

    @staticmethod
    def _parse_relative_date(text: str) -> date | None:
        """Parse Korean relative time (e.g., '3일 전', '2주 전', '1달 전')."""
        today = date.today()

        if not text:
            return None

        # "N분 전", "N시간 전" → today
        if re.search(r"\d+\s*(분|시간)\s*전", text):
            return today

        # "N일 전"
        day_match = re.search(r"(\d+)\s*일\s*전", text)
        if day_match:
            return today - timedelta(days=int(day_match.group(1)))

        # "N주 전"
        week_match = re.search(r"(\d+)\s*주\s*전", text)
        if week_match:
            return today - timedelta(weeks=int(week_match.group(1)))

        # "N달 전" / "N개월 전"
        month_match = re.search(r"(\d+)\s*(달|개월)\s*전", text)
        if month_match:
            months = int(month_match.group(1))
            return today - timedelta(days=months * 30)

        # Try absolute date formats
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%m/%d"):
            try:
                parsed = datetime.strptime(text.strip(), fmt).date()
                if parsed.year == 1900:
                    parsed = parsed.replace(year=today.year)
                return parsed
            except ValueError:
                continue

        return None

    def _classify_condition(self, text: str) -> str:
        """Classify item condition from listing text."""
        for keyword, condition in self.CONDITION_MAP.items():
            if keyword in text:
                return condition
        return "used"

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DanggeunScraper:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
