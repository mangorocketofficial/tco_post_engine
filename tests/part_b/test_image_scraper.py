"""Tests for Coupang product image scraper (helper functions + output format)."""

import json
from pathlib import Path

import pytest

from src.part_b.cta_manager.image_scraper import (
    CoupangImageScraper,
    _upgrade_image_url,
    load_a0_products,
    load_cta_products,
    save_image_results,
)


# --- URL upgrade tests ---


class TestUpgradeImageUrl:
    """Test thumbnail URL → high-res URL conversion."""

    def test_replace_small_thumbnail(self):
        url = "https://thumbnail6.coupangcdn.com/thumbnails/remote/230x230ex/image/product.jpg"
        result = _upgrade_image_url(url)
        assert "/500x500ex/" in result
        assert "/230x230ex/" not in result

    def test_replace_medium_thumbnail(self):
        url = "https://thumbnail6.coupangcdn.com/thumbnails/remote/110x110ex/image/product.jpg"
        result = _upgrade_image_url(url)
        assert "/500x500ex/" in result

    def test_already_high_res(self):
        url = "https://thumbnail6.coupangcdn.com/thumbnails/remote/500x500ex/image/product.jpg"
        result = _upgrade_image_url(url)
        assert "/500x500ex/" in result

    def test_no_size_pattern(self):
        """URLs without size pattern should remain unchanged."""
        url = "https://example.com/images/product.jpg"
        result = _upgrade_image_url(url)
        assert result == url


# --- CTA loading tests ---


class TestLoadCtaProducts:
    """Test CTA links JSON loading."""

    def test_load_valid_cta(self, tmp_path):
        data = {
            "category": "로봇청소기",
            "products": [
                {
                    "product_id": "roborock_s9-maxv",
                    "product_name": "로보락 S9 MaxV",
                    "base_url": "https://link.coupang.com/a/abc123",
                    "success": True,
                },
                {
                    "product_id": "dyson_v15",
                    "product_name": "다이슨 V15",
                    "base_url": "https://link.coupang.com/a/def456",
                    "success": True,
                },
            ],
        }
        path = tmp_path / "cta_links.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        category, products = load_cta_products(path)
        assert category == "로봇청소기"
        assert len(products) == 2
        assert products[0]["base_url"] == "https://link.coupang.com/a/abc123"

    def test_load_empty_products(self, tmp_path):
        data = {"category": "test", "products": []}
        path = tmp_path / "empty_cta.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        category, products = load_cta_products(path)
        assert category == "test"
        assert len(products) == 0

    def test_load_missing_category(self, tmp_path):
        data = {"products": [{"product_id": "x", "product_name": "X"}]}
        path = tmp_path / "no_cat.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        category, products = load_cta_products(path)
        assert category == "unknown"


# --- A0 loading tests ---


class TestLoadA0Products:
    """Test A0 selected products JSON loading."""

    def test_load_valid_a0(self, tmp_path):
        data = {
            "category": "전기면도기",
            "final_products": [
                {"rank": 1, "name": "제품A", "brand": "브랜드A", "price": 100000},
                {"rank": 2, "name": "제품B", "brand": "브랜드B", "price": 200000},
            ],
        }
        path = tmp_path / "a0_test.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        category, products = load_a0_products(path)
        assert category == "전기면도기"
        assert len(products) == 2

    def test_load_missing_category(self, tmp_path):
        data = {"final_products": [{"name": "X", "brand": "Y"}]}
        path = tmp_path / "a0_nocat.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        category, products = load_a0_products(path)
        assert category == "unknown"


# --- Save results tests ---


class TestSaveImageResults:
    """Test image results JSON saving."""

    def test_save_successful_results(self, tmp_path):
        results = [
            {
                "product_id": "roborock_s9-maxv",
                "product_name": "로보락 S9 MaxV",
                "product_url": "https://www.coupang.com/vp/products/123",
                "images": [
                    {
                        "index": 0,
                        "original_url": "https://coupangcdn.com/img1.jpg",
                        "public_url": "https://x.supabase.co/storage/img1.webp",
                        "width": 800,
                        "height": 800,
                    },
                    {
                        "index": 1,
                        "original_url": "https://coupangcdn.com/img2.jpg",
                        "public_url": "https://x.supabase.co/storage/img2.webp",
                        "width": 800,
                        "height": 600,
                    },
                ],
                "image_count": 2,
                "success": True,
            }
        ]

        output_path = tmp_path / "product_images.json"
        save_image_results(results, output_path, "로봇청소기")

        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))

        assert data["category"] == "로봇청소기"
        assert data["source"] == "coupang_image_scraper"
        assert "generated_at" in data
        assert len(data["products"]) == 1
        assert data["products"][0]["image_count"] == 2

    def test_save_creates_parent_dirs(self, tmp_path):
        output_path = tmp_path / "nested" / "dir" / "images.json"
        save_image_results([], output_path, "test")
        assert output_path.exists()

    def test_save_failed_results(self, tmp_path):
        results = [
            {
                "product_id": "failed",
                "product_name": "Failed Product",
                "product_url": "",
                "images": [],
                "image_count": 0,
                "success": False,
            }
        ]

        output_path = tmp_path / "failed_images.json"
        save_image_results(results, output_path, "test")

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(data["products"]) == 1
        assert data["products"][0]["success"] is False

    def test_save_mixed_results(self, tmp_path):
        results = [
            {"product_id": "a", "product_name": "A", "product_url": "url",
             "images": [{"index": 0, "original_url": "x", "public_url": "y", "width": 100, "height": 100}],
             "image_count": 1, "success": True},
            {"product_id": "b", "product_name": "B", "product_url": "",
             "images": [], "image_count": 0, "success": False},
        ]

        output_path = tmp_path / "mixed.json"
        save_image_results(results, output_path, "mixed")

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(data["products"]) == 2


# --- Scraper init tests ---


class TestCoupangImageScraperInit:
    """Test scraper initialization (no browser needed)."""

    def test_default_headless_false(self):
        scraper = CoupangImageScraper()
        assert scraper.headless is False

    def test_headless_true(self):
        scraper = CoupangImageScraper(headless=True)
        assert scraper.headless is True

    def test_no_credentials_needed(self):
        """Image scraper does NOT require Coupang Partners credentials."""
        scraper = CoupangImageScraper()
        assert scraper._page is None
        assert scraper._context is None
