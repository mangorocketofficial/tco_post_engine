"""Shared Pydantic data models for TCO Post Engine.

These models define the data contracts between Part A (Data Engine)
and Part B (Content Engine). All modules import from here.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


# === Enums ===

class PriceSource(str, Enum):
    """Source platforms for price data."""
    DANAWA = "danawa"
    COUPANG = "coupang"
    NAVER = "naver"


class ResalePlatform(str, Enum):
    """Platforms for resale transaction data."""
    DANGGEUN = "danggeun"
    BUNJANG = "bunjang"


class ProductCondition(str, Enum):
    """Condition of resale product."""
    LIKE_NEW = "like_new"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class CommunitySource(str, Enum):
    """Community sources for repair/AS data."""
    PPOMPPU = "ppomppu"
    CLIEN = "clien"
    NAVER_CAFE = "naver_cafe"


class Sentiment(str, Enum):
    """Sentiment classification for community posts."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


# === Part A: Data Models ===

class Product(BaseModel):
    """Core product identity."""
    product_id: str
    name: str
    brand: str
    category: str
    release_date: date


class PriceRecord(BaseModel):
    """Single price observation from a source."""
    product_id: str
    date: date
    price: int = Field(ge=0, description="Price in KRW")
    source: PriceSource
    is_sale: bool = False


class ResaleTransaction(BaseModel):
    """Completed resale transaction."""
    product_id: str
    platform: ResalePlatform
    sale_price: int = Field(ge=0, description="Sale price in KRW")
    listing_date: date
    months_since_release: int = Field(ge=0)
    condition: ProductCondition = ProductCondition.GOOD


class RepairReport(BaseModel):
    """Extracted repair/AS data from community post."""
    product_id: str
    failure_type: str
    repair_cost: int = Field(ge=0, description="Repair cost in KRW")
    as_days: int = Field(ge=0, description="AS turnaround in days")
    sentiment: Sentiment = Sentiment.NEUTRAL
    source: CommunitySource
    source_url: str = ""
    date: date


class MaintenanceTask(BaseModel):
    """Regular maintenance task for a product."""
    product_id: str
    task: str
    frequency_per_month: float = Field(gt=0)
    minutes_per_task: float = Field(ge=0)

    @property
    def total_monthly_minutes(self) -> float:
        return self.frequency_per_month * self.minutes_per_task


class FailureTypeStat(BaseModel):
    """Aggregated statistics for a failure type."""
    type: str
    count: int
    avg_cost: int
    probability: float = Field(ge=0, le=1)


class RepairStats(BaseModel):
    """Aggregated repair statistics for a product."""
    total_reports: int
    failure_types: list[FailureTypeStat] = []


class ResaleCurve(BaseModel):
    """Price retention curve as percentage of original price."""
    mo_6: float | None = Field(default=None, alias="6mo")
    mo_12: float | None = Field(default=None, alias="12mo")
    mo_18: float | None = Field(default=None, alias="18mo")
    mo_24: float | None = Field(default=None, alias="24mo")

    model_config = {"populate_by_name": True}


# === TCO Calculation ===

class TCOSummary(BaseModel):
    """Calculated TCO metrics for a product."""
    purchase_price_avg: int = Field(description="Average purchase price (KRW)")
    purchase_price_min: int = Field(description="Minimum observed price (KRW)")
    resale_value_24mo: int = Field(description="Estimated resale value at 24 months (KRW)")
    expected_repair_cost: int = Field(description="Probability-weighted repair cost (KRW)")
    real_cost_3yr: int = Field(description="Q1 + Q3 - Q2 (KRW)")
    as_turnaround_days: float = Field(description="Average AS turnaround (days)")
    monthly_maintenance_minutes: float = Field(description="Total monthly maintenance (minutes)")


# === API Contract: Part A → Part B Export ===

class ProductTCOExport(BaseModel):
    """Complete TCO export for a single product (Part A → Part B)."""
    product_id: str
    name: str
    brand: str
    release_date: date
    tco: TCOSummary
    price_history: list[PriceRecord] = []
    resale_curve: ResaleCurve | None = None
    repair_stats: RepairStats | None = None
    maintenance_tasks: list[MaintenanceTask] = []


class TCOCategoryExport(BaseModel):
    """Full TCO export for a product category — the main data contract."""
    category: str
    generated_at: datetime
    products: list[ProductTCOExport]
