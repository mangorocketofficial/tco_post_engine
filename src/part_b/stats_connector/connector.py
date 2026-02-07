"""Stats Connector — Push post metrics to mangorocket-stats dashboard.

Provides local JSON-based metrics storage and an HTTP client for pushing
metrics to the mangorocket-stats Next.js dashboard.

Usage:
    connector = StatsConnector()
    connector.record_metrics(post_metrics)
    summary = connector.get_summary()
    connector.push_to_dashboard()  # When dashboard endpoint is ready
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.common.config import DATA_DIR
from src.common.logging import setup_logging

from .models import (
    CTAClickMetrics,
    DashboardPayload,
    MetricPeriod,
    PostMetrics,
    SectionPerformance,
)

logger = setup_logging(module_name="stats_connector")

# Default storage paths
METRICS_DIR = DATA_DIR / "metrics"
METRICS_FILE = METRICS_DIR / "post_metrics.json"

# Dashboard API (future integration)
DEFAULT_DASHBOARD_URL = "http://localhost:3000/api/tco-posts"


class StatsConnector:
    """Manages post performance metrics storage and dashboard integration.

    Stores metrics locally as JSON and provides methods to push
    to the mangorocket-stats dashboard when its API is available.
    """

    def __init__(
        self,
        metrics_path: Path | None = None,
        dashboard_url: str = DEFAULT_DASHBOARD_URL,
    ):
        """Initialize the stats connector.

        Args:
            metrics_path: Path to local JSON metrics file.
                          Defaults to data/metrics/post_metrics.json.
            dashboard_url: URL for the dashboard API endpoint.
        """
        self.metrics_path = metrics_path or METRICS_FILE
        self.dashboard_url = dashboard_url
        self._metrics: list[PostMetrics] = []

        # Load existing metrics if available
        if self.metrics_path.exists():
            self._load_metrics()

    @property
    def metric_count(self) -> int:
        """Number of recorded post metrics."""
        return len(self._metrics)

    # --- Metrics Recording ---

    def record_metrics(self, metrics: PostMetrics) -> None:
        """Record performance metrics for a blog post.

        Args:
            metrics: Post performance metrics to record
        """
        if not metrics.recorded_at:
            metrics.recorded_at = datetime.now().isoformat()

        # Update existing or add new
        existing_idx = next(
            (i for i, m in enumerate(self._metrics) if m.post_id == metrics.post_id),
            None,
        )

        if existing_idx is not None:
            self._metrics[existing_idx] = metrics
            logger.info("Updated metrics for post %s", metrics.post_id)
        else:
            self._metrics.append(metrics)
            logger.info("Recorded metrics for post %s", metrics.post_id)

        self._save_metrics()

    def get_metrics(self, post_id: str) -> PostMetrics | None:
        """Get metrics for a specific post.

        Args:
            post_id: The post identifier

        Returns:
            PostMetrics or None if not found
        """
        return next(
            (m for m in self._metrics if m.post_id == post_id),
            None,
        )

    def get_all_metrics(self) -> list[PostMetrics]:
        """Get all recorded post metrics."""
        return list(self._metrics)

    def get_metrics_by_category(self, category: str) -> list[PostMetrics]:
        """Get metrics filtered by product category.

        Args:
            category: Product category (e.g., "로봇청소기")

        Returns:
            List of matching PostMetrics
        """
        return [m for m in self._metrics if m.category == category]

    def delete_metrics(self, post_id: str) -> bool:
        """Delete metrics for a post. Returns True if deleted."""
        before = len(self._metrics)
        self._metrics = [m for m in self._metrics if m.post_id != post_id]
        deleted = len(self._metrics) < before
        if deleted:
            self._save_metrics()
        return deleted

    # --- Summary & Analysis ---

    def get_summary(self) -> dict:
        """Generate aggregate summary across all tracked posts.

        Returns:
            Dictionary with summary statistics
        """
        if not self._metrics:
            return {
                "total_posts": 0,
                "total_page_views": 0,
                "avg_bounce_rate": 0,
                "avg_time_on_page": 0,
                "total_cta_clicks": 0,
                "avg_conversion_rate": 0,
                "total_revenue": 0,
            }

        total_views = sum(m.page_views for m in self._metrics)
        total_cta = sum(m.cta_clicks.total_clicks for m in self._metrics)
        total_revenue = sum(m.affiliate_revenue for m in self._metrics)

        bounce_rates = [m.bounce_rate for m in self._metrics if m.bounce_rate > 0]
        avg_bounce = sum(bounce_rates) / len(bounce_rates) if bounce_rates else 0

        times = [m.avg_time_on_page for m in self._metrics if m.avg_time_on_page > 0]
        avg_time = sum(times) / len(times) if times else 0

        conv_rates = [m.conversion_rate for m in self._metrics if m.conversion_rate > 0]
        avg_conv = sum(conv_rates) / len(conv_rates) if conv_rates else 0

        return {
            "total_posts": len(self._metrics),
            "total_page_views": total_views,
            "avg_bounce_rate": round(avg_bounce, 4),
            "avg_time_on_page": round(avg_time, 1),
            "total_cta_clicks": total_cta,
            "avg_conversion_rate": round(avg_conv, 4),
            "total_revenue": total_revenue,
        }

    def evaluate_section_performance(self, metrics: PostMetrics) -> SectionPerformance:
        """Evaluate per-section performance against targets.

        Target thresholds (from dev_agent.md B4-2):
        - Section 0 (Hook): bounce_rate < 40%
        - Section 2 (Criteria): scroll_depth > 60%
        - Section 3 (Table): CTA click rate
        - Section 4 (TCO): time on section > 30s
        - Section 6 (FAQ): exit rate (lower = better)

        Args:
            metrics: Post metrics to evaluate

        Returns:
            SectionPerformance with evaluated metrics
        """
        cta_click_rate = 0.0
        if metrics.page_views > 0:
            cta_click_rate = metrics.cta_clicks.total_clicks / metrics.page_views

        return SectionPerformance(
            section_0_bounce_rate=metrics.bounce_rate,
            section_2_scroll_depth=metrics.scroll_depth_avg,
            section_3_cta_click_rate=cta_click_rate,
            section_4_time_on_section=metrics.avg_time_on_page * 0.3,  # Estimate
            section_6_exit_rate=0.0,  # Requires detailed analytics
        )

    # --- Dashboard Integration ---

    def build_dashboard_payload(self) -> DashboardPayload:
        """Build payload for pushing to mangorocket-stats dashboard.

        Returns:
            DashboardPayload ready for API transmission
        """
        return DashboardPayload(
            post_metrics=list(self._metrics),
            summary=self.get_summary(),
            last_updated=datetime.now().isoformat(),
        )

    def push_to_dashboard(self) -> bool:
        """Push metrics to the mangorocket-stats dashboard API.

        Sends a POST request with all metrics to the dashboard endpoint.
        Returns False if the dashboard is unreachable (expected during MVP).

        Returns:
            True if push succeeded, False otherwise
        """
        import httpx

        payload = self.build_dashboard_payload()

        try:
            response = httpx.post(
                self.dashboard_url,
                json=payload.to_dict(),
                timeout=10.0,
            )
            response.raise_for_status()
            logger.info("Pushed %d metrics to dashboard", len(self._metrics))
            return True
        except httpx.ConnectError:
            logger.warning(
                "Dashboard not reachable at %s (expected during MVP)",
                self.dashboard_url,
            )
            return False
        except httpx.HTTPStatusError as e:
            logger.error("Dashboard API error: %s", e.response.status_code)
            return False

    # --- Local Persistence ---

    def _save_metrics(self) -> None:
        """Save metrics to local JSON file."""
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "metrics": [m.to_dict() for m in self._metrics],
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.metrics_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_metrics(self) -> None:
        """Load metrics from local JSON file."""
        try:
            with open(self.metrics_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._metrics = [
                PostMetrics.from_dict(m)
                for m in data.get("metrics", [])
            ]
            logger.info("Loaded %d metrics from %s", len(self._metrics), self.metrics_path)
        except (json.JSONDecodeError, FileNotFoundError):
            logger.warning("Could not load metrics from %s", self.metrics_path)
            self._metrics = []
