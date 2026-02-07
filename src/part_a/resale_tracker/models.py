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

    retention_pct = resale_price / original_price at each interval.
    """

    product_name: str
    original_price: int
    retention_6mo: float | None = None   # percentage (0-100)
    retention_12mo: float | None = None
    retention_18mo: float | None = None
    retention_24mo: float | None = None
    sample_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "original_price": self.original_price,
            "resale_curve": {
                "6mo": self.retention_6mo,
                "12mo": self.retention_12mo,
                "18mo": self.retention_18mo,
                "24mo": self.retention_24mo,
            },
            "sample_counts": self.sample_counts,
        }
