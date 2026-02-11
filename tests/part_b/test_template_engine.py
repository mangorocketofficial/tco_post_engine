"""
Unit tests for the template engine data models.
Tests data model creation, context building, and model integrity.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.part_b.template_engine import (
    BlogPostData,
    CategoryCriteria,
    ConsumableItem,
    CredibilityStats,
    FAQ,
    HomeType,
    PriceVolatility,
    Product,
    SituationPick,
    TCOData,
)


@pytest.fixture
def sample_tco_data() -> TCOData:
    """Create sample TCO data for testing."""
    return TCOData(
        purchase_price=899000,
        annual_consumable_cost=60000,
        consumable_cost_total=180000,
        real_cost_total=1079000,
        consumable_breakdown=[
            ConsumableItem(name="필터", unit_price=15000, changes_per_year=2, annual_cost=30000, compatible_available=True, compatible_price=8000),
            ConsumableItem(name="사이드브러시", unit_price=10000, changes_per_year=2, annual_cost=20000),
            ConsumableItem(name="먼지봉투", unit_price=5000, changes_per_year=2, annual_cost=10000),
        ],
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
            consumable_data_count=30,
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


class TestDataModels:
    """Tests for data model classes."""

    def test_tco_data_creation(self):
        """Test TCOData dataclass creation."""
        tco = TCOData(
            purchase_price=900000,
            annual_consumable_cost=60000,
            consumable_cost_total=180000,
            real_cost_total=1080000,
        )

        assert tco.purchase_price == 900000
        assert tco.real_cost_total == 1080000
        assert tco.annual_consumable_cost == 60000

    def test_blog_post_data_to_template_context(self, sample_blog_data: BlogPostData):
        """Test BlogPostData to_template_context method."""
        context = sample_blog_data.to_template_context()

        assert "title" in context
        assert "category" in context
        assert "products" in context
        assert "faqs" in context
        assert context["total_review_count"] == 100

    def test_consumable_breakdown_in_context(self, sample_blog_data: BlogPostData):
        """Test consumable_breakdown is included in product context."""
        context = sample_blog_data.to_template_context()
        product = context["products"][0]

        tco = product["tco"]
        assert "consumable_breakdown" in tco
        assert len(tco["consumable_breakdown"]) == 3
        assert tco["consumable_breakdown"][0]["name"] == "필터"

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
