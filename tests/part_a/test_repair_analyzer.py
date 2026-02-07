"""Tests for the repair analyzer module."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.part_a.repair_analyzer.models import (
    CommunityPost,
    RepairRecord,
    RepairStats,
    FailureTypeStat,
    calculate_repair_stats,
)
from src.part_a.repair_analyzer.community_scraper import CommunityScraper
from src.part_a.repair_analyzer.gpt_extractor import MockGPTExtractor


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class TestCommunityPost:
    """Test CommunityPost model."""

    def test_create_post(self):
        post = CommunityPost(
            title="로보락 S8 수리 후기",
            body="센서 고장으로 AS 보냈습니다",
            source="ppomppu",
            source_url="https://ppomppu.co.kr/123",
            date=date(2026, 1, 15),
        )
        assert post.title == "로보락 S8 수리 후기"
        assert post.source == "ppomppu"

    def test_to_dict(self):
        post = CommunityPost(
            title="Test",
            body="Body text " * 100,
            source="clien",
            date=date(2026, 2, 1),
        )
        d = post.to_dict()
        assert d["source"] == "clien"
        assert len(d["body"]) <= 200  # Truncated


class TestRepairRecord:
    """Test RepairRecord model."""

    def test_create_record(self):
        record = RepairRecord(
            product_name="로보락 S8 Pro Ultra",
            failure_type="sensor",
            repair_cost=150000,
            as_days=7,
            sentiment="positive",
            source="ppomppu",
        )
        assert record.repair_cost == 150000
        assert record.failure_type == "sensor"

    def test_to_dict(self):
        record = RepairRecord(
            product_name="Test",
            failure_type="motor",
            repair_cost=200000,
            as_days=10,
            sentiment="negative",
            source="clien",
            source_url="https://clien.net/123",
            date=date(2026, 1, 20),
        )
        d = record.to_dict()
        assert d["failure_type"] == "motor"
        assert d["repair_cost"] == 200000
        assert d["as_days"] == 10
        assert d["date"] == "2026-01-20"


class TestRepairStats:
    """Test repair statistics calculation."""

    def test_calculate_empty(self):
        stats = calculate_repair_stats([])
        assert stats.total_reports == 0
        assert stats.expected_repair_cost == 0
        assert stats.avg_as_days == 0.0

    def test_calculate_single_type(self):
        records = [
            RepairRecord("Product", "sensor", 150000, as_days=7, sentiment="positive", source="ppomppu"),
            RepairRecord("Product", "sensor", 180000, as_days=5, sentiment="neutral", source="clien"),
        ]
        stats = calculate_repair_stats(records)

        assert stats.total_reports == 2
        assert stats.product_name == "Product"
        # All same type → probability = 1.0, avg_cost = 165000
        assert stats.expected_repair_cost == 165000
        assert stats.avg_as_days == 6.0
        assert len(stats.failure_breakdown) == 1
        assert stats.failure_breakdown[0].type == "sensor"
        assert stats.failure_breakdown[0].probability == 1.0

    def test_calculate_multiple_types(self):
        records = [
            RepairRecord("Product", "sensor", 150000, as_days=7, source="ppomppu"),
            RepairRecord("Product", "sensor", 180000, as_days=5, source="clien"),
            RepairRecord("Product", "motor", 300000, as_days=14, source="ppomppu"),
            RepairRecord("Product", "battery", 120000, as_days=3, source="clien"),
        ]
        stats = calculate_repair_stats(records)

        assert stats.total_reports == 4
        # sensor: avg=165000, prob=0.5 → 82500
        # motor: avg=300000, prob=0.25 → 75000
        # battery: avg=120000, prob=0.25 → 30000
        # expected = 82500 + 75000 + 30000 = 187500
        assert stats.expected_repair_cost == 187500
        assert stats.avg_as_days == pytest.approx(7.25, abs=0.1)
        assert len(stats.failure_breakdown) == 3

    def test_calculate_with_zero_costs(self):
        records = [
            RepairRecord("Product", "sensor", 0, as_days=7, source="ppomppu"),
            RepairRecord("Product", "sensor", 150000, as_days=5, source="clien"),
        ]
        stats = calculate_repair_stats(records)
        # avg_cost only uses non-zero costs: 150000
        assert stats.failure_breakdown[0].avg_cost == 150000

    def test_stats_to_dict(self):
        stats = RepairStats(
            product_name="Test",
            total_reports=10,
            expected_repair_cost=150000,
            avg_as_days=7.5,
            failure_breakdown=[
                FailureTypeStat("sensor", 5, 150000, 0.5),
                FailureTypeStat("motor", 3, 200000, 0.3),
            ],
        )
        d = stats.to_dict()
        assert d["total_reports"] == 10
        assert d["expected_repair_cost"] == 150000
        assert d["repair_stats"]["total_reports"] == 10
        assert len(d["repair_stats"]["failure_types"]) == 2


class TestCommunityScraper:
    """Test community scraper with cached HTML fixtures."""

    def test_parse_date(self):
        assert CommunityScraper._parse_date("2026-01-15") == date(2026, 1, 15)
        assert CommunityScraper._parse_date("2026.01.15") == date(2026, 1, 15)
        assert CommunityScraper._parse_date("2026/01/15") == date(2026, 1, 15)
        assert CommunityScraper._parse_date("") is None
        assert CommunityScraper._parse_date("invalid") is None

    def test_parse_ppomppu_results(self, temp_db):
        """Test parsing Ppomppu search results from cached HTML."""
        html = (FIXTURES_DIR / "ppomppu_search.html").read_text(encoding="utf-8")

        scraper = CommunityScraper(temp_db)
        mock_response = MagicMock()
        mock_response.text = html
        scraper._client.get = MagicMock(return_value=mock_response)

        posts = scraper._search_ppomppu("로보락 S8 수리", max_results=10)

        assert len(posts) == 4
        assert posts[0].title == "로보락 S8 Pro Ultra 센서 고장 수리 후기"
        assert posts[0].source == "ppomppu"
        assert posts[0].date == date(2026, 1, 15)
        assert "센서" in posts[0].body

    def test_deduplication(self, temp_db):
        """Test that search_all deduplicates by URL."""
        scraper = CommunityScraper(temp_db)

        # Mock to return same posts for every source/keyword
        mock_response = MagicMock()
        mock_response.text = (FIXTURES_DIR / "ppomppu_search.html").read_text(encoding="utf-8")
        scraper._client.get = MagicMock(return_value=mock_response)

        posts = scraper.search_all("로보락", ["수리", "AS"], max_per_source=10)

        # Should be deduplicated by URL
        urls = [p.source_url for p in posts if p.source_url]
        assert len(urls) == len(set(urls))


class TestMockGPTExtractor:
    """Test the mock/heuristic GPT extractor."""

    def test_extract_sensor_failure(self):
        extractor = MockGPTExtractor()
        post = CommunityPost(
            title="로보락 S8 Pro 센서 고장",
            body="센서 문제로 AS 보냈는데 15만원 나왔어요. 7일 만에 돌아왔습니다.",
            source="ppomppu",
            date=date(2026, 1, 15),
        )
        record = extractor.extract_single(post, "로보락 S8 Pro")

        assert record is not None
        assert record.failure_type == "sensor"
        assert record.repair_cost == 150000
        assert record.as_days == 7
        assert record.product_name == "로보락 S8 Pro"

    def test_extract_battery_failure(self):
        extractor = MockGPTExtractor()
        post = CommunityPost(
            title="로보락 배터리 교체",
            body="배터리 수명 다해서 교체했습니다. 12만원 들었고 5일 걸렸어요.",
            source="clien",
            date=date(2026, 1, 20),
        )
        record = extractor.extract_single(post, "로보락")

        assert record is not None
        assert record.failure_type == "battery"
        assert record.repair_cost == 120000
        assert record.as_days == 5

    def test_extract_irrelevant_post(self):
        extractor = MockGPTExtractor()
        post = CommunityPost(
            title="아이폰 수리 후기",
            body="아이폰 화면 깨져서 교체했습니다.",
            source="ppomppu",
        )
        record = extractor.extract_single(post, "로보락 S8 Pro")

        assert record is None  # Irrelevant post

    def test_extract_batch(self):
        extractor = MockGPTExtractor()
        posts = [
            CommunityPost(
                "로보락 S8 센서 고장",
                "센서 문제 15만원 수리 7일 만에",
                "ppomppu",
            ),
            CommunityPost(
                "아이폰 수리",
                "아이폰 화면 교체",
                "ppomppu",
            ),
            CommunityPost(
                "로보락 모터 소음",
                "모터에서 이상한 소음 20만원 수리비 10일 소요 불만족",
                "clien",
            ),
        ]
        records = extractor.extract_batch(posts, "로보락")

        assert len(records) == 2  # Only 2 are relevant
        assert records[0].failure_type == "sensor"
        assert records[1].failure_type == "motor"

    def test_extract_cost_man_won(self):
        """Test extracting '만원' notation."""
        assert MockGPTExtractor._extract_cost("수리비 15만원 나왔어요") == 150000
        assert MockGPTExtractor._extract_cost("12만원") == 120000
        assert MockGPTExtractor._extract_cost("수리비 없음") == 0

    def test_extract_cost_won(self):
        """Test extracting regular 원 notation."""
        assert MockGPTExtractor._extract_cost("150,000원 청구") == 150000
        assert MockGPTExtractor._extract_cost("200000원") == 200000

    def test_detect_sentiment(self):
        assert MockGPTExtractor._detect_sentiment("만족합니다 친절") == "positive"
        assert MockGPTExtractor._detect_sentiment("불만족 최악") == "negative"
        assert MockGPTExtractor._detect_sentiment("그냥 보통") == "neutral"

    def test_extract_as_days(self):
        assert MockGPTExtractor._extract_as_days("7일 만에 돌아왔어요") == 7
        assert MockGPTExtractor._extract_as_days("2주 걸렸습니다") == 14
        assert MockGPTExtractor._extract_as_days("기간 모름") is None


class TestSaveToDb:
    """Test database persistence."""

    def test_save_repair_records(self, temp_db):
        """Test saving repair records to database."""
        from src.part_a.repair_analyzer.main import save_records_to_db
        from src.part_a.database.connection import get_connection

        records = [
            RepairRecord(
                product_name="테스트 제품",
                failure_type="sensor",
                repair_cost=150000,
                as_days=7,
                sentiment="positive",
                source="ppomppu",
                source_url="https://example.com/1",
                date=date(2026, 1, 15),
            ),
            RepairRecord(
                product_name="테스트 제품",
                failure_type="motor",
                repair_cost=200000,
                as_days=10,
                sentiment="negative",
                source="clien",
                source_url="https://example.com/2",
                date=date(2026, 1, 20),
            ),
        ]

        inserted = save_records_to_db(records, temp_db)
        assert inserted == 2

        conn = get_connection(temp_db)
        try:
            rows = conn.execute(
                "SELECT COUNT(*) as cnt FROM repair_reports"
            ).fetchone()
            assert rows["cnt"] == 2

            row = conn.execute(
                "SELECT * FROM repair_reports ORDER BY id LIMIT 1"
            ).fetchone()
            assert row["failure_type"] == "sensor"
            assert row["repair_cost"] == 150000
            assert row["as_days"] == 7
        finally:
            conn.close()
