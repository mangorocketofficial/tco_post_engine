"""Category configuration for product selection.

Loads category-specific settings from YAML files under config/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class CategoryConfig:
    """Category-specific configuration for the product selector."""

    name: str
    search_terms: list[str]
    negative_keywords: list[str]
    positive_keywords: list[str]
    price_range_min: int = 0
    price_range_max: int = 10_000_000
    max_product_age_months: int = 18
    min_community_posts: int = 20
    danawa_category_code: str = ""

    @classmethod
    def from_yaml(cls, path: str | Path) -> CategoryConfig:
        """Load category config from a YAML file.

        Args:
            path: Path to YAML file (absolute or relative to project root).

        Returns:
            CategoryConfig instance.
        """
        p = Path(path)
        if not p.is_absolute():
            p = _PROJECT_ROOT / p
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        price_range = data.get("price_range", {})
        return cls(
            name=data.get("name", ""),
            search_terms=data.get("search_terms", []),
            negative_keywords=data.get("negative_keywords", []),
            positive_keywords=data.get("positive_keywords", []),
            price_range_min=price_range.get("min", 0),
            price_range_max=price_range.get("max", 10_000_000),
            max_product_age_months=data.get("max_product_age_months", 18),
            min_community_posts=data.get("min_community_posts", 20),
            danawa_category_code=data.get("danawa_category_code", ""),
        )

    @classmethod
    def from_category_name(cls, category: str) -> CategoryConfig:
        """Create a generic config from a category name.

        Uses sensible defaults for keywords and thresholds.
        For fine-tuned settings, use a YAML config file instead.

        Args:
            category: Category name (e.g., "식기세척기").

        Returns:
            CategoryConfig with the given category as search term.
        """
        return cls(
            name=category,
            search_terms=[category],
            negative_keywords=["불만", "후회", "실망", "반품", "고장", "AS", "수리", "오류"],
            positive_keywords=["추천", "만족", "최고", "잘샀다", "좋아요", "강추"],
            price_range_min=0,
            price_range_max=10_000_000,
            max_product_age_months=18,
            min_community_posts=20,
            danawa_category_code="",
        )

    @classmethod
    def default_robot_vacuum(cls) -> CategoryConfig:
        """Return default config for robot vacuum category."""
        return cls(
            name="robot_vacuum",
            search_terms=["로봇청소기"],
            negative_keywords=["불만", "후회", "실망", "반품", "고장", "AS", "수리", "오류"],
            positive_keywords=["추천", "만족", "최고", "잘샀다", "좋아요", "강추"],
            price_range_min=300_000,
            price_range_max=2_000_000,
            max_product_age_months=18,
            min_community_posts=20,
            danawa_category_code="10204001",
        )
