"""
Data models for template engine.
Schema matches api-contract.json from Part A.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class TCOData:
    """Core TCO metrics for a product."""
    purchase_price_avg: int  # KRW
    purchase_price_min: int  # KRW
    resale_value_24mo: int  # KRW
    expected_repair_cost: int  # KRW
    real_cost_3yr: int  # KRW = purchase + repair - resale
    as_turnaround_days: float  # avg days
    monthly_maintenance_minutes: int  # min/month


@dataclass
class PriceHistoryEntry:
    """Daily price tracking entry."""
    date: str  # YYYY-MM-DD
    price: int
    source: str  # danawa | coupang | naver
    is_sale: bool


@dataclass
class ResaleCurve:
    """Price retention percentages at different time points."""
    mo_6: float  # 6-month retention %
    mo_12: float  # 12-month retention %
    mo_18: float  # 18-month retention %
    mo_24: float  # 24-month retention %

    def to_dict(self) -> dict:
        return {
            "6mo": self.mo_6,
            "12mo": self.mo_12,
            "18mo": self.mo_18,
            "24mo": self.mo_24,
        }


@dataclass
class FailureType:
    """Repair failure category statistics."""
    type: str  # sensor, motor, software, battery, etc.
    count: int
    avg_cost: int  # KRW
    probability: float  # 0-1


@dataclass
class RepairStats:
    """Aggregated repair statistics for a product."""
    total_reports: int
    failure_types: list[FailureType] = field(default_factory=list)


@dataclass
class MaintenanceTask:
    """Regular maintenance task definition."""
    task: str
    frequency_per_month: float
    minutes_per_task: int


@dataclass
class Product:
    """Complete product data with TCO metrics."""
    product_id: str
    name: str
    brand: str
    release_date: str  # YYYY-MM-DD
    tco: TCOData
    price_history: list[PriceHistoryEntry] = field(default_factory=list)
    resale_curve: Optional[ResaleCurve] = None
    repair_stats: Optional[RepairStats] = None
    maintenance_tasks: list[MaintenanceTask] = field(default_factory=list)

    # Content generation fields (added by Part B)
    cta_link: str = ""
    highlight: str = ""  # 추천 포인트
    verdict: str = "recommend"  # recommend | caution
    recommendation_reason: str = ""
    caution_reason: str = ""


@dataclass
class SituationPick:
    """Situation-based product recommendation for Section 0."""
    situation: str  # e.g., "가성비 중시"
    product_name: str
    reason: str


@dataclass
class HomeType:
    """Home type recommendation for Section 2."""
    type: str  # e.g., "소형 원룸"
    recommendation: str


@dataclass
class FAQ:
    """FAQ entry for Section 6."""
    question: str
    answer: str


@dataclass
class PriceVolatility:
    """Price volatility info for Section 5."""
    min_diff: str  # formatted price difference
    max_diff: str
    status: str  # e.g., "평균보다 저렴한 시기"
    updated_date: str


@dataclass
class CredibilityStats:
    """Data counts for Section 1 credibility claim."""
    total_review_count: int
    price_data_count: int
    resale_data_count: int
    repair_data_count: int
    as_review_count: int
    maintenance_data_count: int


@dataclass
class BlogPostData:
    """Complete data structure for blog post generation."""
    # Meta
    title: str
    category: str  # e.g., "로봇청소기"
    generated_at: str  # ISO datetime

    # Products
    products: list[Product]
    top_products: list[Product]  # Top 3 for quick pick

    # Section-specific data
    situation_picks: list[SituationPick]
    home_types: list[HomeType]
    faqs: list[FAQ]

    # Stats
    credibility: CredibilityStats
    price_volatility: Optional[PriceVolatility] = None
    price_updated_date: str = ""

    def to_template_context(self) -> dict:
        """Convert to Jinja2 template context dictionary."""
        return {
            "title": self.title,
            "category": self.category,
            "generated_at": self.generated_at,
            "products": [self._product_to_dict(p) for p in self.products],
            "top_products": [self._product_to_dict(p) for p in self.top_products],
            "situation_picks": [
                {"situation": sp.situation, "product_name": sp.product_name, "reason": sp.reason}
                for sp in self.situation_picks
            ],
            "home_types": [
                {"type": ht.type, "recommendation": ht.recommendation}
                for ht in self.home_types
            ],
            "faqs": [
                {"question": f.question, "answer": f.answer}
                for f in self.faqs
            ],
            "total_review_count": self.credibility.total_review_count,
            "price_data_count": self.credibility.price_data_count,
            "resale_data_count": self.credibility.resale_data_count,
            "repair_data_count": self.credibility.repair_data_count,
            "as_review_count": self.credibility.as_review_count,
            "maintenance_data_count": self.credibility.maintenance_data_count,
            "price_volatility": {
                "min_diff": self.price_volatility.min_diff,
                "max_diff": self.price_volatility.max_diff,
                "status": self.price_volatility.status,
                "updated_date": self.price_volatility.updated_date,
            } if self.price_volatility else None,
            "price_updated_date": self.price_updated_date,
        }

    def _product_to_dict(self, product: Product) -> dict:
        """Convert Product to dictionary for template."""
        return {
            "product_id": product.product_id,
            "name": product.name,
            "brand": product.brand,
            "release_date": product.release_date,
            "tco": {
                "purchase_price_avg": product.tco.purchase_price_avg,
                "purchase_price_min": product.tco.purchase_price_min,
                "resale_value_24mo": product.tco.resale_value_24mo,
                "expected_repair_cost": product.tco.expected_repair_cost,
                "real_cost_3yr": product.tco.real_cost_3yr,
                "as_turnaround_days": product.tco.as_turnaround_days,
                "monthly_maintenance_minutes": product.tco.monthly_maintenance_minutes,
            },
            "resale_curve": product.resale_curve.to_dict() if product.resale_curve else {},
            "cta_link": product.cta_link,
            "highlight": product.highlight,
            "verdict": product.verdict,
            "recommendation_reason": product.recommendation_reason,
            "caution_reason": product.caution_reason,
        }
