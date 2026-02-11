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


