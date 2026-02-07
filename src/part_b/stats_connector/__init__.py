# Stats Connector — Push metrics to mangorocket-stats dashboard
"""
Stats Connector module for tracking and pushing blog post performance metrics.

Provides local JSON-based storage and HTTP client for integration
with the mangorocket-stats Next.js dashboard.
"""

from .connector import StatsConnector
from .models import (
    CTAClickMetrics,
    DashboardPayload,
    MetricPeriod,
    PostMetrics,
    SectionPerformance,
)

__all__ = [
    "StatsConnector",
    "CTAClickMetrics",
    "DashboardPayload",
    "MetricPeriod",
    "PostMetrics",
    "SectionPerformance",
]
