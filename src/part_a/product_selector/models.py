"""Data models for the product selector module (A-0).

All models use @dataclass with to_dict() for JSON serialization,
matching the established Part A pattern.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date


@dataclass
class SalesRankingEntry:
    """A single sales ranking observation from one platform."""

    product_name: str
    brand: str
    platform: str  # naver | danawa | coupang
    rank: int
    review_count: int = 0
    rating: float = 0.0
    price: int = 0
    product_code: str = ""

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "brand": self.brand,
            "platform": self.platform,
            "rank": self.rank,
            "review_count": self.review_count,
            "rating": self.rating,
            "price": self.price,
            "product_code": self.product_code,
        }


@dataclass
class SearchInterest:
    """Naver DataLab search volume for a product."""

    product_name: str
    volume_30d: float  # Relative 0-100
    volume_90d: float
    trend_direction: str = "stable"  # rising | stable | declining

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "volume_30d": self.volume_30d,
            "volume_90d": self.volume_90d,
            "trend_direction": self.trend_direction,
        }


@dataclass
class SentimentData:
    """Community sentiment aggregation for a product."""

    product_name: str
    total_posts: int
    negative_posts: int
    positive_posts: int

    @property
    def complaint_rate(self) -> float:
        if self.total_posts <= 0:
            return 0.0
        return self.negative_posts / self.total_posts

    @property
    def satisfaction_rate(self) -> float:
        if self.total_posts <= 0:
            return 0.0
        return self.positive_posts / self.total_posts

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "total_posts": self.total_posts,
            "negative_posts": self.negative_posts,
            "positive_posts": self.positive_posts,
            "complaint_rate": round(self.complaint_rate, 3),
            "satisfaction_rate": round(self.satisfaction_rate, 3),
        }


@dataclass
class PricePosition:
    """Price tier classification for a product."""

    product_name: str
    current_price: int
    avg_price_90d: int
    price_tier: str  # premium | mid | budget
    price_normalized: float = 0.0  # 0.0 (cheapest) to 1.0 (most expensive)

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "current_price": self.current_price,
            "avg_price_90d": self.avg_price_90d,
            "price_tier": self.price_tier,
            "price_normalized": round(self.price_normalized, 3),
        }


@dataclass
class ResaleQuickCheck:
    """Quick resale ratio check from Danggeun listings."""

    product_name: str
    avg_used_price: int
    avg_new_price: int
    sample_count: int

    @property
    def resale_ratio(self) -> float:
        if self.avg_new_price <= 0:
            return 0.0
        return self.avg_used_price / self.avg_new_price

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "avg_used_price": self.avg_used_price,
            "avg_new_price": self.avg_new_price,
            "sample_count": self.sample_count,
            "resale_ratio": round(self.resale_ratio, 3),
        }


@dataclass
class CandidateProduct:
    """A candidate product with all collected data before scoring."""

    name: str
    brand: str
    category: str
    product_code: str = ""
    release_date: date | None = None
    rankings: list[SalesRankingEntry] = field(default_factory=list)
    search_interest: SearchInterest | None = None
    sentiment: SentimentData | None = None
    price_position: PricePosition | None = None
    resale_check: ResaleQuickCheck | None = None
    in_stock: bool = True
    presence_score: int = 0  # Count of platforms (0-3)
    avg_rank: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "product_code": self.product_code,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "presence_score": self.presence_score,
            "avg_rank": round(self.avg_rank, 1),
            "in_stock": self.in_stock,
            "search_interest": self.search_interest.to_dict() if self.search_interest else None,
            "sentiment": self.sentiment.to_dict() if self.sentiment else None,
            "price_position": self.price_position.to_dict() if self.price_position else None,
            "resale_check": self.resale_check.to_dict() if self.resale_check else None,
        }


@dataclass
class ProductScores:
    """Normalized scores (0.0-1.0) for a candidate product."""

    product_name: str
    sales_presence: float = 0.0
    search_interest: float = 0.0
    sentiment: float = 0.0
    price_position: float = 0.0
    resale_retention: float = 0.0
    price_normalized: float = 0.0  # For value slot formula

    @property
    def weighted_total(self) -> float:
        """Overall weighted score (for debugging/logging)."""
        return (
            self.sales_presence * 0.20
            + self.search_interest * 0.25
            + self.sentiment * 0.25
            + self.price_position * 0.15
            + self.resale_retention * 0.15
        )

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "sales_presence": round(self.sales_presence, 3),
            "search_interest": round(self.search_interest, 3),
            "sentiment": round(self.sentiment, 3),
            "price_position": round(self.price_position, 3),
            "resale_retention": round(self.resale_retention, 3),
            "weighted_total": round(self.weighted_total, 3),
        }


@dataclass
class SlotAssignment:
    """A selected product assigned to a slot."""

    slot: str  # stability | balance | value
    candidate: CandidateProduct
    scores: ProductScores
    selection_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "slot": self.slot,
            "name": self.candidate.name,
            "brand": self.candidate.brand,
            "price_tier": (
                self.candidate.price_position.price_tier
                if self.candidate.price_position
                else "unknown"
            ),
            "selection_reasons": self.selection_reasons,
            "scores": self.scores.to_dict(),
        }


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    check_name: str  # brand_diversity | price_spread | data_sufficiency | recency | availability
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass
class SelectionResult:
    """The complete output of the product selection pipeline."""

    category: str
    selection_date: date
    data_sources: dict
    candidate_pool_size: int
    selected_products: list[SlotAssignment]
    validation: list[ValidationResult]

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "selection_date": self.selection_date.isoformat(),
            "data_sources": self.data_sources,
            "candidate_pool_size": self.candidate_pool_size,
            "selected_products": [sp.to_dict() for sp in self.selected_products],
            "validation": {
                v.check_name: f"{'PASS' if v.passed else 'FAIL'} — {v.detail}"
                for v in self.validation
            },
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)
