"""Data models for post performance metrics and stats tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class MetricPeriod(str, Enum):
    """Time period for aggregated metrics."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class CTAClickMetrics:
    """CTA click tracking per section."""
    section_3_clicks: int = 0  # Quick Pick
    section_4_clicks: int = 0  # Deep Dive
    section_5_clicks: int = 0  # Action Trigger
    total_clicks: int = 0

    @property
    def click_distribution(self) -> dict[str, float]:
        """Click distribution across sections as percentages."""
        if self.total_clicks == 0:
            return {"section_3": 0, "section_4": 0, "section_5": 0}
        return {
            "section_3": self.section_3_clicks / self.total_clicks,
            "section_4": self.section_4_clicks / self.total_clicks,
            "section_5": self.section_5_clicks / self.total_clicks,
        }


@dataclass
class PostMetrics:
    """Performance metrics for a single blog post."""
    post_id: str
    title: str
    category: str
    publish_date: str  # ISO date
    url: str = ""
    platform: str = ""  # naver, tistory

    # Core metrics
    page_views: int = 0
    unique_visitors: int = 0
    bounce_rate: float = 0.0  # 0-1
    avg_time_on_page: float = 0.0  # seconds
    scroll_depth_avg: float = 0.0  # 0-1

    # CTA performance
    cta_clicks: CTAClickMetrics = field(default_factory=CTAClickMetrics)
    conversion_rate: float = 0.0  # 0-1

    # Revenue
    affiliate_revenue: int = 0  # KRW
    estimated_earnings: int = 0  # KRW

    # Metadata
    product_count: int = 0
    data_sources_count: int = 0
    recorded_at: str = ""  # ISO datetime

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "post_id": self.post_id,
            "title": self.title,
            "category": self.category,
            "publish_date": self.publish_date,
            "url": self.url,
            "platform": self.platform,
            "page_views": self.page_views,
            "unique_visitors": self.unique_visitors,
            "bounce_rate": self.bounce_rate,
            "avg_time_on_page": self.avg_time_on_page,
            "scroll_depth_avg": self.scroll_depth_avg,
            "cta_clicks": {
                "section_3_clicks": self.cta_clicks.section_3_clicks,
                "section_4_clicks": self.cta_clicks.section_4_clicks,
                "section_5_clicks": self.cta_clicks.section_5_clicks,
                "total_clicks": self.cta_clicks.total_clicks,
            },
            "conversion_rate": self.conversion_rate,
            "affiliate_revenue": self.affiliate_revenue,
            "estimated_earnings": self.estimated_earnings,
            "product_count": self.product_count,
            "data_sources_count": self.data_sources_count,
            "recorded_at": self.recorded_at or datetime.now().isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> PostMetrics:
        """Deserialize from dictionary."""
        cta_data = data.get("cta_clicks", {})
        return cls(
            post_id=data.get("post_id", ""),
            title=data.get("title", ""),
            category=data.get("category", ""),
            publish_date=data.get("publish_date", ""),
            url=data.get("url", ""),
            platform=data.get("platform", ""),
            page_views=data.get("page_views", 0),
            unique_visitors=data.get("unique_visitors", 0),
            bounce_rate=data.get("bounce_rate", 0.0),
            avg_time_on_page=data.get("avg_time_on_page", 0.0),
            scroll_depth_avg=data.get("scroll_depth_avg", 0.0),
            cta_clicks=CTAClickMetrics(
                section_3_clicks=cta_data.get("section_3_clicks", 0),
                section_4_clicks=cta_data.get("section_4_clicks", 0),
                section_5_clicks=cta_data.get("section_5_clicks", 0),
                total_clicks=cta_data.get("total_clicks", 0),
            ),
            conversion_rate=data.get("conversion_rate", 0.0),
            affiliate_revenue=data.get("affiliate_revenue", 0),
            estimated_earnings=data.get("estimated_earnings", 0),
            product_count=data.get("product_count", 0),
            data_sources_count=data.get("data_sources_count", 0),
            recorded_at=data.get("recorded_at", ""),
        )


@dataclass
class SectionPerformance:
    """Per-section success metrics (from dev_agent.md B4-2)."""
    section_0_bounce_rate: float = 0.0  # Target: < 40%
    section_2_scroll_depth: float = 0.0  # Target: > 60%
    section_3_cta_click_rate: float = 0.0  # Higher = better
    section_4_time_on_section: float = 0.0  # Target: > 30s
    section_6_exit_rate: float = 0.0  # Lower = better


@dataclass
class DashboardPayload:
    """Payload format for pushing to mangorocket-stats dashboard."""
    post_metrics: list[PostMetrics] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    last_updated: str = ""

    def to_dict(self) -> dict:
        """Serialize for API transmission."""
        return {
            "posts": [m.to_dict() for m in self.post_metrics],
            "summary": self.summary,
            "last_updated": self.last_updated or datetime.now().isoformat(),
        }
