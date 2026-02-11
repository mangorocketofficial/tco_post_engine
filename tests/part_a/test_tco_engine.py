"""Tests for the TCO engine module (consumable-based, JSON mode)."""

from __future__ import annotations

import json

import pytest

from src.part_a.tco_engine.calculator import TCOCalculator
from src.part_a.tco_engine.exporter import TCOExporter


@pytest.fixture
def a0_data(tmp_path):
    """Create a temporary A0 selected products JSON file."""
    data = {
        "selected_tier": "가성비",
        "tier_scores": {"가성비": 85, "프리미엄": 72},
        "tier_product_counts": {"가성비": 2, "프리미엄": 1},
        "candidate_pool_size": 15,
        "selected_products": [
            {
                "product_id": "roborock-q-revo-s",
                "name": "로보락 Q Revo S",
                "brand": "로보락",
                "release_date": "2024-06-01",
                "purchase_price": 899000,
                "rank": 1,
                "total_score": 92,
            },
            {
                "product_id": "samsung-jetbot-ai",
                "name": "삼성 비스포크 제트봇 AI",
                "brand": "삼성",
                "release_date": "2024-03-15",
                "purchase_price": 1290000,
                "rank": 2,
                "total_score": 88,
            },
        ],
    }
    path = tmp_path / "a0_selected.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def a2_data(tmp_path):
    """Create a temporary A2 consumable data JSON file."""
    data = {
        "products": [
            {
                "product_name": "로보락 Q Revo S",
                "annual_consumable_cost": 60000,
                "consumables": [
                    {
                        "name": "필터",
                        "unit_price": 15000,
                        "replacement_cycle_months": 6,
                        "changes_per_year": 2,
                        "annual_cost": 30000,
                        "compatible_available": True,
                        "compatible_price": 8000,
                    },
                    {
                        "name": "사이드브러시",
                        "unit_price": 10000,
                        "replacement_cycle_months": 6,
                        "changes_per_year": 2,
                        "annual_cost": 20000,
                        "compatible_available": False,
                    },
                    {
                        "name": "먼지봉투",
                        "unit_price": 5000,
                        "replacement_cycle_months": 6,
                        "changes_per_year": 2,
                        "annual_cost": 10000,
                        "compatible_available": False,
                    },
                ],
                "notes": "호환필터 사용 시 50% 절감 가능",
            },
            {
                "product_name": "삼성 비스포크 제트봇 AI",
                "annual_consumable_cost": 45000,
                "consumables": [
                    {
                        "name": "필터",
                        "unit_price": 25000,
                        "replacement_cycle_months": 12,
                        "changes_per_year": 1,
                        "annual_cost": 25000,
                        "compatible_available": False,
                    },
                    {
                        "name": "사이드브러시",
                        "unit_price": 10000,
                        "replacement_cycle_months": 6,
                        "changes_per_year": 2,
                        "annual_cost": 20000,
                        "compatible_available": False,
                    },
                ],
                "notes": "",
            },
        ]
    }
    path = tmp_path / "a2_consumable.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def a5_data(tmp_path):
    """Create a temporary A5 review insights JSON file."""
    data = {
        "total_reviews_analyzed": 120,
        "review_sources": ["네이버 카페", "쿠팡 리뷰"],
        "products": [
            {
                "product_name": "로보락 Q Revo S",
                "reviews_collected": 80,
                "purchase_motivations": ["가성비", "물걸레 기능"],
                "sentiment_keywords": {"positive": ["조용", "깔끔"], "negative": ["앱 불편"]},
                "hidden_differentiator": "자동 물걸레 세척",
                "as_reputation": "positive",
                "as_reputation_summary": "AS 응대 빠르고 만족도 높음",
            },
        ],
    }
    path = tmp_path / "a5_reviews.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


class TestTCOCalculator:
    """Test consumable-based TCO calculation logic."""

    def test_calculate_from_files_basic(self, a0_data, a2_data):
        """Test basic TCO calculation from A0+A2 files."""
        results = TCOCalculator.calculate_from_files(a0_data, a2_data)

        assert len(results) == 2

        # Product 1: 로보락
        roborock = results[0]
        assert roborock["name"] == "로보락 Q Revo S"
        assert roborock["brand"] == "로보락"

        tco = roborock["tco"]
        assert tco["purchase_price"] == 899000
        assert tco["annual_consumable_cost"] == 60000
        assert tco["consumable_cost_total"] == 180000  # 60000 * 3
        assert tco["real_cost_total"] == 1079000  # 899000 + 180000

    def test_calculate_formula_consistency(self, a0_data, a2_data):
        """Verify TCO formula: real_cost = purchase + consumable_total."""
        results = TCOCalculator.calculate_from_files(a0_data, a2_data)

        for r in results:
            tco = r["tco"]
            tco_years = tco.get("tco_years", 3)
            assert tco["consumable_cost_total"] == tco["annual_consumable_cost"] * tco_years
            assert tco["real_cost_total"] == tco["purchase_price"] + tco["consumable_cost_total"]

    def test_calculate_consumable_breakdown(self, a0_data, a2_data):
        """Verify consumable breakdown is included."""
        results = TCOCalculator.calculate_from_files(a0_data, a2_data)

        roborock = results[0]
        breakdown = roborock["tco"]["consumable_breakdown"]
        assert len(breakdown) == 3
        assert breakdown[0]["name"] == "필터"
        assert breakdown[0]["annual_cost"] == 30000

    def test_calculate_no_consumables(self, tmp_path, a0_data):
        """Product with no consumable data should have 0 consumable cost."""
        a2_empty = tmp_path / "a2_empty.json"
        a2_empty.write_text(json.dumps({"products": []}, ensure_ascii=False), encoding="utf-8")

        results = TCOCalculator.calculate_from_files(a0_data, a2_empty)

        for r in results:
            tco = r["tco"]
            assert tco["annual_consumable_cost"] == 0
            assert tco["consumable_cost_total"] == 0
            assert tco["real_cost_total"] == tco["purchase_price"]

    def test_calculate_2yr_tco(self, a0_data, a2_data):
        """Test TCO calculation with tco_years=2."""
        results = TCOCalculator.calculate_from_files(a0_data, a2_data, tco_years=2)

        roborock = results[0]
        tco = roborock["tco"]
        assert tco["tco_years"] == 2
        assert tco["consumable_cost_total"] == 60000 * 2  # 120000
        assert tco["real_cost_total"] == 899000 + 120000  # 1019000


