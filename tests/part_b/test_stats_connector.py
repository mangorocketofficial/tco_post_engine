"""Tests for the stats_connector module.

Tests cover:
- Post metrics model serialization/deserialization
- CTA click metrics and distribution
- Metrics recording, retrieval, and deletion
- Category filtering
- Summary statistics calculation
- Section performance evaluation
- Dashboard payload building
- Local JSON persistence (save/load)
- Dashboard push (mocked HTTP)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.part_b.stats_connector.models import (
    CTAClickMetrics,
    DashboardPayload,
    MetricPeriod,
    PostMetrics,
    SectionPerformance,
)
from src.part_b.stats_connector.connector import StatsConnector


# === Fixtures ===


@pytest.fixture
def sample_metrics() -> PostMetrics:
    """Sample post metrics."""
    return PostMetrics(
        post_id="robot-vacuum-2026-01",
        title="2026년 로봇청소기 추천 TOP 3",
        category="로봇청소기",
        publish_date="2026-02-07",
        url="https://blog.naver.com/mangorocket/12345",
        platform="naver",
        page_views=1500,
        unique_visitors=1200,
        bounce_rate=0.35,
        avg_time_on_page=180.5,
        scroll_depth_avg=0.72,
        cta_clicks=CTAClickMetrics(
            section_3_clicks=45,
            section_4_clicks=30,
            section_5_clicks=25,
            total_clicks=100,
        ),
        conversion_rate=0.067,
        affiliate_revenue=125000,
        product_count=3,
        data_sources_count=372,
    )


@pytest.fixture
def sample_metrics_2() -> PostMetrics:
    """Second sample for multi-post testing."""
    return PostMetrics(
        post_id="air-purifier-2026-01",
        title="2026년 공기청정기 TCO 비교",
        category="공기청정기",
        publish_date="2026-02-10",
        page_views=800,
        bounce_rate=0.42,
        avg_time_on_page=120.0,
        cta_clicks=CTAClickMetrics(
            section_3_clicks=20,
            section_4_clicks=15,
            section_5_clicks=10,
            total_clicks=45,
        ),
        conversion_rate=0.056,
        affiliate_revenue=85000,
    )


@pytest.fixture
def connector(tmp_path) -> StatsConnector:
    """Create a StatsConnector with temp storage."""
    return StatsConnector(metrics_path=tmp_path / "test_metrics.json")


# === Test: Models ===


class TestPostMetrics:
    def test_to_dict(self, sample_metrics):
        d = sample_metrics.to_dict()
        assert d["post_id"] == "robot-vacuum-2026-01"
        assert d["page_views"] == 1500
        assert d["cta_clicks"]["total_clicks"] == 100
        assert d["conversion_rate"] == 0.067

    def test_from_dict_roundtrip(self, sample_metrics):
        d = sample_metrics.to_dict()
        restored = PostMetrics.from_dict(d)
        assert restored.post_id == sample_metrics.post_id
        assert restored.page_views == sample_metrics.page_views
        assert restored.cta_clicks.total_clicks == sample_metrics.cta_clicks.total_clicks
        assert restored.conversion_rate == sample_metrics.conversion_rate

    def test_from_dict_defaults(self):
        m = PostMetrics.from_dict({"post_id": "test"})
        assert m.post_id == "test"
        assert m.page_views == 0
        assert m.bounce_rate == 0.0

    def test_recorded_at_auto_set(self, sample_metrics):
        d = sample_metrics.to_dict()
        assert d["recorded_at"] != ""


class TestCTAClickMetrics:
    def test_click_distribution(self):
        clicks = CTAClickMetrics(
            section_3_clicks=50,
            section_4_clicks=30,
            section_5_clicks=20,
            total_clicks=100,
        )
        dist = clicks.click_distribution
        assert dist["section_3"] == 0.5
        assert dist["section_4"] == 0.3
        assert dist["section_5"] == 0.2

    def test_click_distribution_zero_total(self):
        clicks = CTAClickMetrics()
        dist = clicks.click_distribution
        assert all(v == 0 for v in dist.values())


class TestDashboardPayload:
    def test_to_dict(self, sample_metrics):
        payload = DashboardPayload(
            post_metrics=[sample_metrics],
            summary={"total_posts": 1},
        )
        d = payload.to_dict()
        assert len(d["posts"]) == 1
        assert d["summary"]["total_posts"] == 1
        assert d["last_updated"] != ""


# === Test: Metrics Recording ===


class TestMetricsRecording:
    def test_record_metrics(self, connector, sample_metrics):
        connector.record_metrics(sample_metrics)
        assert connector.metric_count == 1

    def test_record_sets_recorded_at(self, connector):
        m = PostMetrics(post_id="test", title="Test", category="test", publish_date="2026-01-01")
        connector.record_metrics(m)
        stored = connector.get_metrics("test")
        assert stored.recorded_at != ""

    def test_get_metrics(self, connector, sample_metrics):
        connector.record_metrics(sample_metrics)
        result = connector.get_metrics("robot-vacuum-2026-01")
        assert result is not None
        assert result.title == "2026년 로봇청소기 추천 TOP 3"

    def test_get_nonexistent(self, connector):
        assert connector.get_metrics("nonexistent") is None

    def test_update_existing_metrics(self, connector, sample_metrics):
        connector.record_metrics(sample_metrics)
        sample_metrics.page_views = 2000
        connector.record_metrics(sample_metrics)

        assert connector.metric_count == 1  # No duplicate
        result = connector.get_metrics("robot-vacuum-2026-01")
        assert result.page_views == 2000

    def test_get_all_metrics(self, connector, sample_metrics, sample_metrics_2):
        connector.record_metrics(sample_metrics)
        connector.record_metrics(sample_metrics_2)
        all_metrics = connector.get_all_metrics()
        assert len(all_metrics) == 2

    def test_get_metrics_by_category(self, connector, sample_metrics, sample_metrics_2):
        connector.record_metrics(sample_metrics)
        connector.record_metrics(sample_metrics_2)

        robot = connector.get_metrics_by_category("로봇청소기")
        assert len(robot) == 1
        assert robot[0].post_id == "robot-vacuum-2026-01"

    def test_delete_metrics(self, connector, sample_metrics):
        connector.record_metrics(sample_metrics)
        assert connector.delete_metrics("robot-vacuum-2026-01")
        assert connector.metric_count == 0

    def test_delete_nonexistent(self, connector):
        assert not connector.delete_metrics("nonexistent")


# === Test: Summary ===


class TestSummary:
    def test_empty_summary(self, connector):
        summary = connector.get_summary()
        assert summary["total_posts"] == 0
        assert summary["total_page_views"] == 0

    def test_summary_with_data(self, connector, sample_metrics, sample_metrics_2):
        connector.record_metrics(sample_metrics)
        connector.record_metrics(sample_metrics_2)
        summary = connector.get_summary()

        assert summary["total_posts"] == 2
        assert summary["total_page_views"] == 2300  # 1500 + 800
        assert summary["total_cta_clicks"] == 145  # 100 + 45
        assert summary["total_revenue"] == 210000  # 125000 + 85000
        assert 0 < summary["avg_bounce_rate"] < 1
        assert summary["avg_time_on_page"] > 0
        assert summary["avg_conversion_rate"] > 0


# === Test: Section Performance ===


class TestSectionPerformance:
    def test_evaluate_performance(self, connector, sample_metrics):
        perf = connector.evaluate_section_performance(sample_metrics)

        assert perf.section_0_bounce_rate == 0.35
        assert perf.section_2_scroll_depth == 0.72
        assert perf.section_3_cta_click_rate > 0
        assert perf.section_4_time_on_section > 0

    def test_cta_click_rate_calculation(self, connector, sample_metrics):
        perf = connector.evaluate_section_performance(sample_metrics)
        # 100 clicks / 1500 views = 0.0667
        expected = 100 / 1500
        assert abs(perf.section_3_cta_click_rate - expected) < 0.001

    def test_zero_views_performance(self, connector):
        m = PostMetrics(post_id="empty", title="Empty", category="test", publish_date="2026-01-01")
        perf = connector.evaluate_section_performance(m)
        assert perf.section_3_cta_click_rate == 0


# === Test: Persistence ===


class TestPersistence:
    def test_save_and_load(self, tmp_path, sample_metrics):
        path = tmp_path / "metrics.json"
        c1 = StatsConnector(metrics_path=path)
        c1.record_metrics(sample_metrics)

        # Load in new instance
        c2 = StatsConnector(metrics_path=path)
        assert c2.metric_count == 1
        result = c2.get_metrics("robot-vacuum-2026-01")
        assert result.page_views == 1500
        assert result.cta_clicks.total_clicks == 100

    def test_save_creates_dirs(self, tmp_path, sample_metrics):
        path = tmp_path / "nested" / "dir" / "metrics.json"
        c = StatsConnector(metrics_path=path)
        c.record_metrics(sample_metrics)
        assert path.exists()

    def test_load_nonexistent_file(self, tmp_path):
        c = StatsConnector(metrics_path=tmp_path / "nonexistent.json")
        assert c.metric_count == 0

    def test_json_format(self, tmp_path, sample_metrics):
        path = tmp_path / "metrics.json"
        c = StatsConnector(metrics_path=path)
        c.record_metrics(sample_metrics)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "metrics" in data
        assert "last_updated" in data
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["post_id"] == "robot-vacuum-2026-01"


# === Test: Dashboard Push ===


class TestDashboardPush:
    def test_build_payload(self, connector, sample_metrics):
        connector.record_metrics(sample_metrics)
        payload = connector.build_dashboard_payload()

        assert len(payload.post_metrics) == 1
        assert payload.summary["total_posts"] == 1
        assert payload.last_updated != ""

    def test_payload_serialization(self, connector, sample_metrics):
        connector.record_metrics(sample_metrics)
        payload = connector.build_dashboard_payload()
        d = payload.to_dict()

        assert isinstance(d["posts"], list)
        assert isinstance(d["summary"], dict)

    @patch("httpx.post")
    def test_push_success(self, mock_post, connector, sample_metrics):
        connector.record_metrics(sample_metrics)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = connector.push_to_dashboard()
        assert result is True
        mock_post.assert_called_once()

    @patch("httpx.post")
    def test_push_connection_error(self, mock_post, connector, sample_metrics):
        import httpx
        connector.record_metrics(sample_metrics)
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        result = connector.push_to_dashboard()
        assert result is False
