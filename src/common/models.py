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


class ConsumableItem(BaseModel):
    """A single consumable cost item for a product."""
    name: str
    unit_price: int = Field(ge=0, description="Unit price in KRW")
    replacement_cycle_months: int = Field(gt=0)
    changes_per_year: float = Field(gt=0)
    annual_cost: int = Field(ge=0, description="Annual cost in KRW")
    compatible_available: bool = False
    compatible_price: int | None = None


# === TCO Calculation ===

class TCOSummary(BaseModel):
    """Calculated TCO metrics for a product."""
    purchase_price: int = Field(description="Purchase price from A0 Naver Shopping lprice (KRW)")
    annual_consumable_cost: int = Field(description="Annual consumable cost (KRW)")
    tco_years: int = Field(default=3, description="TCO calculation period in years")
    consumable_cost_total: int = Field(default=0, description="Consumable cost over tco_years (KRW)")
    real_cost_total: int = Field(default=0, description="purchase + consumable_cost_total (KRW)")
    consumable_breakdown: list[ConsumableItem] = []


# === API Contract: Part A → Part B Export ===

class ProductTCOExport(BaseModel):
    """Complete TCO export for a single product (Part A → Part B)."""
    product_id: str
    name: str
    brand: str
    release_date: date
    tco: TCOSummary


class TCOCategoryExport(BaseModel):
    """Full TCO export for a product category — the main data contract."""
    category: str
    tco_years: int = 3
    generated_at: datetime
    products: list[ProductTCOExport]
