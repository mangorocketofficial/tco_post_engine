"""Data models for the product selector module (A-0).

All models use @dataclass with to_dict() for JSON serialization,
matching the established Part A pattern.
"""

from __future__ import annotations

import json
import re as _re
from dataclasses import dataclass, field
from datetime import date

# Manufacturer prefix → normalized name
_MANUFACTURER_PREFIXES: list[tuple[str, str]] = [
    ("LG전자", "LG"),
    ("삼성전자", "삼성"),
    ("대우전자", "대우"),
    ("위니아딤채", "위니아"),
    ("위니아", "위니아"),
]


def extract_manufacturer(product_name: str) -> str:
    """Extract manufacturer name from product name.

    Examples:
        "LG전자 LG 트롬 세탁기" → "LG"
        "삼성전자 비스포크AI콤보" → "삼성"
        "LG 트롬 오브제" → "LG"
    """
    name = product_name.strip()
    for prefix, manufacturer in _MANUFACTURER_PREFIXES:
        if name.startswith(prefix):
            return manufacturer
    # "LG " without "전자"
    if _re.match(r"^LG\b", name):
        return "LG"
    return ""


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
class KeywordMetrics:
    """Naver Search Ad keyword metrics for a product."""

    product_name: str
    monthly_search_volume: int = 0  # PC + Mobile
    monthly_pc_search: int = 0
    monthly_mobile_search: int = 0
    monthly_clicks: int = 0
    monthly_pc_clicks: int = 0
    monthly_mobile_clicks: int = 0
    avg_cpc: int = 0  # KRW
    competition: str = "low"  # high | medium | low

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "monthly_search_volume": self.monthly_search_volume,
            "monthly_clicks": self.monthly_clicks,
            "avg_cpc": self.avg_cpc,
            "competition": self.competition,
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
    keyword_metrics: KeywordMetrics | None = None
    price: int = 0  # Best known price (KRW)
    in_stock: bool = True
    naver_rank: int = 0  # Rank from Naver Shopping search

    @property
    def manufacturer(self) -> str:
        """Real manufacturer name, extracted from product name.

        Falls back to brand field if manufacturer cannot be determined.
        Use this for brand diversity checks instead of .brand (which is
        the product line name from Naver Shopping API).
        """
        mfr = extract_manufacturer(self.name)
        return mfr or self.brand

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "product_code": self.product_code,
            "price": self.price,
            "naver_rank": self.naver_rank,
            "in_stock": self.in_stock,
            "keyword_metrics": self.keyword_metrics.to_dict() if self.keyword_metrics else None,
        }


@dataclass
class ProductScores:
    """Normalized scores (0.0-1.0) based on Naver Search Ad keyword metrics.

    4 dimensions:
    - Monthly Clicks (40%): actual user engagement
    - Average CPC (30%): commercial value
    - Search Volume (20%): consumer awareness
    - Competition (10%): market validation
    """

    product_name: str
    clicks_score: float = 0.0
    cpc_score: float = 0.0
    search_volume_score: float = 0.0
    competition_score: float = 0.0

    @property
    def total_score(self) -> float:
        return (
            self.clicks_score * 0.4
            + self.cpc_score * 0.3
            + self.search_volume_score * 0.2
            + self.competition_score * 0.1
        )

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "clicks_score": round(self.clicks_score, 3),
            "cpc_score": round(self.cpc_score, 3),
            "search_volume_score": round(self.search_volume_score, 3),
            "competition_score": round(self.competition_score, 3),
            "total_score": round(self.total_score, 3),
        }


@dataclass
class SelectedProduct:
    """A product selected for the TCO comparison (ranked by score)."""

    rank: int  # 1, 2, 3
    candidate: CandidateProduct
    scores: ProductScores
    selection_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "name": self.candidate.name,
            "brand": self.candidate.brand,
            "price": self.candidate.price,
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
    selected_products: list[SelectedProduct]
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


# ---------------------------------------------------------------------------
# A-0.1: Blog recommendation models
# ---------------------------------------------------------------------------


@dataclass
class BlogSearchResult:
    """A single blog search result from SerpAPI."""

    title: str
    snippet: str
    link: str
    source: str  # "naver" | "google"
    rank: int  # Position within search results

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "snippet": self.snippet,
            "link": self.link,
            "source": self.source,
            "rank": self.rank,
        }


@dataclass
class ProductMention:
    """A product mentioned across blog search results, with frequency count."""

    product_name: str
    normalized_name: str
    mention_count: int
    sources: list[str] = field(default_factory=list)  # Blog URLs

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "normalized_name": self.normalized_name,
            "mention_count": self.mention_count,
            "sources": self.sources,
        }


@dataclass
class RecommendationResult:
    """Output of the A-0.1 blog recommendation pipeline."""

    keyword: str
    search_query: str
    total_blogs_searched: int
    total_products_extracted: int
    top_products: list[ProductMention]
    search_date: str

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "search_query": self.search_query,
            "total_blogs_searched": self.total_blogs_searched,
            "total_products_extracted": self.total_products_extracted,
            "top_products": [p.to_dict() for p in self.top_products],
            "search_date": self.search_date,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Final merged selection models (A-0 + A-0.1)
# ---------------------------------------------------------------------------


@dataclass
class FinalProduct:
    """A product in the final merged Top 3 selection."""

    rank: int  # 1, 2, 3
    name: str
    brand: str
    price: int
    source: str  # "a0" | "a0.1" | "both"
    selection_reasons: list[str] = field(default_factory=list)

    # A-0 data (if available)
    a0_rank: int | None = None
    a0_scores: ProductScores | None = None

    # A-0.1 data (if available)
    recommendation_mention_count: int | None = None
    recommendation_normalized_name: str = ""

    # Match info
    match_method: str = "none"  # "model_code" | "substring" | "none"

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "name": self.name,
            "brand": self.brand,
            "price": self.price,
            "source": self.source,
            "selection_reasons": self.selection_reasons,
            "a0_rank": self.a0_rank,
            "a0_scores": self.a0_scores.to_dict() if self.a0_scores else None,
            "recommendation_mention_count": self.recommendation_mention_count,
            "recommendation_normalized_name": self.recommendation_normalized_name,
            "match_method": self.match_method,
        }


@dataclass
class FinalSelectionResult:
    """The complete output of the final merged selection pipeline."""

    category: str
    selection_date: date
    merge_case: str  # "default" | "overlap_1" | "overlap_2"
    a0_result: SelectionResult
    a0_1_result: RecommendationResult
    final_products: list[FinalProduct]
    match_details: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "selection_date": self.selection_date.isoformat(),
            "merge_case": self.merge_case,
            "final_products": [p.to_dict() for p in self.final_products],
            "a0_summary": {
                "candidate_pool_size": self.a0_result.candidate_pool_size,
                "top_3": [sp.to_dict() for sp in self.a0_result.selected_products],
            },
            "a0_1_summary": {
                "total_blogs_searched": self.a0_1_result.total_blogs_searched,
                "top_products": [p.to_dict() for p in self.a0_1_result.top_products],
            },
            "match_details": self.match_details,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)
