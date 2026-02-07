"""Tests for the resale tracker module."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.part_a.resale_tracker.models import ResaleRecord, ResaleCurve
from src.part_a.resale_tracker.danggeun_scraper import DanggeunScraper


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
            retention_6mo=80.0,
            retention_12mo=65.0,
            retention_18mo=55.0,
            retention_24mo=45.0,
        )
        d = curve.to_dict()
        assert d["original_price"] == 1500000
        assert d["resale_curve"]["6mo"] == 80.0
        assert d["resale_curve"]["24mo"] == 45.0


class TestDanggeunScraper:
    """Test Danggeun scraper with cached HTML fixtures."""

    def test_parse_price_basic(self):
        assert DanggeunScraper._parse_price("1,200,000원") == 1200000
        assert DanggeunScraper._parse_price("850,000원") == 850000
        assert DanggeunScraper._parse_price("0") == 0

    def test_parse_price_man_won(self):
        """Test parsing '만원' notation."""
        assert DanggeunScraper._parse_price("120만원") == 1200000
        assert DanggeunScraper._parse_price("150만원") == 1500000
        assert DanggeunScraper._parse_price("85만원") == 850000

    def test_parse_relative_date(self):
        today = date.today()

        # Minutes/hours ago → today
        assert DanggeunScraper._parse_relative_date("30분 전") == today
        assert DanggeunScraper._parse_relative_date("2시간 전") == today

        # Days ago
        result = DanggeunScraper._parse_relative_date("3일 전")
        assert result == today - timedelta(days=3)

        # Weeks ago
        result = DanggeunScraper._parse_relative_date("2주 전")
        assert result == today - timedelta(weeks=2)

        # Months ago
        result = DanggeunScraper._parse_relative_date("1달 전")
        assert result == today - timedelta(days=30)

        result = DanggeunScraper._parse_relative_date("3개월 전")
        assert result == today - timedelta(days=90)

        # Empty / invalid
        assert DanggeunScraper._parse_relative_date("") is None
        assert DanggeunScraper._parse_relative_date("어제") is None

    def test_classify_condition(self):
        scraper = DanggeunScraper.__new__(DanggeunScraper)
        assert scraper._classify_condition("미개봉 새상품") == "new"
        assert scraper._classify_condition("거의 새것 상태 좋음") == "like_new"
        assert scraper._classify_condition("S급 깨끗") == "like_new"
        assert scraper._classify_condition("중고 사용감 약간") == "used"
        assert scraper._classify_condition("하자 있음") == "worn"
        assert scraper._classify_condition("판매합니다") == "used"  # default

    def test_parse_search_results(self, temp_db):
        """Test parsing Danggeun search results from cached HTML."""
        html = (FIXTURES_DIR / "danggeun_search.html").read_text(encoding="utf-8")

        scraper = DanggeunScraper(temp_db)
        mock_response = MagicMock()
        mock_response.text = html
        scraper._client.get = MagicMock(return_value=mock_response)

        records = scraper.search_sold_items("로보락 Q Revo S")

        # Should find 4 sold items (listing-4 has no sold indicator)
        assert len(records) == 4

        # First sold item (거래완료)
        assert records[0].product_name == "로보락 Q Revo S 풀세트 거의새것"
        assert records[0].sale_price == 1200000
        assert records[0].condition == "like_new"
        assert records[0].platform == "danggeun"

        # Second sold item (거래완료)
        assert records[1].product_name == "로보락 Q Revo S 본체만 중고"
        assert records[1].sale_price == 850000
        assert records[1].condition == "used"

        # Third sold item (거래완료, 미개봉)
        assert records[2].product_name == "로보락 Q Revo S 미개봉"
        assert records[2].sale_price == 1350000
        assert records[2].condition == "new"

        # Fourth sold item (판매완료)
        assert records[3].product_name == "로보락 Q Revo S 사용감 있음"
        assert records[3].sale_price == 700000
        assert records[3].condition == "worn"

    def test_retention_curve_calculation(self):
        """Test price retention curve calculation."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)

        records = [
            # 6mo bucket (months 0-9)
            ResaleRecord("Product", "danggeun", 1200000, months_since_release=3.0),
            ResaleRecord("Product", "danggeun", 1100000, months_since_release=6.0),
            # 12mo bucket (months 9-15)
            ResaleRecord("Product", "danggeun", 900000, months_since_release=12.0),
            ResaleRecord("Product", "danggeun", 850000, months_since_release=11.0),
            # 18mo bucket (months 15-21)
            ResaleRecord("Product", "danggeun", 700000, months_since_release=18.0),
            # 24mo bucket (months 21-30)
            ResaleRecord("Product", "danggeun", 600000, months_since_release=24.0),
            ResaleRecord("Product", "danggeun", 550000, months_since_release=25.0),
        ]

        curve = scraper.calculate_retention_curve(records, original_price=1500000)

        # 6mo: avg(1200000, 1100000) = 1150000 → 76.7%
        assert curve.retention_6mo == pytest.approx(76.7, abs=0.1)
        # 12mo: avg(900000, 850000) = 875000 → 58.3%
        assert curve.retention_12mo == pytest.approx(58.3, abs=0.1)
        # 18mo: 700000 → 46.7%
        assert curve.retention_18mo == pytest.approx(46.7, abs=0.1)
        # 24mo: avg(600000, 550000) = 575000 → 38.3%
        assert curve.retention_24mo == pytest.approx(38.3, abs=0.1)

        assert curve.sample_counts == {"6mo": 2, "12mo": 2, "18mo": 1, "24mo": 2}

    def test_retention_curve_empty_buckets(self):
        """Test retention curve when some buckets are empty."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)

        records = [
            ResaleRecord("Product", "danggeun", 1000000, months_since_release=5.0),
        ]

        curve = scraper.calculate_retention_curve(records, original_price=1500000)

        assert curve.retention_6mo == pytest.approx(66.7, abs=0.1)
        assert curve.retention_12mo is None
        assert curve.retention_18mo is None
        assert curve.retention_24mo is None

    def test_retention_curve_with_release_date(self):
        """Test retention curve using release_date instead of months_since_release."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)

        release = date(2025, 6, 1)
        records = [
            ResaleRecord("Product", "danggeun", 1000000, listing_date=date(2025, 12, 1)),
            ResaleRecord("Product", "danggeun", 800000, listing_date=date(2026, 6, 1)),
        ]

        curve = scraper.calculate_retention_curve(
            records, original_price=1500000, release_date=release
        )

        # First: ~6 months → 6mo bucket
        assert curve.retention_6mo is not None
        # Second: ~12 months → 12mo bucket
        assert curve.retention_12mo is not None

    def test_retention_curve_zero_price_raises(self):
        """Test that original_price=0 raises ValueError."""
        scraper = DanggeunScraper.__new__(DanggeunScraper)
        with pytest.raises(ValueError):
            scraper.calculate_retention_curve([], original_price=0)

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
