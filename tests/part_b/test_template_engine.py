"""
Unit tests for the template engine module.
Tests template loading, variable substitution, and blog post rendering.
"""

import json
import sys
from pathlib import Path

import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.part_b.template_engine import (
    BlogPostData,
    CategoryCriteria,
    CredibilityStats,
    FAQ,
    HomeType,
    MaintenanceTask,
    PriceVolatility,
    Product,
    ResaleCurve,
    SituationPick,
    TCOData,
    TemplateRenderer,
    load_tco_data_from_json,
    render_blog_post,
)


@pytest.fixture
def sample_tco_data() -> TCOData:
    """Create sample TCO data for testing."""
    return TCOData(
        purchase_price_avg=899000,
        purchase_price_min=849000,
        resale_value_1yr=650000,
        resale_value_2yr=450000,
        resale_value_3yr_plus=315000,
        expected_repair_cost=85000,
        real_cost_3yr=534000,
        as_turnaround_days=5.2,
        monthly_maintenance_minutes=10,
    )


@pytest.fixture
def sample_product(sample_tco_data: TCOData) -> Product:
    """Create sample product for testing."""
    return Product(
        product_id="test-product-1",
        name="테스트 로봇청소기",
        brand="테스트브랜드",
        release_date="2024-01-01",
        tco=sample_tco_data,
        resale_curve=ResaleCurve(yr_1=72, yr_2=50, yr_3_plus=35),
        maintenance_tasks=[
            MaintenanceTask(task="먼지통 비우기", frequency_per_month=4, minutes_per_task=1, automated=True),
            MaintenanceTask(task="필터 세척", frequency_per_month=2, minutes_per_task=3, automated=False),
        ],
        cta_link="https://example.com/test",
        highlight="테스트 추천 포인트",
        slot_label="테스트 슬롯",
        verdict="recommend",
        recommendation_reason="테스트 추천 이유입니다.",
    )


@pytest.fixture
def sample_blog_data(sample_product: Product) -> BlogPostData:
    """Create sample blog post data for testing."""
    products = [sample_product]
    return BlogPostData(
        title="테스트 블로그 포스트 제목",
        category="로봇청소기",
        generated_at="2026-02-07",
        products=products,
        top_products=products,
        situation_picks=[
            SituationPick(
                situation="가성비 중시",
                product_name="테스트 로봇청소기",
                reason="테스트 이유",
            )
        ],
        home_types=[
            HomeType(
                type="소형 원룸",
                recommendation="테스트 로봇청소기 추천",
            )
        ],
        faqs=[
            FAQ(
                question="테스트 질문입니다?",
                answer="테스트 답변입니다.",
            )
        ],
        credibility=CredibilityStats(
            total_review_count=100,
            price_data_count=50,
            resale_data_count=30,
            repair_data_count=40,
            as_review_count=20,
            maintenance_data_count=15,
        ),
        category_criteria=CategoryCriteria(
            myth_busting="흡입력 수치보다 실제 픽업률이 중요합니다.",
            real_differentiator="물걸레 위생 관리가 진짜 차별점입니다.",
            decision_fork="전선이 많은 집은 카메라 AI가 필수입니다.",
        ),
        price_volatility=PriceVolatility(
            min_diff="10,000",
            max_diff="50,000",
            status="평균 대비 저렴한 시기",
            updated_date="2026-02-07",
        ),
        price_updated_date="2026-02-07",
    )


class TestTemplateRenderer:
    """Tests for TemplateRenderer class."""

    def test_renderer_initialization(self):
        """Test that renderer initializes correctly."""
        renderer = TemplateRenderer()
        assert renderer.templates_dir.exists()
        assert renderer.env is not None

    def test_custom_templates_dir(self, tmp_path):
        """Test renderer with custom templates directory."""
        # Create a minimal template
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "test.jinja2").write_text("Hello {{ name }}!")

        renderer = TemplateRenderer(templates_dir=templates_dir)
        result = renderer.render_section("test", {"name": "World"})
        assert result == "Hello World!"

    def test_render_section_hook(self):
        """Test rendering Section 0 (Hook)."""
        renderer = TemplateRenderer()
        context = {
            "category": "로봇청소기",
            "situation_picks": [
                {"situation": "가성비", "product_name": "로보락", "reason": "저렴함"}
            ],
        }
        result = renderer.render_section("section_0_hook", context)

        assert "로봇청소기" in result
        assert "가성비" in result
        assert "로보락" in result

    def test_render_section_credibility(self):
        """Test rendering Section 1 (Credibility)."""
        renderer = TemplateRenderer()
        context = {
            "total_review_count": 372,
            "price_data_count": 450,
            "resale_data_count": 89,
            "repair_data_count": 156,
            "as_review_count": 67,
            "maintenance_data_count": 45,
        }
        result = renderer.render_section("section_1_credibility", context)

        assert "372" in result
        assert "자체 분석" in result
        assert "다나와" in result

    def test_render_section_quick_pick(self):
        """Test rendering Section 3 (Quick Pick Table)."""
        renderer = TemplateRenderer()
        context = {
            "top_products": [
                {
                    "name": "로보락 Q Revo S",
                    "tco": {"real_cost_3yr": 534000},
                    "highlight": "가성비 최강",
                    "cta_link": "https://example.com/roborock",
                }
            ],
            "price_updated_date": "2026-02-07",
        }
        result = renderer.render_section("section_3_quick_pick", context)

        assert "로보락 Q Revo S" in result
        assert "534,000" in result
        assert "최저가 확인하기" in result

    def test_render_section_faq(self):
        """Test rendering Section 6 (FAQ)."""
        renderer = TemplateRenderer()
        context = {
            "faqs": [
                {"question": "테스트 질문?", "answer": "테스트 답변입니다."},
                {"question": "두번째 질문?", "answer": "두번째 답변입니다."},
            ]
        }
        result = renderer.render_section("section_6_faq", context)

        assert "테스트 질문?" in result
        assert "테스트 답변입니다." in result
        assert "Q1" in result
        assert "Q2" in result


