"""Tests for the price tracker module."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.part_a.price_tracker.models import PriceRecord, ProductPriceSummary
from src.part_a.price_tracker.danawa_scraper import DanawaScraper


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class TestPriceRecord:
    """Test PriceRecord model."""

    def test_create_record(self):
        record = PriceRecord(
            product_name="로보락 Q Revo S",
            price=1490000,
            source="danawa",
            date=date(2026, 2, 7),
        )
        assert record.product_name == "로보락 Q Revo S"
        assert record.price == 1490000
        assert record.source == "danawa"
        assert record.is_sale is False

    def test_to_dict(self):
        record = PriceRecord(
            product_name="Test",
            price=100000,
            source="danawa",
            date=date(2026, 1, 15),
            is_sale=True,
        )
        d = record.to_dict()
        assert d["date"] == "2026-01-15"
        assert d["price"] == 100000
        assert d["source"] == "danawa"
        assert d["is_sale"] is True


class TestProductPriceSummary:
    """Test ProductPriceSummary model."""

    def test_summary(self):
        summary = ProductPriceSummary(
            product_name="Test Product",
            current_price=1500000,
            lowest_price=1200000,
            avg_price_30d=1400000,
        )
        d = summary.to_dict()
        assert d["current_price"] == 1500000
        assert d["lowest_price"] == 1200000
        assert d["avg_price_30d"] == 1400000


class TestDanawaScraper:
    """Test Danawa scraper with cached HTML fixtures."""

    def test_parse_price_basic(self):
        assert DanawaScraper._parse_price("1,490,000원") == 1490000
        assert DanawaScraper._parse_price("990,000원") == 990000
        assert DanawaScraper._parse_price("0") == 0
        assert DanawaScraper._parse_price("") == 0

    def test_parse_price_no_comma(self):
        assert DanawaScraper._parse_price("1490000") == 1490000

    def test_parse_price_with_text(self):
        assert DanawaScraper._parse_price("최저가 1,490,000원~") == 1490000

    def test_parse_date(self):
        assert DanawaScraper._parse_date("2026-02-07") == date(2026, 2, 7)
        assert DanawaScraper._parse_date("2026.02.07") == date(2026, 2, 7)
        assert DanawaScraper._parse_date("20260207") == date(2026, 2, 7)
        assert DanawaScraper._parse_date("invalid") is None

    def test_parse_search_results(self, temp_db):
        """Test parsing Danawa search results from cached HTML."""
        html = (FIXTURES_DIR / "danawa_search.html").read_text(encoding="utf-8")

        scraper = DanawaScraper(temp_db)

        # Mock the HTTP client to return our fixture
        mock_response = MagicMock()
        mock_response.text = html
        scraper._client.get = MagicMock(return_value=mock_response)

        products = scraper.search_products("로봇청소기")

        assert len(products) == 3
        assert products[0]["product_code"] == "12345678"
        assert products[0]["name"] == "로보락 Q Revo S 로봇청소기"
        assert products[0]["brand"] == "로보락"
        assert products[0]["price"] == 1490000

        assert products[1]["product_code"] == "87654321"
        assert products[1]["price"] == 1290000

        assert products[2]["product_code"] == "11112222"
        assert products[2]["price"] == 1890000

    def test_parse_product_prices(self, temp_db):
        """Test parsing product price listings from cached HTML."""
        html = (FIXTURES_DIR / "danawa_product.html").read_text(encoding="utf-8")

        scraper = DanawaScraper(temp_db)
        mock_response = MagicMock()
        mock_response.text = html
        scraper._client.get = MagicMock(return_value=mock_response)

        records = scraper.get_product_prices("12345678")

        assert len(records) >= 1
        # All records should be from danawa
        for r in records:
            assert r.source == "danawa"
            assert r.price > 0

    def test_save_prices_to_db(self, temp_db):
        """Test saving price records to database."""
        scraper = DanawaScraper(temp_db)

        records = [
            PriceRecord(
                product_name="Test Product A",
                price=1000000,
                source="danawa",
                date=date(2026, 2, 7),
            ),
            PriceRecord(
                product_name="Test Product A",
                price=990000,
                source="danawa",
                date=date(2026, 2, 6),
            ),
            PriceRecord(
                product_name="Test Product B",
                price=800000,
                source="danawa",
                date=date(2026, 2, 7),
            ),
        ]

        inserted = scraper.save_prices_to_db(records)
        assert inserted == 3

        # Verify in database
        from src.part_a.database.connection import get_connection

        conn = get_connection(temp_db)
        try:
            rows = conn.execute("SELECT COUNT(*) as cnt FROM prices").fetchone()
            assert rows["cnt"] == 3

            products = conn.execute("SELECT COUNT(*) as cnt FROM products").fetchone()
            assert products["cnt"] == 2  # Two unique products
        finally:
            conn.close()

    def test_save_prices_skips_duplicates(self, temp_db):
        """Test that duplicate prices are skipped."""
        scraper = DanawaScraper(temp_db)

        record = PriceRecord(
            product_name="Dup Product",
            price=1000000,
            source="danawa",
            date=date(2026, 2, 7),
        )

        assert scraper.save_prices_to_db([record]) == 1
        # Insert same record again — should be skipped
        assert scraper.save_prices_to_db([record]) == 0

    def test_parse_price_history_json(self, temp_db):
        """Test parsing price history from JSON response."""
        scraper = DanawaScraper(temp_db)

        json_response = '{"priceList": [{"date": "2026-01-01", "price": 1500000}, {"date": "2026-02-01", "price": 1490000}]}'
        records = scraper._parse_price_history_response(json_response, "12345678")

        assert len(records) == 2
        assert records[0].price == 1500000
        assert records[0].date == date(2026, 1, 1)
        assert records[1].price == 1490000
