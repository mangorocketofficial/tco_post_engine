"""Data models for Part A storage layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Product:
    """A tracked product."""

    name: str
    brand: str
    category: str
    release_date: date | None = None
    id: int | None = None
    created_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "release_date": self.release_date.isoformat() if self.release_date else None,
        }


@dataclass
class Price:
    """A single price observation for a product."""

    product_id: int
    date: date
    price: int  # KRW
    source: str  # danawa | coupang | naver
    is_sale: bool = False
    id: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "date": self.date.isoformat(),
            "price": self.price,
            "source": self.source,
            "is_sale": self.is_sale,
        }


@dataclass
class ResaleTransaction:
    """A completed resale transaction."""

    product_id: int
    platform: str  # danggeun | bunjang
    sale_price: int  # KRW
    months_since_release: float | None = None
    condition: str = "used"  # new | like_new | used | worn
    listing_date: date | None = None
    id: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "platform": self.platform,
            "sale_price": self.sale_price,
            "months_since_release": self.months_since_release,
            "condition": self.condition,
            "listing_date": self.listing_date.isoformat() if self.listing_date else None,
        }


@dataclass
class RepairReport:
    """A repair/AS report extracted from community posts (Phase 2)."""

    product_id: int
    failure_type: str
    repair_cost: int  # KRW
    as_days: int | None = None
    sentiment: str = "neutral"  # positive | negative | neutral
    source_url: str = ""
    date: date | None = None
    id: int | None = None


@dataclass
class MaintenanceTask:
    """A maintenance task for a product (Phase 2)."""

    product_id: int
    task: str
    frequency_per_month: float
    minutes_per_task: float
    id: int | None = None

    @property
    def total_monthly_minutes(self) -> float:
        return self.frequency_per_month * self.minutes_per_task
