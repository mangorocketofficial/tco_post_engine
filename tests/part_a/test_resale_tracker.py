"""Tests for the resale tracker module."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.part_a.resale_tracker.models import ResaleRecord, ResaleCurve
from src.part_a.resale_tracker.base_scraper import BaseResaleScraper
from src.part_a.resale_tracker.danggeun_scraper import DanggeunScraper
from src.part_a.resale_tracker.bunjang_scraper import BunjangScraper


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class TestResaleRecord:
    """Test ResaleRecord model."""

    def test_create_record(self):
        record = ResaleRecord(
            product_name="로보락 Q Revo S",
            platform="danggeun",
            sale_price=1200000,
            listing_date=date(2026, 2, 1),
            condition="like_new",
        )
        assert record.sale_price == 1200000
        assert record.platform == "danggeun"
        assert record.condition == "like_new"

    def test_to_dict(self):
        record = ResaleRecord(
            product_name="Test",
            platform="danggeun",
            sale_price=500000,
            listing_date=date(2026, 1, 15),
            months_since_release=12.0,
            condition="used",
        )
        d = record.to_dict()
        assert d["sale_price"] == 500000
        assert d["platform"] == "danggeun"
        assert d["listing_date"] == "2026-01-15"
        assert d["months_since_release"] == 12.0


class TestResaleCurve:
    """Test ResaleCurve model."""

    def test_to_dict(self):
        curve = ResaleCurve(
            product_name="Test",
            original_price=1500000,
            retention_1yr=75.0,
            retention_2yr=55.0,
            retention_3yr_plus=35.0,
            median_price_1yr=1125000,
            median_price_2yr=825000,
            median_price_3yr_plus=525000,
        )
        d = curve.to_dict()
        assert d["original_price"] == 1500000
        assert d["resale_curve"]["1yr"] == 75.0
        assert d["resale_curve"]["2yr"] == 55.0
        assert d["resale_curve"]["3yr_plus"] == 35.0
        assert d["median_prices"]["1yr"] == 1125000
        assert d["median_prices"]["3yr_plus"] == 525000


# === Shared utility tests (methods on BaseResaleScraper) ===


class TestBaseScraperUtilities:
    """Test shared parsing utilities from BaseResaleScraper."""

    def test_parse_price_basic(self):
        assert BaseResaleScraper._parse_price("1,200,000원") == 1200000
        assert BaseResaleScraper._parse_price("850,000원") == 850000
        assert BaseResaleScraper._parse_price("0") == 0

    def test_parse_price_man_won(self):
        """Test parsing '만원' notation."""
        assert BaseResaleScraper._parse_price("120만원") == 1200000
        assert BaseResaleScraper._parse_price("150만원") == 1500000
        assert BaseResaleScraper._parse_price("85만원") == 850000

    def test_parse_relative_date(self):
        today = date.today()

        # Minutes/hours ago → today
        assert BaseResaleScraper._parse_relative_date("30분 전") == today
        assert BaseResaleScraper._parse_relative_date("2시간 전") == today

        # Days ago
        result = BaseResaleScraper._parse_relative_date("3일 전")
        assert result == today - timedelta(days=3)

        # Weeks ago
        result = BaseResaleScraper._parse_relative_date("2주 전")
        assert result == today - timedelta(weeks=2)

        # Months ago
        result = BaseResaleScraper._parse_relative_date("1달 전")
        assert result == today - timedelta(days=30)

        result = BaseResaleScraper._parse_relative_date("3개월 전")
        assert result == today - timedelta(days=90)

        # Empty / invalid
        assert BaseResaleScraper._parse_relative_date("") is None
        assert BaseResaleScraper._parse_relative_date("어제") is None

    def test_classify_condition(self):
        scraper = DanggeunScraper.__new__(DanggeunScraper)
        assert scraper._classify_condition("미개봉 새상품") == "new"
        assert scraper._classify_condition("거의 새것 상태 좋음") == "like_new"
        assert scraper._classify_condition("S급 깨끗") == "like_new"
        assert scraper._classify_condition("중고 사용감 약간") == "used"
        assert scraper._classify_condition("하자 있음") == "worn"
        assert scraper._classify_condition("판매합니다") == "used"  # default


# === Danggeun Scraper tests ===


class TestDanggeunScraper:
    """Test Danggeun scraper with Remix JSON fixture."""

    def test_parse_search_results(self, temp_db):
        """Test parsing Danggeun search results from Remix JSON fixture."""
        html = (FIXTURES_DIR / "danggeun_search.html").read_text(encoding="utf-8")

        scraper = DanggeunScraper(temp_db)
        mock_response = MagicMock()
        mock_response.text = html
        scraper._client.get = MagicMock(return_value=mock_response)

        records = scraper.search_sold_items("로보락 Q Revo S")

        # Should find 4 sold items (listing-4 is "Ongoing", not sold)
        assert len(records) == 4

        # First sold item (Closed, 거의새것)
        assert records[0].product_name == "로보락 Q Revo S 풀세트 거의새것"
        assert records[0].sale_price == 1200000
        assert records[0].condition == "like_new"
        assert records[0].platform == "danggeun"
        assert records[0].listing_date == date(2026, 2, 5)

        # Second sold item (Closed, 중고)
        assert records[1].product_name == "로보락 Q Revo S 본체만 중고"
        assert records[1].sale_price == 850000
        assert records[1].condition == "used"

        # Third sold item (Closed, 미개봉)
        assert records[2].product_name == "로보락 Q Revo S 미개봉"
        assert records[2].sale_price == 1350000
        assert records[2].condition == "new"

        # Fourth sold item (Closed, 사용감)
        assert records[3].product_name == "로보락 Q Revo S 사용감 있음"
        assert records[3].sale_price == 700000
        assert records[3].condition == "worn"

    def test_extract_remix_listings_missing_context(self):
        """Returns empty list when __remixContext is not found."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)
        result = scraper._extract_remix_listings("<html><body>No context</body></html>")
        assert result == []

    def test_extract_remix_listings_invalid_json(self):
        """Returns empty list when JSON is invalid."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)
        html = '<script>window.__remixContext = {invalid json};</script>'
        result = scraper._extract_remix_listings(html)
        assert result == []

    def test_parse_danggeun_date_iso(self):
        """Test ISO date parsing."""
        result = DanggeunScraper._parse_danggeun_date("2026-01-15T09:30:00Z")
        assert result == date(2026, 1, 15)

    def test_parse_danggeun_date_none(self):
        """Test None input."""
        assert DanggeunScraper._parse_danggeun_date(None) is None
        assert DanggeunScraper._parse_danggeun_date("") is None

    def test_parse_remix_listing_skips_ongoing(self):
        """Listings with status 'Ongoing' should be skipped."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)
        item = {
            "title": "Test Product",
            "price": "1000000.0",
            "status": "Ongoing",
            "createdAt": "2026-02-01T10:00:00Z",
        }
        result = scraper._parse_remix_listing(item)
        assert result is None

    def test_parse_remix_listing_accepts_closed(self):
        """Listings with status 'Closed' should be parsed."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)
        item = {
            "id": "12345",
            "title": "Test Product 중고",
            "price": "500000.0",
            "status": "Closed",
            "createdAt": "2026-01-20T14:00:00Z",
            "content": "잘 사용했습니다",
        }
        result = scraper._parse_remix_listing(item)
        assert result is not None
        assert result.sale_price == 500000
        assert result.platform == "danggeun"
        assert result.product_id == "12345"


# === Retention Curve tests (shared via BaseResaleScraper) ===


class TestRetentionCurve:
    """Test retention curve calculation (shared across platforms)."""

    def test_retention_curve_calculation(self):
        """Test price retention curve with yearly buckets and median."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)

        records = [
            # 1yr bucket (≤18mo)
            ResaleRecord("Product", "danggeun", 1200000, months_since_release=3.0),
            ResaleRecord("Product", "danggeun", 1100000, months_since_release=6.0),
            ResaleRecord("Product", "danggeun", 900000, months_since_release=12.0),
            # 2yr bucket (18-30mo)
            ResaleRecord("Product", "danggeun", 700000, months_since_release=20.0),
            ResaleRecord("Product", "danggeun", 600000, months_since_release=24.0),
            ResaleRecord("Product", "danggeun", 550000, months_since_release=28.0),
            # 3yr_plus bucket (>30mo)
            ResaleRecord("Product", "danggeun", 400000, months_since_release=36.0),
            ResaleRecord("Product", "danggeun", 350000, months_since_release=42.0),
        ]

        curve = scraper.calculate_retention_curve(records, original_price=1500000)

        # 1yr: median(1200000, 1100000, 900000) = 1100000 → 73.3%
        assert curve.retention_1yr == pytest.approx(73.3, abs=0.1)
        assert curve.median_price_1yr == 1100000
        # 2yr: median(700000, 600000, 550000) = 600000 → 40.0%
        assert curve.retention_2yr == pytest.approx(40.0, abs=0.1)
        assert curve.median_price_2yr == 600000
        # 3yr+: median(400000, 350000) = 375000 → 25.0%
        assert curve.retention_3yr_plus == pytest.approx(25.0, abs=0.1)
        assert curve.median_price_3yr_plus == 375000

        assert curve.sample_counts == {"1yr": 3, "2yr": 3, "3yr_plus": 2}

    def test_retention_curve_empty_buckets(self):
        """Test retention curve when some buckets are empty."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)

        records = [
            ResaleRecord("Product", "danggeun", 1000000, months_since_release=5.0),
        ]

        curve = scraper.calculate_retention_curve(records, original_price=1500000)

        assert curve.retention_1yr == pytest.approx(66.7, abs=0.1)
        assert curve.median_price_1yr == 1000000
        assert curve.retention_2yr is None
        assert curve.retention_3yr_plus is None

    def test_retention_curve_with_release_date(self):
        """Test retention curve using release_date instead of months_since_release."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)

        release = date(2025, 6, 1)
        records = [
            ResaleRecord("Product", "danggeun", 1000000, listing_date=date(2025, 12, 1)),
            ResaleRecord("Product", "danggeun", 800000, listing_date=date(2026, 6, 1)),
            ResaleRecord("Product", "danggeun", 500000, listing_date=date(2027, 12, 1)),
        ]

        curve = scraper.calculate_retention_curve(
            records, original_price=1500000, release_date=release
        )

        # First two: ~6mo and ~12mo → both in 1yr bucket (≤18mo)
        assert curve.retention_1yr is not None
        # Third: ~30mo → 2yr bucket (18-30mo)
        assert curve.retention_2yr is not None

    def test_retention_curve_excludes_worn_items(self):
        """Test that worn/broken items are excluded from retention curve."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)

        records = [
            ResaleRecord("Product", "danggeun", 1000000, months_since_release=6.0, condition="used"),
            ResaleRecord("Product", "danggeun", 900000, months_since_release=8.0, condition="like_new"),
            # This worn item should be excluded
            ResaleRecord("Product", "danggeun", 300000, months_since_release=7.0, condition="worn"),
        ]

        curve = scraper.calculate_retention_curve(records, original_price=1500000)

        # median(1000000, 900000) = 950000 → 63.3% (worn item excluded)
        assert curve.retention_1yr == pytest.approx(63.3, abs=0.1)
        assert curve.median_price_1yr == 950000
        assert curve.sample_counts["1yr"] == 2  # worn item not counted

    def test_retention_curve_zero_price_raises(self):
        """Test that original_price=0 raises ValueError."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)
        with pytest.raises(ValueError):
            scraper.calculate_retention_curve([], original_price=0)


