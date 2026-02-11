"""Tests for Coupang Partners affiliate link scraper."""

import json
from pathlib import Path

import pytest

from src.part_b.cta_manager.link_scraper import (
    CoupangLinkScraper,
    _make_product_id,
    load_a0_products,
    save_results,
)


# --- Helper function tests ---


class TestMakeProductId:
    """Test slug-style product ID generation."""

    def test_brand_and_name(self):
        pid = _make_product_id("로보락 Q Revo S 로봇청소기", "로보락")
        assert pid.startswith("로보락_")
        assert "로보락" in pid

    def test_no_brand(self):
        pid = _make_product_id("필립스 전기면도기 S9000", "")
        assert pid == "필립스-전기면도기-s9000"

    def test_brand_with_spaces(self):
        pid = _make_product_id("삼성 비스포크 제트 AI", "삼성전자")
        assert pid == "삼성전자_삼성-비스포크-제트"

    def test_single_word_name(self):
        pid = _make_product_id("면도기", "브랜드")
        assert "브랜드" in pid


# --- A0 loading tests ---


class TestLoadA0Products:
    """Test A0 JSON loading."""

    def test_load_valid_a0(self, tmp_path):
        a0_data = {
            "category": "전기면도기",
            "final_products": [
                {"rank": 1, "name": "제품A", "brand": "브랜드A", "price": 100000},
                {"rank": 2, "name": "제품B", "brand": "브랜드B", "price": 200000},
                {"rank": 3, "name": "제품C", "brand": "브랜드C", "price": 150000},
            ],
        }
        path = tmp_path / "a0_test.json"
        path.write_text(json.dumps(a0_data, ensure_ascii=False), encoding="utf-8")

        category, products = load_a0_products(path)
        assert category == "전기면도기"
        assert len(products) == 3
        assert products[0]["name"] == "제품A"

    def test_load_empty_products(self, tmp_path):
        a0_data = {"category": "테스트", "final_products": []}
        path = tmp_path / "a0_empty.json"
        path.write_text(json.dumps(a0_data), encoding="utf-8")

        category, products = load_a0_products(path)
        assert category == "테스트"
        assert len(products) == 0

    def test_load_missing_category(self, tmp_path):
        a0_data = {"final_products": [{"name": "X", "brand": "Y"}]}
        path = tmp_path / "a0_nocat.json"
        path.write_text(json.dumps(a0_data), encoding="utf-8")

        category, products = load_a0_products(path)
        assert category == "unknown"
        assert len(products) == 1


# --- Save results tests ---


class TestSaveResults:
    """Test result JSON saving."""

    def test_save_with_successful_links(self, tmp_path):
        results = [
            {
                "product_id": "brand-a_product-a",
                "product_name": "제품A",
                "brand": "BrandA",
                "base_url": "https://link.coupang.com/abc123",
                "platform": "coupang",
                "success": True,
            },
            {
                "product_id": "brand-b_product-b",
                "product_name": "제품B",
                "brand": "BrandB",
                "base_url": "",
                "platform": "coupang",
                "success": False,
            },
        ]

        output_path = tmp_path / "cta_links_test.json"
        save_results(results, output_path, "테스트카테고리")

        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))

        assert data["category"] == "테스트카테고리"
        assert data["source"] == "coupang_partners_scraper"
        assert len(data["products"]) == 2

        # cta_manager_links should only include successful links
        cta_links = data["cta_manager_links"]["links"]
        assert len(cta_links) == 1
        assert cta_links[0]["product_id"] == "brand-a_product-a"
        assert cta_links[0]["base_url"] == "https://link.coupang.com/abc123"

    def test_save_creates_parent_dirs(self, tmp_path):
        output_path = tmp_path / "nested" / "dir" / "output.json"
        save_results([], output_path, "test")
        assert output_path.exists()

    def test_save_all_failed(self, tmp_path):
        results = [
            {
                "product_id": "x",
                "product_name": "X",
                "brand": "",
                "base_url": "",
                "platform": "coupang",
                "success": False,
            },
        ]
        output_path = tmp_path / "all_fail.json"
        save_results(results, output_path, "test")

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(data["cta_manager_links"]["links"]) == 0
        assert len(data["products"]) == 1


# --- CTAManager integration test ---


class TestCTAManagerIntegration:
    """Verify output format is compatible with CTAManager.load_links()."""

    def test_output_loadable_by_cta_manager(self, tmp_path):
        from src.part_b.cta_manager.manager import CTAManager

        results = [
            {
                "product_id": "test-product",
                "product_name": "테스트 제품",
                "brand": "테스트",
                "base_url": "https://link.coupang.com/test123",
                "platform": "coupang",
                "success": True,
            },
        ]

        output_path = tmp_path / "cta_links.json"
        save_results(results, output_path, "test")

        # Extract cta_manager_links portion and save as standalone file
        data = json.loads(output_path.read_text(encoding="utf-8"))
        links_path = tmp_path / "links_only.json"
        links_path.write_text(
            json.dumps(data["cta_manager_links"], ensure_ascii=False),
            encoding="utf-8",
        )

        # CTAManager should be able to load this
        manager = CTAManager(links_path=links_path)
        assert manager.link_count == 1
        link = manager.get_link("test-product")
        assert link is not None
        assert link.base_url == "https://link.coupang.com/test123"


# --- Scraper init tests ---


class TestCoupangLinkScraperInit:
    """Test scraper initialization (no browser needed)."""

    def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.setenv("COUPANG_ID", "")
        monkeypatch.setenv("COUPANG_PASSWORD", "")

        with pytest.raises(ValueError, match="COUPANG_ID"):
            CoupangLinkScraper()

    def test_valid_credentials(self, monkeypatch):
        monkeypatch.setenv("COUPANG_ID", "test@test.com")
        monkeypatch.setenv("COUPANG_PASSWORD", "testpass")

        scraper = CoupangLinkScraper(headless=True)
        assert scraper.coupang_id == "test@test.com"
        assert scraper.headless is True
