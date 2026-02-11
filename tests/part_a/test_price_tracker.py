"""Tests for the price tracker module."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.part_a.price_tracker.models import PriceRecord, ProductPriceSummary
from src.part_a.price_tracker.danawa_scraper import (
    DanawaScraper,
    clean_product_name,
    compute_name_similarity,
    filter_prices_a0_reference,
    filter_prices_iqr,
)


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

    # --- Layer 1: Absolute floor filter ---

    def test_parse_price_floor_filters_sub_1000(self):
        """Layer 1: Values below 1,000 are treated as 0 (parsing artifacts)."""
        assert DanawaScraper._parse_price("3원") == 0
        assert DanawaScraper._parse_price("7원") == 0
        assert DanawaScraper._parse_price("13원") == 0
        assert DanawaScraper._parse_price("787") == 0
        assert DanawaScraper._parse_price("841") == 0
        assert DanawaScraper._parse_price("999") == 0

    def test_parse_price_floor_keeps_valid(self):
        """Layer 1: 1,000+ values pass through."""
        assert DanawaScraper._parse_price("1,000원") == 1000
        assert DanawaScraper._parse_price("26,100원") == 26100
        assert DanawaScraper._parse_price("75,890원") == 75890

    def test_layer1_combined_input(self):
        """Layer 1: Full scenario — only valid prices survive."""
        raw = ["3원", "7원", "13원", "787원", "841원", "75,890원", "79,810원"]
        parsed = [DanawaScraper._parse_price(t) for t in raw]
        valid = [p for p in parsed if p > 0]
        assert valid == [75890, 79810]


class TestFilterPricesIQR:
    """Layer 2: IQR-based outlier removal."""

    def _make_records(self, prices: list[int]) -> list[PriceRecord]:
        return [
            PriceRecord(product_name="test", price=p, source="danawa")
            for p in prices
        ]

    def test_iqr_removes_outlier(self):
        """IQR removes extreme outlier from 6+ records."""
        prices = [75890, 79810, 80620, 80990, 83730, 389000]
        records = self._make_records(prices)
        filtered = filter_prices_iqr(records)
        remaining_prices = [r.price for r in filtered]
        assert 389000 not in remaining_prices
        assert 75890 in remaining_prices

    def test_iqr_skips_when_fewer_than_4(self):
        """IQR is skipped when fewer than 4 records."""
        prices = [75890, 79810]
        records = self._make_records(prices)
        filtered = filter_prices_iqr(records)
        assert len(filtered) == 2

    def test_iqr_keeps_tight_cluster(self):
        """IQR keeps all records when prices are tightly clustered."""
        prices = [80000, 81000, 82000, 83000, 84000]
        records = self._make_records(prices)
        filtered = filter_prices_iqr(records)
        assert len(filtered) == 5

    def test_iqr_empty_list(self):
        filtered = filter_prices_iqr([])
        assert filtered == []


class TestFilterPricesA0Reference:
    """Layer 3: A0 reference price cross-check."""

    def _make_records(self, prices: list[int]) -> list[PriceRecord]:
        return [
            PriceRecord(product_name="test", price=p, source="danawa")
            for p in prices
        ]

    def test_removes_too_high(self):
        """Price > 3× reference is removed."""
        records = self._make_records([26100, 50000, 666440])
        filtered = filter_prices_a0_reference(records, reference_price=26100)
        remaining = [r.price for r in filtered]
        assert 666440 not in remaining
        assert 26100 in remaining
        assert 50000 in remaining

    def test_removes_too_low(self):
        """Price < 0.3× reference is removed."""
        records = self._make_records([2000, 26100, 50000])
        filtered = filter_prices_a0_reference(records, reference_price=26100)
        remaining = [r.price for r in filtered]
        assert 2000 not in remaining

    def test_skips_when_no_reference(self):
        """Layer 3 is skipped when A0 price is 0."""
        records = self._make_records([3000, 26100, 666440])
        filtered = filter_prices_a0_reference(records, reference_price=0)
        assert len(filtered) == 3

    def test_all_layers_combined(self):
        """Full product1 raw data: only prices in reasonable range survive."""
        # Simulate: raw parse → Layer 1 → Layer 2 → Layer 3
        raw_texts = [
            "3원", "7원", "13원", "787원", "841원",
            "26,100원", "25,000원", "27,500원", "28,000원", "24,500원",
            "666,440원", "700,120원",
        ]
        # Layer 1 (via _parse_price)
        parsed = [DanawaScraper._parse_price(t) for t in raw_texts]
        records = [
            PriceRecord(product_name="test", price=p, source="danawa")
            for p in parsed if p > 0
        ]
        # Layer 2
        records = filter_prices_iqr(records)
        # Layer 3
        records = filter_prices_a0_reference(records, reference_price=26100)

        remaining = [r.price for r in records]
        # All sub-1000 gone, 666k+ gone, only reasonable shaver prices remain
        for p in remaining:
            assert 20000 <= p <= 80000


class TestCleanProductName:
    """Product name cleaning utility."""

    def test_strips_danawa_ui_text(self):
        dirty = "다이슨 빅+콰이엇 포름알데히드 BP04VS검색하기VS검색 도움말추천상품과스펙비교하세요.닫기"
        cleaned = clean_product_name(dirty)
        assert "VS검색하기" not in cleaned
        assert "VS검색 도움말" not in cleaned
        assert "추천상품과스펙비교하세요" not in cleaned
        assert "닫기" not in cleaned
        assert "다이슨" in cleaned
        assert "BP04" in cleaned

    def test_strips_purchase_type_labels(self):
        assert "(일반구매)" not in clean_product_name("AS305DWWA (일반구매)")
        assert "(공식판매)" not in clean_product_name("LG 제품 (공식판매)")

    def test_preserves_clean_name(self):
        name = "필립스 9000시리즈 면도기 S9986/55"
        assert clean_product_name(name) == name

    def test_empty_string(self):
        assert clean_product_name("") == ""


class TestComputeNameSimilarity:
    """Token-overlap name similarity."""

    def test_exact_match(self):
        assert compute_name_similarity("브라운 면도기 5", "브라운 면도기 5") == 1.0

    def test_partial_match(self):
        score = compute_name_similarity(
            "브라운 면도기 5 시리즈",
            "브라운 면도기 5 시리즈 5147s",
        )
        assert score >= 0.5

    def test_no_match(self):
        score = compute_name_similarity(
            "존재하지않는제품XYZ",
            "다이슨 공기청정기 BP04",
        )
        assert score < 0.5

    def test_empty_strings(self):
        assert compute_name_similarity("", "test") == 0.0
        assert compute_name_similarity("test", "") == 0.0
