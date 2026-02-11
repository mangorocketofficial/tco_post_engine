"""End-to-end integration tests for the TCO Post Engine pipeline.

Tests the data contract, post-processing, and stats integration.
ContentWriter and Jinja2 renderer have been removed (generation now via Claude Code).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.part_b.cta_manager.manager import CTAManager
from src.part_b.cta_manager.models import AffiliateLink, AffiliatePlatform
from src.part_b.publisher.processor import PostProcessor
from src.part_b.publisher.pipeline import PublishPipeline
from src.part_b.publisher.models import SEOMetaTags
from src.part_b.stats_connector.connector import StatsConnector
from src.part_b.stats_connector.models import PostMetrics


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "sample_tco_data.json"

SAMPLE_HTML = """<h1>2026년 로봇청소기 추천 TOP 3</h1>
<p>로봇청소기 3대를 비교했습니다.</p>
<table>
<tr><td>로보락 Q Revo S</td><td>1,154,000원</td></tr>
<tr><td>삼성 비스포크 제트 AI</td><td>1,335,000원</td></tr>
<tr><td>에코백스 X2 콤보</td><td>1,710,000원</td></tr>
</table>
<p><a href="https://link.coupang.com/a/roborock">최저가 확인하기</a></p>
"""


class TestPostProcessing:
    """Test post-processing and export pipeline."""

    def test_post_processor_adds_disclosure(self):
        """Post-processor adds affiliate disclosure to content."""
        processor = PostProcessor()
        processed = processor.process(SAMPLE_HTML)
        assert "쿠팡 파트너스" in processed

    def test_html_export(self):
        """Export to HTML produces valid structure."""
        processor = PostProcessor()
        seo = SEOMetaTags(
            title="로봇청소기 TCO 비교",
            description="로봇청소기 TCO 비교",
            keywords=["로봇청소기", "TCO", "비교"],
        )
        html_result = processor.export_html(SAMPLE_HTML, seo)

        assert html_result.format.value == "html"
        assert "<!DOCTYPE html>" in html_result.content
        assert '<html lang="ko">' in html_result.content
        assert html_result.word_count > 0

    def test_markdown_export(self):
        """Export to Markdown preserves content."""
        processor = PostProcessor()
        md_result = processor.export_markdown(SAMPLE_HTML)

        assert md_result.format.value == "markdown"
        assert "쿠팡 파트너스" in md_result.content
        assert md_result.word_count > 0

    def test_export_saves_to_file(self, tmp_path):
        """Export result can be saved to file."""
        processor = PostProcessor()
        html_result = processor.export_html(SAMPLE_HTML)
        md_result = processor.export_markdown(SAMPLE_HTML)

        html_path = tmp_path / "output" / "blog.html"
        md_path = tmp_path / "output" / "blog.md"

        processor.save_export(html_result, html_path)
        processor.save_export(md_result, md_path)

        assert html_path.exists()
        assert md_path.exists()

        html_content = html_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html_content

    def test_pipeline_export_only(self):
        """PublishPipeline.export_only works with pre-generated HTML."""
        pipeline = PublishPipeline()
        results = pipeline.export_only(SAMPLE_HTML, title="테스트")

        assert "html" in results
        assert "markdown" in results


class TestCTAIntegration:
    """Test CTA manager link application."""

    def test_cta_plan_creates_entries(self):
        """CTA manager creates placement plan with entries per section."""
        cta = CTAManager()
        cta.register_link(
            "roborock-q-revo-s",
            "https://link.coupang.com/a/roborock",
            affiliate_tag="tco_blog",
        )

        product_ids = ["roborock-q-revo-s"]
        plan = cta.create_placement_plan(product_ids, campaign="robot_vacuum")

        roborock_entries = plan.get_entries_by_product("roborock-q-revo-s")
        assert len(roborock_entries) == 3  # Section 2, 3, 4


class TestStatsIntegration:
    """Test stats connector integration with the pipeline."""

    def test_record_post_metrics(self, tmp_path):
        """Stats connector records metrics for a published post."""
        metrics_file = tmp_path / "post_metrics.json"
        connector = StatsConnector(metrics_path=metrics_file)

        metrics = PostMetrics(
            post_id="robot-vacuum-2026-02",
            title="로봇청소기 TCO 비교",
            category="로봇청소기",
            publish_date="2026-02-07",
            platform="naver",
        )
        connector.record_metrics(metrics)

        retrieved = connector.get_metrics("robot-vacuum-2026-02")
        assert retrieved is not None
        assert retrieved.category == "로봇청소기"

    def test_save_and_load_metrics(self, tmp_path):
        """Stats data persists to disk and loads back."""
        metrics_file = tmp_path / "post_metrics.json"
        connector = StatsConnector(metrics_path=metrics_file)

        connector.record_metrics(PostMetrics(
            post_id="test-1",
            title="테스트 포스트",
            category="로봇청소기",
            publish_date="2026-02-07",
            platform="naver",
        ))

        # Create a new connector pointing at same file — should auto-load
        connector2 = StatsConnector(metrics_path=metrics_file)
        assert connector2.get_metrics("test-1") is not None


class TestDataContractCompliance:
    """Verify that the Part A → Part B data contract is followed."""

    def test_fixture_matches_api_contract(self):
        """sample_tco_data.json matches the consumable-based schema."""
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Top-level fields
        assert "category" in data
        assert "products" in data
        assert isinstance(data["products"], list)
        assert len(data["products"]) > 0

        # Per-product fields
        for p in data["products"]:
            assert "product_id" in p
            assert "name" in p
            assert "brand" in p
            assert "tco" in p

            tco = p["tco"]
            assert "purchase_price" in tco
            assert "annual_consumable_cost" in tco
            assert "consumable_cost_total" in tco
            assert "real_cost_total" in tco

            # TCO formula check: real_cost_total = purchase_price + consumable_cost_total
            expected_real_cost = tco["purchase_price"] + tco["consumable_cost_total"]
            assert tco["real_cost_total"] == expected_real_cost, (
                f"TCO formula mismatch for {p['name']}: "
                f"{tco['purchase_price']} + {tco['consumable_cost_total']} "
                f"= {expected_real_cost}, "
                f"but got {tco['real_cost_total']}"
            )

            # Consumable total = annual * tco_years
            tco_years = tco.get("tco_years", 3)
            expected_3yr = tco["annual_consumable_cost"] * tco_years
            assert tco["consumable_cost_total"] == expected_3yr, (
                f"Consumable total mismatch for {p['name']}: "
                f"{tco['annual_consumable_cost']} * {tco_years} = {expected_3yr}, "
                f"but got {tco['consumable_cost_total']}"
            )

    def test_all_tco_numeric_fields_are_numbers(self):
        """All quantitative TCO fields are numeric, not strings."""
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        numeric_keys = {"purchase_price", "annual_consumable_cost", "consumable_cost_total", "real_cost_total"}
        for p in data["products"]:
            tco = p["tco"]
            for key in numeric_keys:
                val = tco[key]
                assert isinstance(val, (int, float)), (
                    f"{p['name']}.tco.{key} should be numeric, got {type(val)}"
                )

    def test_consumable_costs_sum_correctly(self):
        """Consumable breakdown annual costs should sum to annual_consumable_cost."""
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for p in data["products"]:
            tco = p["tco"]
            breakdown = tco.get("consumable_breakdown", [])
            if breakdown:
                total = sum(item["annual_cost"] for item in breakdown)
                assert total == tco["annual_consumable_cost"], (
                    f"{p['name']} breakdown sum {total} != "
                    f"annual_consumable_cost {tco['annual_consumable_cost']}"
                )
