"""
Data models for template engine.
Schema matches api-contract.json from Part A.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class ConsumableItem:
    """A single consumable cost item."""
    name: str
    unit_price: int
    changes_per_year: float
    annual_cost: int
    compatible_available: bool = False
    compatible_price: int | None = None


@dataclass
class TCOData:
    """Core TCO metrics for a product."""
    purchase_price: int  # KRW — from A0 Naver Shopping lprice
    annual_consumable_cost: int  # KRW
    tco_years: int = 3  # TCO calculation period (tech=3, pet=2)
    consumable_cost_total: int = 0  # KRW = annual × tco_years
    real_cost_total: int = 0  # KRW = purchase + consumable_cost_total
    consumable_breakdown: list[ConsumableItem] = field(default_factory=list)


@dataclass
class Product:
    """Complete product data with TCO metrics."""
    product_id: str
    name: str
    brand: str
    release_date: str  # YYYY-MM-DD
    tco: TCOData

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
    consumable_data_count: int


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
    # Multi-category support
    tco_years: int = 3  # TCO period (tech=3, pet=2)
    domain: str = "tech"  # "tech" | "pet"

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
            "consumable_data_count": self.credibility.consumable_data_count,
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
        return {
            "product_id": product.product_id,
            "name": product.name,
            "brand": product.brand,
            "release_date": product.release_date,
            "tco": {
                "purchase_price": product.tco.purchase_price,
                "annual_consumable_cost": product.tco.annual_consumable_cost,
                "tco_years": product.tco.tco_years,
                "consumable_cost_total": product.tco.consumable_cost_total,
                "real_cost_total": product.tco.real_cost_total,
                "consumable_breakdown": [
                    {
                        "name": c.name,
                        "unit_price": c.unit_price,
                        "changes_per_year": c.changes_per_year,
                        "annual_cost": c.annual_cost,
                        "compatible_available": c.compatible_available,
                        "compatible_price": c.compatible_price,
                    }
                    for c in product.tco.consumable_breakdown
                ],
            },
            "cta_link": product.cta_link,
            "highlight": product.highlight,
            "slot_label": product.slot_label,
            "verdict": product.verdict,
            "recommendation_reason": product.recommendation_reason,
            "caution_reason": product.caution_reason,
        }