# === Database tests ===


class TestDatabaseIntegration:
    """Test database save operations."""

    def test_save_records_to_db(self, temp_db):
        """Test saving resale records to database."""
        scraper = DanggeunScraper(temp_db)

        records = [
            ResaleRecord(
                product_name="테스트 제품",
                platform="danggeun",
                sale_price=1000000,
                listing_date=date(2026, 2, 1),
                condition="used",
            ),
            ResaleRecord(
                product_name="테스트 제품",
                platform="danggeun",
                sale_price=950000,
                listing_date=date(2026, 1, 20),
                condition="like_new",
            ),
        ]

        inserted = scraper.save_records_to_db(records)
        assert inserted == 2

        from src.part_a.database.connection import get_connection

        conn = get_connection(temp_db)
        try:
            rows = conn.execute(
                "SELECT COUNT(*) as cnt FROM resale_transactions"
            ).fetchone()
            assert rows["cnt"] == 2

            products = conn.execute(
                "SELECT COUNT(*) as cnt FROM products"
            ).fetchone()
            assert products["cnt"] == 1  # Same product
        finally:
            conn.close()

    def test_save_bunjang_records_to_db(self, temp_db):
        """Test saving Bunjang records preserves platform field."""
        scraper = BunjangScraper(temp_db)

        records = [
            ResaleRecord(
                product_name="테스트 제품",
                platform="bunjang",
                sale_price=1100000,
                listing_date=date(2026, 2, 4),
                condition="like_new",
            ),
        ]

        inserted = scraper.save_records_to_db(records)
        assert inserted == 1

        from src.part_a.database.connection import get_connection

        conn = get_connection(temp_db)
        try:
            row = conn.execute(
                "SELECT platform FROM resale_transactions"
            ).fetchone()
            assert row["platform"] == "bunjang"
        finally:
            conn.close()