class TestBlogPostRendering:
    """Tests for complete blog post rendering."""

    def test_render_complete_blog_post(self, sample_blog_data: BlogPostData):
        """Test rendering a complete blog post."""
        result = render_blog_post(sample_blog_data)

        # Check title
        assert "테스트 블로그 포스트 제목" in result

        # Check all sections are present
        assert "1분 요약" in result  # Section 0
        assert "신뢰할 수 있는 이유" in result  # Section 1
        assert "진짜 중요한 기준" in result  # Section 2
        assert "한눈에 보는 추천" in result  # Section 3
        assert "상세 분석" in result  # Section 4
        assert "지금 확인해야 하는 이유" in result  # Section 5
        assert "자주 묻는 질문" in result  # Section 6

    def test_render_with_multiple_products(self):
        """Test rendering with multiple products."""
        products = [
            Product(
                product_id=f"product-{i}",
                name=f"제품 {i}",
                brand=f"브랜드 {i}",
                release_date="2024-01-01",
                tco=TCOData(
                    purchase_price_avg=1000000 * (i + 1),
                    purchase_price_min=900000 * (i + 1),
                    resale_value_1yr=700000 * (i + 1),
                    resale_value_2yr=500000 * (i + 1),
                    resale_value_3yr_plus=350000 * (i + 1),
                    expected_repair_cost=50000 * (i + 1),
                    real_cost_3yr=550000 * (i + 1),
                    as_turnaround_days=3.0 + i,
                    monthly_maintenance_minutes=5 * (i + 1),
                ),
                cta_link=f"https://example.com/product-{i}",
                highlight=f"추천 포인트 {i}",
                verdict="recommend",
                recommendation_reason=f"추천 이유 {i}",
            )
            for i in range(3)
        ]

        blog_data = BlogPostData(
            title="멀티 제품 테스트",
            category="로봇청소기",
            generated_at="2026-02-07",
            products=products,
            top_products=products,
            situation_picks=[
                SituationPick("상황1", "제품 0", "이유1"),
                SituationPick("상황2", "제품 1", "이유2"),
                SituationPick("상황3", "제품 2", "이유3"),
            ],
            home_types=[HomeType("타입1", "추천1")],
            faqs=[FAQ("질문?", "답변")],
            credibility=CredibilityStats(100, 50, 30, 40, 20, 15),
            price_volatility=None,
            price_updated_date="2026-02-07",
        )

        result = render_blog_post(blog_data)

        # All products should be in the output
        assert "제품 0" in result
        assert "제품 1" in result
        assert "제품 2" in result

        # TCO table should have all products
        assert "1,000,000원" in result
        assert "2,000,000원" in result
        assert "3,000,000원" in result

    def test_disclosure_statement_present(self, sample_blog_data: BlogPostData):
        """Test that affiliate disclosure is present."""
        result = render_blog_post(sample_blog_data)

        assert "쿠팡 파트너스" in result
        assert "수수료" in result

    def test_cta_links_present(self, sample_blog_data: BlogPostData):
        """Test that CTA links are rendered correctly."""
        result = render_blog_post(sample_blog_data)

        assert "최저가 확인하기" in result
        assert "https://example.com/test" in result