class TestTCOExporter:
    """Test JSON export for Part B consumption."""

    def test_export_from_files_basic(self, a0_data, a2_data, tmp_path):
        """Test export creates valid output."""
        output_path = tmp_path / "tco_export.json"
        export = TCOExporter.export_from_files(
            category="로봇청소기",
            a0_path=a0_data,
            a2_path=a2_data,
            output_path=output_path,
        )

        assert export["category"] == "로봇청소기"
        assert export["selected_tier"] == "가성비"
        assert len(export["products"]) == 2

        # Verify file was written
        assert output_path.exists()
        with open(output_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["category"] == "로봇청소기"

    def test_export_product_fields(self, a0_data, a2_data, tmp_path):
        """Test per-product export fields."""
        output_path = tmp_path / "export.json"
        export = TCOExporter.export_from_files(
            category="로봇청소기",
            a0_path=a0_data,
            a2_path=a2_data,
            output_path=output_path,
        )

        product = export["products"][0]
        assert "product_id" in product
        assert "name" in product
        assert "brand" in product
        assert "tco" in product

        tco = product["tco"]
        assert "purchase_price" in tco
        assert "annual_consumable_cost" in tco
        assert "consumable_cost_total" in tco
        assert "real_cost_total" in tco

    def test_export_with_a5_data(self, a0_data, a2_data, a5_data, tmp_path):
        """Test export enriched with A5 review data."""
        output_path = tmp_path / "export.json"
        export = TCOExporter.export_from_files(
            category="로봇청소기",
            a0_path=a0_data,
            a2_path=a2_data,
            a5_path=a5_data,
            output_path=output_path,
        )

        roborock = export["products"][0]
        assert "review_insights" in roborock
        assert roborock["review_insights"]["reviews_collected"] == 80
        assert roborock["as_reputation"] == "positive"

    def test_export_summary(self, a0_data, a2_data, tmp_path):
        """Test export summary section."""
        output_path = tmp_path / "export.json"
        export = TCOExporter.export_from_files(
            category="로봇청소기",
            a0_path=a0_data,
            a2_path=a2_data,
            output_path=output_path,
        )

        summary = export["summary"]
        assert "cheapest" in summary
        assert "most_expensive" in summary
        assert "cost_difference" in summary

    def test_export_credibility(self, a0_data, a2_data, a5_data, tmp_path):
        """Test credibility metadata in export."""
        output_path = tmp_path / "export.json"
        export = TCOExporter.export_from_files(
            category="로봇청소기",
            a0_path=a0_data,
            a2_path=a2_data,
            a5_path=a5_data,
            output_path=output_path,
        )

        cred = export["credibility"]
        assert cred["product_count"] == 2
        assert cred["total_reviews_analyzed"] == 120


class TestTCOFormula:
    """Test the core TCO formula independently."""

    def test_formula_basic(self):
        """Real Cost (3yr) = purchase_price + (annual_consumable_cost * 3)"""
        purchase = 899_000
        annual_consumable = 60_000

        consumable_3yr = annual_consumable * 3
        real_cost = purchase + consumable_3yr

        assert consumable_3yr == 180_000
        assert real_cost == 1_079_000

    def test_formula_no_consumables(self):
        """Zero consumable cost means real_cost == purchase_price."""
        purchase = 1_000_000
        annual_consumable = 0

        real_cost = purchase + (annual_consumable * 3)
        assert real_cost == 1_000_000


class TestTCOVerification:
    """Test TCO verification logic."""

    def test_verification_passes(self, a0_data, a2_data, tmp_path):
        """Verification should pass for correctly calculated TCO."""
        output_path = tmp_path / "export.json"
        export = TCOExporter.export_from_files(
            category="로봇청소기",
            a0_path=a0_data,
            a2_path=a2_data,
            output_path=output_path,
        )

        # No verification errors expected
        verification = export.get("_verification", {})
        assert not verification.get("errors", [])