# === Bunjang Scraper tests ===


class TestBunjangScraper:
    """Test Bunjang scraper with JSON API fixture."""

    def test_parse_search_results(self, temp_db):
        """Test parsing Bunjang API response from fixture."""
        fixture_path = FIXTURES_DIR / "bunjang_search.json"
        fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))

        scraper = BunjangScraper(temp_db)
        mock_response = MagicMock()
        mock_response.json.return_value = fixture_data
        scraper._client.get = MagicMock(return_value=mock_response)

        records = scraper.search_sold_items("로보락 Q Revo S")

        # All 5 items should be collected (both sold and active)
        assert len(records) == 5

        # First item (sold)
        assert records[0].product_name == "로보락 Q Revo S 풀세트 거의새것"
        assert records[0].sale_price == 1150000
        assert records[0].condition == "like_new"
        assert records[0].platform == "bunjang"
        assert records[0].product_id == "300001"

        # Second item (sold, 중고)
        assert records[1].sale_price == 800000
        assert records[1].condition == "used"

        # Third item (sold, 미개봉)
        assert records[2].sale_price == 1400000
        assert records[2].condition == "new"

        # Fifth item (active, 하자)
        assert records[4].condition == "worn"

    def test_parse_bunjang_date_unix(self):
        """Test parsing Unix timestamp."""
        result = BunjangScraper._parse_bunjang_date(1738684800)
        assert result is not None
        assert isinstance(result, date)

    def test_parse_bunjang_date_string(self):
        """Test parsing string Unix timestamp."""
        result = BunjangScraper._parse_bunjang_date("1738684800")
        assert result is not None
        assert isinstance(result, date)

    def test_parse_bunjang_date_none(self):
        """Test None returns None."""
        assert BunjangScraper._parse_bunjang_date(None) is None

    def test_skips_zero_price(self, temp_db):
        """Items with zero price should be skipped."""
        scraper = BunjangScraper(temp_db)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "list": [
                {"pid": "1", "name": "Test", "price": "0", "status": "2", "update_time": 1738684800},
            ]
        }
        scraper._client.get = MagicMock(return_value=mock_response)

        records = scraper.search_sold_items("test")
        assert len(records) == 0


# === Multi-platform aggregation tests ===


class TestMultiPlatformAggregation:
    """Test combining records from multiple platforms."""

    def test_retention_curve_with_mixed_platforms(self):
        """Retention curve should work with records from different platforms."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)

        records = [
            # Danggeun records
            ResaleRecord("Product", "danggeun", 1200000, months_since_release=6.0),
            ResaleRecord("Product", "danggeun", 900000, months_since_release=12.0),
            # Bunjang records
            ResaleRecord("Product", "bunjang", 1150000, months_since_release=5.0),
            ResaleRecord("Product", "bunjang", 850000, months_since_release=10.0),
        ]

        curve = scraper.calculate_retention_curve(records, original_price=1500000)

        # All 4 records in 1yr bucket
        assert curve.sample_counts["1yr"] == 4
        assert curve.retention_1yr is not None
        # median(1200000, 1150000, 900000, 850000) = 1025000
        assert curve.median_price_1yr == 1025000

    def test_empty_records_list(self):
        """Retention curve with no records should return None for all buckets."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)

        curve = scraper.calculate_retention_curve(
            [],
            original_price=1500000,
        )

        assert curve.retention_1yr is None
        assert curve.retention_2yr is None
        assert curve.retention_3yr_plus is None
