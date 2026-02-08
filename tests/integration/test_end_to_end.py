"""End-to-end integration tests for the TCO Post Engine pipeline.

Tests the full flow:
TCO data → ContentWriter → CTA Manager → Template Engine → PostProcessor → Export

Uses mock LLM responses to avoid API calls during testing.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.part_b.content_writer.writer import ContentWriter
from src.part_b.content_writer.models import WriterConfig, LLMProvider
from src.part_b.cta_manager.manager import CTAManager
from src.part_b.cta_manager.models import AffiliateLink, AffiliatePlatform
from src.part_b.template_engine import render_blog_post
from src.part_b.publisher.processor import PostProcessor
from src.part_b.publisher.pipeline import PublishPipeline
from src.part_b.publisher.models import SEOMetaTags
from src.part_b.stats_connector.connector import StatsConnector
from src.part_b.stats_connector.models import PostMetrics


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "sample_tco_data.json"

# Mock LLM response for enrichment
MOCK_ENRICHMENT_RESPONSE = json.dumps({
    "situation_picks": [
        {
            "situation": "1인 가구 원룸",
            "product_name": "로보락 Q Revo S",
            "reason": "가격 대비 성능이 뛰어나고 3년 실질 비용이 가장 낮습니다."
        },
        {
            "situation": "반려동물 가정",
            "product_name": "삼성 비스포크 제트 AI",
            "reason": "AS 속도가 빠르고 자동 비움 기능으로 관리가 편리합니다."
        },
    ],
    "home_types": [
        {"type": "아파트 (30평 이상)", "recommendation": "삼성 비스포크 제트 AI — 넓은 공간 매핑에 강점"},
        {"type": "빌라/투룸", "recommendation": "로보락 Q Revo S — 가성비 최고"},
    ],
    "faqs": [
        {
            "question": "로봇청소기 배터리 수명은 얼마나 되나요?",
            "answer": "평균 2-3년이며, 교체 비용은 15-20만원 수준입니다."
        },
        {
            "question": "AS 기간은 보통 얼마나 걸리나요?",
            "answer": "브랜드별로 3-9일 소요되며, 삼성이 가장 빠릅니다."
        },
    ],
    "category_criteria": {
        "myth_busting": "흡입력 Pa 수치 차이는 실제 픽업률에 거의 영향이 없습니다.",
        "real_differentiator": "물걸레 위생 관리 시스템이 진짜 차별점입니다.",
        "decision_fork": "전선이 많은 집은 카메라 AI, 깔끔한 집은 LiDAR만으로 충분합니다.",
    },
    "products": [
        {
            "product_id": "roborock-q-revo-s",
            "highlight": "3년 실질 비용 53만원으로 최저 — 가성비 끝판왕",
            "slot_label": "최소 비용 실속",
            "verdict": "recommend",
            "recommendation_reason": "TCO가 가장 낮고 유지보수도 간편합니다.",
            "caution_reason": ""
        },
        {
            "product_id": "samsung-bespoke-jet-ai",
            "highlight": "삼성 AS 네트워크 — 수리 3일 만에 완료",
            "slot_label": "고장 스트레스 제로",
            "verdict": "recommend",
            "recommendation_reason": "AS가 빠르고 소프트웨어 업데이트가 꾸준합니다.",
            "caution_reason": ""
        },
        {
            "product_id": "ecovacs-x2-combo",
            "highlight": "핸디+로봇 2-in-1이지만 수리 비용 주의",
            "slot_label": "풀옵션 올인원",
            "verdict": "caution",
            "recommendation_reason": "",
            "caution_reason": "기대 수리비가 12만원으로 가장 높고, AS 소요일이 8.5일입니다."
        },
    ],
})

MOCK_TITLE = "2026년 로봇청소기 3년 실질 비용 비교 — 데이터 534건 분석"


class TestFullPipeline:
    """End-to-end pipeline tests using mock LLM responses."""

    def _load_fixture(self) -> dict:
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _mock_call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Mock LLM call that returns enrichment or title."""
        if "제목" in user_prompt or "title" in user_prompt.lower():
            return MOCK_TITLE
        return MOCK_ENRICHMENT_RESPONSE

    @patch.object(ContentWriter, "_call_llm")
    def test_content_writer_produces_blog_data(self, mock_llm):
        """ContentWriter generates BlogPostData from TCO fixture."""
        mock_llm.side_effect = self._mock_call_llm

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_path=FIXTURE_PATH)

        assert blog_data.title == MOCK_TITLE
        assert blog_data.category == "로봇청소기"
        assert len(blog_data.products) == 3
        assert len(blog_data.faqs) == 2
        assert len(blog_data.situation_picks) == 2
        assert len(blog_data.home_types) == 2
        assert blog_data.credibility is not None
        assert blog_data.price_volatility is not None

    @patch.object(ContentWriter, "_call_llm")
    def test_numeric_data_preserved(self, mock_llm):
        """All numeric data from Part A passes through unchanged."""
        mock_llm.side_effect = self._mock_call_llm

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_path=FIXTURE_PATH)

        # Check first product (roborock)
        roborock = next(p for p in blog_data.products if p.product_id == "roborock-q-revo-s")
        assert roborock.tco.purchase_price_avg == 899000
        assert roborock.tco.purchase_price_min == 849000
        assert roborock.tco.resale_value_1yr == 650000
        assert roborock.tco.resale_value_2yr == 450000
        assert roborock.tco.resale_value_3yr_plus == 315000
        assert roborock.tco.expected_repair_cost == 85000
        assert roborock.tco.real_cost_3yr == 534000

        # Check resale curve preserved
        assert roborock.resale_curve is not None
        assert roborock.resale_curve.yr_1 == 72
        assert roborock.resale_curve.yr_3_plus == 35

        # Check repair stats preserved
        assert roborock.repair_stats is not None
        assert roborock.repair_stats.total_reports == 127
        assert len(roborock.repair_stats.failure_types) == 4

    @patch.object(ContentWriter, "_call_llm")
    def test_top_products_sorted_by_tco(self, mock_llm):
        """Top products are sorted by lowest real_cost_3yr."""
        mock_llm.side_effect = self._mock_call_llm

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_path=FIXTURE_PATH)

        costs = [p.tco.real_cost_3yr for p in blog_data.top_products]
        assert costs == sorted(costs)
        assert blog_data.top_products[0].product_id == "roborock-q-revo-s"

    @patch.object(ContentWriter, "_call_llm")
    def test_template_renders_blog_post(self, mock_llm):
        """Template engine renders BlogPostData to markdown."""
        mock_llm.side_effect = self._mock_call_llm

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_path=FIXTURE_PATH)

        rendered = render_blog_post(blog_data)

        assert isinstance(rendered, str)
        assert len(rendered) > 100
        # Contains the title
        assert MOCK_TITLE in rendered or blog_data.title in rendered
        # Contains product names
        assert "로보락" in rendered
        assert "삼성" in rendered
        assert "에코백스" in rendered
        # Contains TCO numbers (formatted)
        assert "534,000" in rendered or "534000" in rendered

    @patch.object(ContentWriter, "_call_llm")
    def test_cta_links_applied(self, mock_llm):
        """CTA manager applies affiliate links to blog data."""
        mock_llm.side_effect = self._mock_call_llm

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_path=FIXTURE_PATH)

        # Set up CTA manager with affiliate links
        cta = CTAManager()
        cta.register_link(
            "roborock-q-revo-s",
            "https://link.coupang.com/a/roborock",
            affiliate_tag="tco_blog",
        )
        cta.register_link(
            "samsung-bespoke-jet-ai",
            "https://link.coupang.com/a/samsung",
            affiliate_tag="tco_blog",
        )

        # Create placement plan
        product_ids = [p.product_id for p in blog_data.products]
        plan = cta.create_placement_plan(product_ids, campaign="robot_vacuum")

        # Verify plan has correct entries
        roborock_entries = plan.get_entries_by_product("roborock-q-revo-s")
        assert len(roborock_entries) == 3  # Section 3, 4, 5

        # Apply CTA links using pipeline-style pattern
        for product in blog_data.products:
            entries = plan.get_entries_by_product(product.product_id)
            if entries:
                product.cta_link = entries[0].url

        roborock = next(p for p in blog_data.products if p.product_id == "roborock-q-revo-s")
        assert roborock.cta_link is not None
        assert "coupang" in roborock.cta_link

    @patch.object(ContentWriter, "_call_llm")
    def test_post_processor_adds_disclosure(self, mock_llm):
        """Post-processor adds affiliate disclosure to content."""
        mock_llm.side_effect = self._mock_call_llm

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_path=FIXTURE_PATH)

        rendered = render_blog_post(blog_data)

        processor = PostProcessor()
        processed = processor.process(rendered)

        assert "쿠팡 파트너스" in processed

    @patch.object(ContentWriter, "_call_llm")
    def test_html_export(self, mock_llm):
        """Export to HTML produces valid structure."""
        mock_llm.side_effect = self._mock_call_llm

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_path=FIXTURE_PATH)
        rendered = render_blog_post(blog_data)

        processor = PostProcessor()
        seo = SEOMetaTags(
            title=blog_data.title,
            description="로봇청소기 TCO 비교",
            keywords=["로봇청소기", "TCO", "비교"],
        )
        html_result = processor.export_html(rendered, seo)

        assert html_result.format.value == "html"
        assert "<!DOCTYPE html>" in html_result.content
        assert '<html lang="ko">' in html_result.content
        assert html_result.word_count > 0

    @patch.object(ContentWriter, "_call_llm")
    def test_markdown_export(self, mock_llm):
        """Export to Markdown preserves content."""
        mock_llm.side_effect = self._mock_call_llm

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_path=FIXTURE_PATH)
        rendered = render_blog_post(blog_data)

        processor = PostProcessor()
        md_result = processor.export_markdown(rendered)

        assert md_result.format.value == "markdown"
        assert "쿠팡 파트너스" in md_result.content
        assert md_result.word_count > 0

    @patch.object(ContentWriter, "_call_llm")
    def test_export_saves_to_file(self, mock_llm, tmp_path):
        """Export result can be saved to file."""
        mock_llm.side_effect = self._mock_call_llm

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_path=FIXTURE_PATH)
        rendered = render_blog_post(blog_data)

        processor = PostProcessor()
        html_result = processor.export_html(rendered)
        md_result = processor.export_markdown(rendered)

        html_path = tmp_path / "output" / "blog.html"
        md_path = tmp_path / "output" / "blog.md"

        processor.save_export(html_result, html_path)
        processor.save_export(md_result, md_path)

        assert html_path.exists()
        assert md_path.exists()

        html_content = html_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html_content

        md_content = md_path.read_text(encoding="utf-8")
        assert len(md_content) > 100


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
        """sample_tco_data.json matches the schema in api-contract.json."""
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
            assert "purchase_price_avg" in tco
            assert "purchase_price_min" in tco
            assert "resale_value_1yr" in tco
            assert "resale_value_2yr" in tco
            assert "resale_value_3yr_plus" in tco
            assert "expected_repair_cost" in tco
            assert "real_cost_3yr" in tco
            assert "as_turnaround_days" in tco
            assert "monthly_maintenance_minutes" in tco

            # TCO formula check (uses 2yr resale)
            expected_real_cost = (
                tco["purchase_price_avg"]
                + tco["expected_repair_cost"]
                - tco["resale_value_2yr"]
            )
            assert tco["real_cost_3yr"] == expected_real_cost, (
                f"TCO formula mismatch for {p['name']}: "
                f"{tco['purchase_price_avg']} + {tco['expected_repair_cost']} "
                f"- {tco['resale_value_2yr']} = {expected_real_cost}, "
                f"but got {tco['real_cost_3yr']}"
            )

    def test_all_numeric_fields_are_numbers(self):
        """All quantitative fields in TCO data are numeric, not strings."""
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for p in data["products"]:
            tco = p["tco"]
            for key, val in tco.items():
                assert isinstance(val, (int, float)), (
                    f"{p['name']}.tco.{key} should be numeric, got {type(val)}"
                )

    def test_resale_curve_values_are_percentages(self):
        """Resale curve values are retention percentages (0-100)."""
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for p in data["products"]:
            curve = p.get("resale_curve", {})
            for period, pct in curve.items():
                assert 0 <= pct <= 100, (
                    f"{p['name']}.resale_curve.{period} = {pct} out of 0-100 range"
                )

    def test_repair_probabilities_sum_approximately_1(self):
        """Failure type probabilities should sum to approximately 1.0."""
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for p in data["products"]:
            stats = p.get("repair_stats", {})
            failures = stats.get("failure_types", [])
            if failures:
                total_prob = sum(f["probability"] for f in failures)
                assert 0.95 <= total_prob <= 1.05, (
                    f"{p['name']} failure probabilities sum to {total_prob}, "
                    f"expected ~1.0"
                )
