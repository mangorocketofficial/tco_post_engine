"""Tests for the content_writer module.

Tests cover:
- Writer configuration and initialization
- Prompt generation
- Enrichment response parsing
- Product data building (ensuring no data fabrication)
- Credibility stats calculation
- Price volatility calculation
- End-to-end generation with mocked LLM
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.part_b.content_writer.models import (
    GenerationResult,
    LLMProvider,
    ToneStyle,
    WriterConfig,
)
from src.part_b.content_writer.prompts import (
    SYSTEM_PROMPT,
    build_enrichment_prompt,
    build_title_prompt,
)
from src.part_b.content_writer.writer import ContentWriter


# === Fixtures ===


@pytest.fixture
def sample_tco_dict() -> dict:
    """Load sample TCO data as dictionary."""
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "sample_tco_data.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_tco_path() -> Path:
    """Path to sample TCO fixture."""
    return Path(__file__).parent.parent.parent / "fixtures" / "sample_tco_data.json"


@pytest.fixture
def mock_enrichment_response() -> str:
    """Mock LLM response with valid enrichment JSON."""
    return json.dumps({
        "situation_picks": [
            {
                "situation": "가성비 중시",
                "product_name": "로보락 Q Revo S",
                "reason": "3년 실질비용 534,000원으로 가장 낮음",
            },
            {
                "situation": "AS 걱정 없이 사용",
                "product_name": "삼성 비스포크 제트 AI",
                "reason": "AS 평균 3.1일로 가장 빠름",
            },
            {
                "situation": "프리미엄 올인원",
                "product_name": "에코백스 X2 콤보",
                "reason": "핸디청소기 겸용으로 활용도 최고",
            },
        ],
        "home_types": [
            {"type": "소형 원룸", "recommendation": "로보락 Q Revo S — 가성비 최고"},
            {"type": "중형 아파트 (20-30평)", "recommendation": "삼성 비스포크 제트 AI — 관리 편의성 우수"},
            {"type": "대형 주택 (40평+)", "recommendation": "에코백스 X2 콤보 — 핸디 겸용 활용도"},
        ],
        "faqs": [
            {
                "question": "로봇청소기 배터리 교체 비용이 얼마나 드나요?",
                "answer": "제품별로 다르지만, 데이터 기준 15만~20만원 범위입니다.",
            },
            {
                "question": "로봇청소기 AS 맡기면 얼마나 걸리나요?",
                "answer": "분석 데이터 기준 3.1일~8.5일까지 브랜드별로 차이가 있습니다.",
            },
            {
                "question": "로봇청소기 중고 판매 시 얼마에 팔 수 있나요?",
                "answer": "24개월 사용 기준 구매가의 47~50% 수준입니다.",
            },
        ],
        "products": [
            {
                "product_id": "roborock-q-revo-s",
                "highlight": "3년 실질비용 최저 — 가성비 끝판왕",
                "verdict": "recommend",
                "recommendation_reason": "3년 실질비용 534,000원으로 비교 제품 중 가장 낮습니다.",
                "caution_reason": "센서 오류 발생률 25%로 주의 필요",
            },
            {
                "product_id": "samsung-bespoke-jet-ai",
                "highlight": "AS 3.1일 — 국내 AS 최강",
                "verdict": "recommend",
                "recommendation_reason": "삼성 AS 네트워크 덕분에 평균 3.1일 만에 수리 완료됩니다.",
                "caution_reason": "구매가 대비 3년 비용이 685,000원으로 중간 수준",
            },
            {
                "product_id": "ecovacs-x2-combo",
                "highlight": "핸디청소기 겸용 올인원",
                "verdict": "caution",
                "recommendation_reason": "핸디청소기 겸용으로 별도 구매 비용 절감 가능",
                "caution_reason": "3년 실질비용 910,000원으로 가장 높고 AS 8.5일 소요",
            },
        ],
    }, ensure_ascii=False)


@pytest.fixture
def writer() -> ContentWriter:
    """Create a ContentWriter with default config."""
    return ContentWriter()


# === Test: Models ===


class TestWriterConfig:
    def test_default_config(self):
        config = WriterConfig()
        assert config.provider == LLMProvider.OPENAI
        assert config.temperature == 0.7
        assert config.tone == ToneStyle.CONVERSATIONAL
        assert config.target_category == "로봇청소기"

    def test_custom_config(self):
        config = WriterConfig(
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-5-20250929",
            temperature=0.5,
        )
        assert config.provider == LLMProvider.ANTHROPIC
        assert config.model == "claude-sonnet-4-5-20250929"

    def test_generation_result(self):
        result = GenerationResult(success=True, provider="openai", model="gpt-4o")
        assert result.success
        assert result.total_tokens == 0


# === Test: Prompts ===


class TestPrompts:
    def test_system_prompt_has_core_rules(self):
        assert "데이터 조작 금지" in SYSTEM_PROMPT
        assert "최저가 확인하기" in SYSTEM_PROMPT
        assert "국내 주요 커뮤니티 리뷰 데이터" in SYSTEM_PROMPT

    def test_enrichment_prompt_includes_products(self, sample_tco_dict):
        products = sample_tco_dict["products"]
        repair_context = [
            {
                "product_name": p["name"],
                "total_reports": p.get("repair_stats", {}).get("total_reports", 0),
                "failure_types": p.get("repair_stats", {}).get("failure_types", []),
            }
            for p in products
        ]

        prompt = build_enrichment_prompt("로봇청소기", products, repair_context)

        assert "로봇청소기" in prompt
        assert "로보락 Q Revo S" in prompt
        assert "534,000원" in prompt  # real_cost_3yr formatted
        assert "situation_picks" in prompt
        assert "faqs" in prompt

    def test_title_prompt(self, sample_tco_dict):
        products = sample_tco_dict["products"]
        prompt = build_title_prompt("로봇청소기", products)
        assert "로봇청소기" in prompt
        assert "로보락 Q Revo S" in prompt

    def test_enrichment_prompt_repair_context(self, sample_tco_dict):
        products = sample_tco_dict["products"]
        repair_context = [
            {
                "product_name": "로보락 Q Revo S",
                "total_reports": 127,
                "failure_types": [
                    {"type": "브러시 마모", "count": 45, "avg_cost": 35000, "probability": 0.35},
                ],
            },
        ]

        prompt = build_enrichment_prompt("로봇청소기", products, repair_context)
        assert "127건" in prompt
        assert "브러시 마모" in prompt


# === Test: Enrichment Parsing ===


class TestEnrichmentParsing:
    def test_parse_valid_json(self, writer, mock_enrichment_response):
        result = writer._parse_enrichment_response(mock_enrichment_response)

        assert len(result["situation_picks_parsed"]) == 3
        assert len(result["home_types_parsed"]) == 3
        assert len(result["faqs_parsed"]) == 3
        assert "roborock-q-revo-s" in result["product_enrichment"]

    def test_parse_json_in_code_block(self, writer, mock_enrichment_response):
        wrapped = f"Here is the result:\n```json\n{mock_enrichment_response}\n```"
        result = writer._parse_enrichment_response(wrapped)

        assert len(result["situation_picks_parsed"]) == 3

    def test_parse_invalid_json_returns_fallback(self, writer):
        result = writer._parse_enrichment_response("This is not JSON at all")

        assert result["situation_picks_parsed"] == []
        assert result["faqs_parsed"] == []
        assert result["product_enrichment"] == {}

    def test_situation_pick_fields(self, writer, mock_enrichment_response):
        result = writer._parse_enrichment_response(mock_enrichment_response)
        pick = result["situation_picks_parsed"][0]

        assert pick.situation == "가성비 중시"
        assert pick.product_name == "로보락 Q Revo S"
        assert "534,000" in pick.reason

    def test_faq_fields(self, writer, mock_enrichment_response):
        result = writer._parse_enrichment_response(mock_enrichment_response)
        faq = result["faqs_parsed"][0]

        assert "배터리" in faq.question
        assert faq.answer != ""


# === Test: Data Building (No Fabrication) ===


class TestDataBuilding:
    def test_build_products_preserves_tco_data(self, writer, sample_tco_dict, mock_enrichment_response):
        """Critical test: TCO numbers must pass through unchanged."""
        enrichment = writer._parse_enrichment_response(mock_enrichment_response)
        products = writer._build_products(sample_tco_dict["products"], enrichment)

        roborock = products[0]
        assert roborock.name == "로보락 Q Revo S"
        assert roborock.tco.purchase_price_avg == 899000  # Exact from fixture
        assert roborock.tco.purchase_price_min == 849000
        assert roborock.tco.resale_value_24mo == 450000
        assert roborock.tco.expected_repair_cost == 85000
        assert roborock.tco.real_cost_3yr == 534000
        assert roborock.tco.as_turnaround_days == 5.2
        assert roborock.tco.monthly_maintenance_minutes == 10

    def test_build_products_applies_enrichment(self, writer, sample_tco_dict, mock_enrichment_response):
        enrichment = writer._parse_enrichment_response(mock_enrichment_response)
        products = writer._build_products(sample_tco_dict["products"], enrichment)

        roborock = products[0]
        assert roborock.highlight != ""
        assert roborock.verdict == "recommend"
        assert roborock.recommendation_reason != ""

    def test_build_products_preserves_resale_curve(self, writer, sample_tco_dict, mock_enrichment_response):
        enrichment = writer._parse_enrichment_response(mock_enrichment_response)
        products = writer._build_products(sample_tco_dict["products"], enrichment)

        roborock = products[0]
        assert roborock.resale_curve is not None
        assert roborock.resale_curve.mo_6 == 85
        assert roborock.resale_curve.mo_24 == 50

    def test_build_products_preserves_repair_stats(self, writer, sample_tco_dict, mock_enrichment_response):
        enrichment = writer._parse_enrichment_response(mock_enrichment_response)
        products = writer._build_products(sample_tco_dict["products"], enrichment)

        roborock = products[0]
        assert roborock.repair_stats is not None
        assert roborock.repair_stats.total_reports == 127
        assert len(roborock.repair_stats.failure_types) == 4

    def test_build_products_preserves_maintenance(self, writer, sample_tco_dict, mock_enrichment_response):
        enrichment = writer._parse_enrichment_response(mock_enrichment_response)
        products = writer._build_products(sample_tco_dict["products"], enrichment)

        roborock = products[0]
        assert len(roborock.maintenance_tasks) == 2
        assert roborock.maintenance_tasks[0].task == "먼지통 비우기"

    def test_all_products_built(self, writer, sample_tco_dict, mock_enrichment_response):
        enrichment = writer._parse_enrichment_response(mock_enrichment_response)
        products = writer._build_products(sample_tco_dict["products"], enrichment)
        assert len(products) == 3


# === Test: Credibility Stats ===


class TestCredibilityStats:
    def test_credibility_counts_from_data(self, writer, sample_tco_dict):
        stats = writer._build_credibility_stats(sample_tco_dict["products"])

        # 3 products × 5 price entries = 15
        assert stats.price_data_count == 15
        # 127 + 89 + 156 = 372 total repair reports
        assert stats.repair_data_count == 372
        # 3 products with resale curves × 20 estimate = 60
        assert stats.resale_data_count == 60
        # Total: 372 + 15 + 60 = 447
        assert stats.total_review_count == 447

    def test_maintenance_data_count(self, writer, sample_tco_dict):
        stats = writer._build_credibility_stats(sample_tco_dict["products"])
        # 2 + 2 + 3 = 7 maintenance tasks
        assert stats.maintenance_data_count == 7


# === Test: Price Volatility ===


class TestPriceVolatility:
    def test_price_volatility_from_history(self, writer, sample_tco_dict):
        volatility = writer._build_price_volatility(sample_tco_dict["products"])

        assert volatility is not None
        assert "원" in volatility.min_diff
        assert volatility.updated_date != ""

    def test_price_volatility_none_for_empty_data(self, writer):
        volatility = writer._build_price_volatility([])
        assert volatility is None

    def test_price_volatility_none_for_single_price(self, writer):
        products = [{"price_history": [{"price": 100000}]}]
        volatility = writer._build_price_volatility(products)
        assert volatility is None


# === Test: End-to-End with Mocked LLM ===


class TestEndToEnd:
    @patch.object(ContentWriter, "_call_llm")
    def test_generate_from_dict(self, mock_llm, sample_tco_dict, mock_enrichment_response):
        # First call = enrichment, second call = title
        mock_llm.side_effect = [
            mock_enrichment_response,
            "2026년 로봇청소기 추천 TOP 3 — 3년 실제 비용 비교",
        ]

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_dict=sample_tco_dict)

        assert blog_data.title == "2026년 로봇청소기 추천 TOP 3 — 3년 실제 비용 비교"
        assert blog_data.category == "로봇청소기"
        assert len(blog_data.products) == 3
        assert len(blog_data.top_products) == 3
        assert len(blog_data.situation_picks) == 3
        assert len(blog_data.home_types) == 3
        assert len(blog_data.faqs) == 3
        assert blog_data.credibility.total_review_count > 0

    @patch.object(ContentWriter, "_call_llm")
    def test_generate_from_path(self, mock_llm, sample_tco_path, mock_enrichment_response):
        mock_llm.side_effect = [
            mock_enrichment_response,
            "로봇청소기 3년 비용 비교",
        ]

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_path=sample_tco_path)

        assert len(blog_data.products) == 3
        assert blog_data.products[0].tco.purchase_price_avg == 899000

    @patch.object(ContentWriter, "_call_llm")
    def test_top_products_sorted_by_cost(self, mock_llm, sample_tco_dict, mock_enrichment_response):
        mock_llm.side_effect = [mock_enrichment_response, "Test Title"]

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_dict=sample_tco_dict)

        # Top products should be sorted by real_cost_3yr ascending
        costs = [p.tco.real_cost_3yr for p in blog_data.top_products]
        assert costs == sorted(costs)

    @patch.object(ContentWriter, "_call_llm")
    def test_generate_preserves_all_numeric_data(self, mock_llm, sample_tco_dict, mock_enrichment_response):
        """Critical: verify no numeric data is fabricated or altered."""
        mock_llm.side_effect = [mock_enrichment_response, "Title"]

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_dict=sample_tco_dict)

        # Check every product's TCO data matches the input exactly
        for i, product in enumerate(blog_data.products):
            raw = sample_tco_dict["products"][i]["tco"]
            assert product.tco.purchase_price_avg == raw["purchase_price_avg"]
            assert product.tco.purchase_price_min == raw["purchase_price_min"]
            assert product.tco.resale_value_24mo == raw["resale_value_24mo"]
            assert product.tco.expected_repair_cost == raw["expected_repair_cost"]
            assert product.tco.real_cost_3yr == raw["real_cost_3yr"]
            assert product.tco.as_turnaround_days == raw["as_turnaround_days"]
            assert product.tco.monthly_maintenance_minutes == raw["monthly_maintenance_minutes"]

    def test_generate_no_data_raises(self):
        writer = ContentWriter()
        with pytest.raises(ValueError, match="Provide either"):
            writer.generate()

    def test_generate_empty_products_raises(self):
        writer = ContentWriter()
        with pytest.raises(ValueError, match="No products found"):
            writer.generate(tco_data_dict={"products": []})


# === Test: Template Integration ===


class TestTemplateIntegration:
    @patch.object(ContentWriter, "_call_llm")
    def test_blog_data_renders_with_template(self, mock_llm, sample_tco_dict, mock_enrichment_response):
        """Verify generated BlogPostData is compatible with template engine."""
        from src.part_b.template_engine import render_blog_post

        mock_llm.side_effect = [mock_enrichment_response, "Test Blog Title"]

        writer = ContentWriter()
        blog_data = writer.generate(tco_data_dict=sample_tco_dict)

        # This should not raise
        rendered = render_blog_post(blog_data)

        assert "Test Blog Title" in rendered
        assert "로보락 Q Revo S" in rendered
        assert "534,000" in rendered or "534000" in rendered
