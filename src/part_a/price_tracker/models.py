"""Data models for price tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class PriceRecord:
    """A single price observation from a shopping platform.

    Maps to the API contract: { date, price, source, is_sale }
    """

    product_name: str
    price: int  # KRW
    source: str  # danawa | coupang | naver
    date: date = field(default_factory=date.today)
    is_sale: bool = False
    product_id: str = ""  # Platform-specific product ID

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "price": self.price,
            "source": self.source,
            "is_sale": self.is_sale,
        }


@dataclass
class ProductPriceSummary:
    """Aggregated price statistics for a product."""

    product_name: str
    current_price: int
    lowest_price: int
    avg_price_30d: int | None = None
    avg_price_90d: int | None = None
    avg_price_180d: int | None = None
    price_history: list[PriceRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "current_price": self.current_price,
            "lowest_price": self.lowest_price,
            "avg_price_30d": self.avg_price_30d,
            "avg_price_90d": self.avg_price_90d,
            "avg_price_180d": self.avg_price_180d,
            "history_count": len(self.price_history),
        }
