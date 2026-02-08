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
    resale_value_1yr: int  # KRW — median resale within 1 year
    resale_value_2yr: int  # KRW — median resale at 1-2 years
    resale_value_3yr_plus: int  # KRW — median resale at 3+ years
    expected_repair_cost: int  # KRW
    real_cost_3yr: int  # KRW = purchase + repair - resale(2yr)
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
    """Price retention percentages at yearly intervals."""
    yr_1: float  # 1-year retention %
    yr_2: float  # 2-year retention %
    yr_3_plus: float  # 3+ year retention %

    def to_dict(self) -> dict:
        return {
            "1yr": self.yr_1,
            "2yr": self.yr_2,
            "3yr_plus": self.yr_3_plus,
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
    automated: Optional[bool] = None  # True=auto, False=manual, None=unknown


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
    slot_label: str = ""  # e.g., "안정형", "가성비형" — from LLM enrichment
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
class CategoryCriteria:
    """Category-specific criteria for Section 2 (LLM-generated)."""
    myth_busting: str  # 2-1: spec myth to bust
    real_differentiator: str  # 2-2: hidden cost factor
    decision_fork: str  # 2-3: home/lifestyle branching


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
    category_criteria: Optional[CategoryCriteria] = None  # Section 2
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
            "category_criteria": {
                "myth_busting": self.category_criteria.myth_busting,
                "real_differentiator": self.category_criteria.real_differentiator,
                "decision_fork": self.category_criteria.decision_fork,
            } if self.category_criteria else None,
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
        # Calculate automation rate from maintenance tasks
        auto_count = sum(1 for mt in product.maintenance_tasks if mt.automated is True)
        total_count = len(product.maintenance_tasks)
        automation_rate = round((auto_count / total_count) * 100) if total_count > 0 else 0

        return {
            "product_id": product.product_id,
            "name": product.name,
            "brand": product.brand,
            "release_date": product.release_date,
            "tco": {
                "purchase_price_avg": product.tco.purchase_price_avg,
                "purchase_price_min": product.tco.purchase_price_min,
                "resale_value_1yr": product.tco.resale_value_1yr,
                "resale_value_2yr": product.tco.resale_value_2yr,
                "resale_value_3yr_plus": product.tco.resale_value_3yr_plus,
                "expected_repair_cost": product.tco.expected_repair_cost,
                "real_cost_3yr": product.tco.real_cost_3yr,
                "as_turnaround_days": product.tco.as_turnaround_days,
                "monthly_maintenance_minutes": product.tco.monthly_maintenance_minutes,
            },
            "resale_curve": product.resale_curve.to_dict() if product.resale_curve else {},
            "cta_link": product.cta_link,
            "highlight": product.highlight,
            "slot_label": product.slot_label,
            "verdict": product.verdict,
            "recommendation_reason": product.recommendation_reason,
            "caution_reason": product.caution_reason,
            "automation_rate": automation_rate,
            "maintenance_tasks": [
                {
                    "task": mt.task,
                    "automated": mt.automated,
                }
                for mt in product.maintenance_tasks
            ],
        }
