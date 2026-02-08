"""Base class for resale platform scrapers.

Provides shared logic for condition classification, price parsing,
retention curve calculation, and database persistence. Platform-specific
scrapers (Danggeun, Bunjang) inherit and implement search_sold_items().
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from statistics import median

from ..common.config import Config
from ..common.http_client import HTTPClient
from ..database.connection import get_connection
from .models import ResaleRecord, ResaleCurve

logger = logging.getLogger(__name__)


class BaseResaleScraper(ABC):
    """Abstract base for resale platform scrapers."""

    # Condition keywords → standardized levels
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

    # Conditions excluded from retention curve (broken/parts-only items)
    EXCLUDED_CONDITIONS = {"worn"}

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = HTTPClient(self.config)

    @abstractmethod
    def search_sold_items(
        self,
        keyword: str,
        max_results: int = 30,
    ) -> list[ResaleRecord]:
        """Search for completed (sold) listings. Platform-specific."""
        ...

    def calculate_retention_curve(
        self,
        records: list[ResaleRecord],
        original_price: int,
        release_date: date | None = None,
    ) -> ResaleCurve:
        """Calculate price retention curve from resale records.

        Groups transactions by age into yearly buckets (1yr, 2yr, 3yr+)
        and computes median-based retention percentage. Excludes broken/worn
        items for more representative pricing.

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

        # Group by yearly buckets, excluding worn/broken items
        buckets: dict[str, list[int]] = {
            "1yr": [],
            "2yr": [],
            "3yr_plus": [],
        }

        for record in records:
            months = record.months_since_release
            if months is None:
                continue

            if record.condition in self.EXCLUDED_CONDITIONS:
                continue

            if months <= 18:
                buckets["1yr"].append(record.sale_price)
            elif months <= 30:
                buckets["2yr"].append(record.sale_price)
            else:
                buckets["3yr_plus"].append(record.sale_price)

        def calc_median_price(prices: list[int]) -> int | None:
            if not prices:
                return None
            return int(median(prices))

        def calc_retention(prices: list[int]) -> float | None:
            if not prices:
                return None
            med = median(prices)
            return round((med / original_price) * 100, 1)

        curve = ResaleCurve(
            product_name=product_name,
            original_price=original_price,
            retention_1yr=calc_retention(buckets["1yr"]),
            retention_2yr=calc_retention(buckets["2yr"]),
            retention_3yr_plus=calc_retention(buckets["3yr_plus"]),
            median_price_1yr=calc_median_price(buckets["1yr"]),
            median_price_2yr=calc_median_price(buckets["2yr"]),
            median_price_3yr_plus=calc_median_price(buckets["3yr_plus"]),
            sample_counts={k: len(v) for k, v in buckets.items()},
        )

        logger.info(
            "Retention curve for %s: 1yr=%s%% 2yr=%s%% 3yr+=%s%%",
            product_name,
            curve.retention_1yr,
            curve.retention_2yr,
            curve.retention_3yr_plus,
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

    def _classify_condition(self, text: str) -> str:
        """Classify item condition from listing text."""
        for keyword, condition in self.CONDITION_MAP.items():
            if keyword in text:
                return condition
        return "used"

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

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