class TestTCODataLoading:
    """Tests for loading TCO data from JSON."""

    def test_load_tco_data_from_json(self, tmp_path):
        """Test loading TCO data from JSON file."""
        json_data = {
            "category": "로봇청소기",
            "generated_at": "2026-02-07T12:00:00+09:00",
            "products": [
                {
                    "product_id": "test-1",
                    "name": "테스트 제품",
                    "brand": "테스트",
                    "release_date": "2024-01-01",
                    "tco": {
                        "purchase_price_avg": 899000,
                        "purchase_price_min": 849000,
                        "resale_value_1yr": 650000,
                        "resale_value_2yr": 450000,
                        "resale_value_3yr_plus": 315000,
                        "expected_repair_cost": 85000,
                        "real_cost_3yr": 534000,
                        "as_turnaround_days": 5.2,
                        "monthly_maintenance_minutes": 10,
                    },
                }
            ],
        }

        json_path = tmp_path / "test_tco.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False)

        products = load_tco_data_from_json(json_path)

        assert len(products) == 1
        assert products[0].name == "테스트 제품"
        assert products[0].tco.real_cost_3yr == 534000

    def test_load_sample_fixture(self):
        """Test loading the sample fixture file."""
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "sample_tco_data.json"

        if fixture_path.exists():
            products = load_tco_data_from_json(fixture_path)

            assert len(products) == 3
            assert any("로보락" in p.name for p in products)
            assert any("삼성" in p.name for p in products)
            assert any("에코백스" in p.name for p in products)


class TestDataModels:
    """Tests for data model classes."""

    def test_tco_data_creation(self):
        """Test TCOData dataclass creation."""
        tco = TCOData(
            purchase_price_avg=900000,
            purchase_price_min=850000,
            resale_value_1yr=650000,
            resale_value_2yr=450000,
            resale_value_3yr_plus=315000,
            expected_repair_cost=80000,
            real_cost_3yr=530000,
            as_turnaround_days=5.0,
            monthly_maintenance_minutes=10,
        )

        assert tco.purchase_price_avg == 900000
        assert tco.real_cost_3yr == 530000

    def test_resale_curve_to_dict(self):
        """Test ResaleCurve to_dict method."""
        curve = ResaleCurve(yr_1=72, yr_2=50, yr_3_plus=35)
        result = curve.to_dict()

        assert result["1yr"] == 72
        assert result["2yr"] == 50
        assert result["3yr_plus"] == 35

    def test_blog_post_data_to_template_context(self, sample_blog_data: BlogPostData):
        """Test BlogPostData to_template_context method."""
        context = sample_blog_data.to_template_context()

        assert "title" in context
        assert "category" in context
        assert "products" in context
        assert "faqs" in context
        assert context["total_review_count"] == 100

    def test_automation_rate_calculation(self, sample_blog_data: BlogPostData):
        """Test automation_rate is calculated from maintenance tasks."""
        context = sample_blog_data.to_template_context()
        product = context["products"][0]

        # 1 automated out of 2 tasks = 50%
        assert product["automation_rate"] == 50

    def test_category_criteria_in_context(self, sample_blog_data: BlogPostData):
        """Test category_criteria is included in template context."""
        context = sample_blog_data.to_template_context()

        assert context["category_criteria"] is not None
        assert "흡입력" in context["category_criteria"]["myth_busting"]
        assert "물걸레" in context["category_criteria"]["real_differentiator"]

    def test_slot_label_in_context(self, sample_blog_data: BlogPostData):
        """Test slot_label is included in product context."""
        context = sample_blog_data.to_template_context()
        product = context["products"][0]

        assert product["slot_label"] == "테스트 슬롯"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_products_list(self):
        """Test rendering with empty products list."""
        blog_data = BlogPostData(
            title="빈 제품 테스트",
            category="로봇청소기",
            generated_at="2026-02-07",
            products=[],
            top_products=[],
            situation_picks=[],
            home_types=[],
            faqs=[],
            credibility=CredibilityStats(0, 0, 0, 0, 0, 0),
            price_volatility=None,
            price_updated_date="",
        )

        # Should not raise an exception
        result = render_blog_post(blog_data)
        assert "빈 제품 테스트" in result

    def test_korean_text_encoding(self, sample_blog_data: BlogPostData):
        """Test that Korean text is rendered correctly."""
        result = render_blog_post(sample_blog_data)

        # Check various Korean text patterns
        assert "추천" in result
        assert "청소기" in result
        assert "분석" in result
        assert "비용" in result

    def test_large_numbers_formatting(self):
        """Test that large KRW numbers are formatted correctly."""
        product = Product(
            product_id="expensive",
            name="고가 제품",
            brand="테스트",
            release_date="2024-01-01",
            tco=TCOData(
                purchase_price_avg=12345678,
                purchase_price_min=11234567,
                resale_value_1yr=8500000,
                resale_value_2yr=6000000,
                resale_value_3yr_plus=4000000,
                expected_repair_cost=500000,
                real_cost_3yr=6845678,
                as_turnaround_days=4.5,
                monthly_maintenance_minutes=8,
            ),
            cta_link="https://example.com",
            highlight="테스트",
            verdict="recommend",
            recommendation_reason="테스트",
        )

        renderer = TemplateRenderer()
        context = {
            "top_products": [
                {
                    "name": product.name,
                    "tco": {"real_cost_3yr": product.tco.real_cost_3yr},
                    "highlight": product.highlight,
                    "cta_link": product.cta_link,
                }
            ],
            "price_updated_date": "2026-02-07",
        }
        result = renderer.render_section("section_3_quick_pick", context)

        # Should have comma-formatted number
        assert "6,845,678" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
