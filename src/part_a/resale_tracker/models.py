"""Data models for resale transaction tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ResaleRecord:
    """A completed resale transaction from a secondhand platform.

    Maps to API contract: { product_id, platform, sale_price, months_since_release, condition }
    """

    product_name: str
    platform: str  # danggeun | bunjang
    sale_price: int  # KRW
    listing_date: date | None = None
    months_since_release: float | None = None
    condition: str = "used"  # new | like_new | used | worn
    product_id: str = ""  # Platform-specific listing ID

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "platform": self.platform,
            "sale_price": self.sale_price,
            "listing_date": self.listing_date.isoformat() if self.listing_date else None,
            "months_since_release": self.months_since_release,
            "condition": self.condition,
        }


@dataclass
class ResaleCurve:
    """Price retention curve for a product over time.

    Buckets: 1yr (≤18mo), 2yr (18-30mo), 3yr_plus (>30mo).
    Uses median resale price for robustness against outliers.
    retention_pct = median(resale_price) / original_price at each interval.
    """

    product_name: str
    original_price: int
    retention_1yr: float | None = None   # percentage (0-100)
    retention_2yr: float | None = None
    retention_3yr_plus: float | None = None
    median_price_1yr: int | None = None  # median resale price (KRW)
    median_price_2yr: int | None = None
    median_price_3yr_plus: int | None = None
    sample_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "original_price": self.original_price,
            "resale_curve": {
                "1yr": self.retention_1yr,
                "2yr": self.retention_2yr,
                "3yr_plus": self.retention_3yr_plus,
            },
            "median_prices": {
                "1yr": self.median_price_1yr,
                "2yr": self.median_price_2yr,
                "3yr_plus": self.median_price_3yr_plus,
            },
            "sample_counts": self.sample_counts,
        }
