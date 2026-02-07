"""Tests for the product selector module (A-0)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.part_a.common.config import Config
from src.part_a.database.connection import get_connection, init_db
from src.part_a.product_selector.candidate_aggregator import CandidateAggregator
from src.part_a.product_selector.category_config import CategoryConfig
from src.part_a.product_selector.models import (
    CandidateProduct,
    PricePosition,
    ProductScores,
    ResaleQuickCheck,
    SalesRankingEntry,
    SearchInterest,
    SelectionResult,
    SentimentData,
    SlotAssignment,
    ValidationResult,
)
from src.part_a.product_selector.price_classifier import PriceClassifier
from src.part_a.product_selector.sales_ranking_scraper import (
    CoupangRankingScraper,
    DanawaRankingScraper,
    NaverShoppingRankingScraper,
    _parse_count,
    _parse_price,
    _parse_rating,
)
from src.part_a.product_selector.scorer import ProductScorer
from src.part_a.product_selector.search_interest_scraper import NaverDataLabScraper
from src.part_a.product_selector.sentiment_scraper import SentimentScraper
from src.part_a.product_selector.slot_selector import SlotSelector
from src.part_a.product_selector.validator import SelectionValidator

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


# ===================================================================
# Helpers — build test data
# ===================================================================


def _make_candidate(
    name: str,
    brand: str,
    presence: int = 3,
    avg_rank: float = 5.0,
    price: int = 1_000_000,
    tier: str = "mid",
    search_vol: float = 50.0,
    neg_posts: int = 5,
    pos_posts: int = 15,
    total_posts: int = 30,
    resale_ratio: float = 0.5,
    in_stock: bool = True,
    release_date: date | None = None,
) -> CandidateProduct:
    """Build a CandidateProduct with all data fields populated."""
    rankings = [
        SalesRankingEntry(
            product_name=name, brand=brand, platform="danawa",
            rank=int(avg_rank), price=price,
        )
    ]
    return CandidateProduct(
        name=name,
        brand=brand,
        category="로봇청소기",
        rankings=rankings,
        presence_score=presence,
        avg_rank=avg_rank,
        in_stock=in_stock,
        release_date=release_date,
        search_interest=SearchInterest(
            product_name=name, volume_30d=search_vol, volume_90d=search_vol,
        ),
        sentiment=SentimentData(
            product_name=name, total_posts=total_posts,
            negative_posts=neg_posts, positive_posts=pos_posts,
        ),
        price_position=PricePosition(
            product_name=name, current_price=price, avg_price_90d=price,
            price_tier=tier,
            price_normalized=(
                {"premium": 1.0, "mid": 0.5, "budget": 0.0}.get(tier, 0.5)
            ),
        ),
        resale_check=ResaleQuickCheck(
            product_name=name,
            avg_used_price=int(price * resale_ratio),
            avg_new_price=price,
            sample_count=10,
        ),
    )


# ===================================================================
# Model Tests
# ===================================================================


class TestSalesRankingEntry:
    def test_create(self):
        entry = SalesRankingEntry(
            product_name="테스트 제품", brand="테스트", platform="danawa", rank=1
        )
        assert entry.product_name == "테스트 제품"
        assert entry.platform == "danawa"
        assert entry.rank == 1

    def test_to_dict(self):
        entry = SalesRankingEntry(
            product_name="Test", brand="Brand", platform="naver",
            rank=3, review_count=100, price=500000,
        )
        d = entry.to_dict()
        assert d["product_name"] == "Test"
        assert d["rank"] == 3
        assert d["review_count"] == 100
        assert d["price"] == 500000


class TestSearchInterest:
    def test_create(self):
        si = SearchInterest(product_name="Test", volume_30d=85.0, volume_90d=70.0)
        assert si.trend_direction == "stable"

    def test_to_dict(self):
        si = SearchInterest(
            product_name="Test", volume_30d=85.0, volume_90d=70.0,
            trend_direction="rising",
        )
        d = si.to_dict()
        assert d["volume_30d"] == 85.0
        assert d["trend_direction"] == "rising"


class TestSentimentData:
    def test_complaint_rate(self):
        sd = SentimentData(
            product_name="Test", total_posts=100, negative_posts=8, positive_posts=72,
        )
        assert sd.complaint_rate == pytest.approx(0.08)

    def test_satisfaction_rate(self):
        sd = SentimentData(
            product_name="Test", total_posts=100, negative_posts=8, positive_posts=72,
        )
        assert sd.satisfaction_rate == pytest.approx(0.72)

    def test_zero_total_posts(self):
        sd = SentimentData(
            product_name="Test", total_posts=0, negative_posts=0, positive_posts=0,
        )
        assert sd.complaint_rate == 0.0
        assert sd.satisfaction_rate == 0.0

    def test_to_dict(self):
        sd = SentimentData(
            product_name="Test", total_posts=50, negative_posts=5, positive_posts=30,
        )
        d = sd.to_dict()
        assert d["complaint_rate"] == 0.1
        assert d["satisfaction_rate"] == 0.6


class TestPricePosition:
    def test_create(self):
        pp = PricePosition(
            product_name="Test", current_price=1000000,
            avg_price_90d=1050000, price_tier="premium",
        )
        assert pp.price_tier == "premium"

    def test_to_dict(self):
        pp = PricePosition(
            product_name="Test", current_price=500000,
            avg_price_90d=520000, price_tier="budget", price_normalized=0.2,
        )
        d = pp.to_dict()
        assert d["price_tier"] == "budget"
        assert d["price_normalized"] == 0.2


class TestResaleQuickCheck:
    def test_resale_ratio(self):
        rc = ResaleQuickCheck(
            product_name="Test", avg_used_price=700000,
            avg_new_price=1000000, sample_count=10,
        )
        assert rc.resale_ratio == pytest.approx(0.7)

    def test_zero_new_price(self):
        rc = ResaleQuickCheck(
            product_name="Test", avg_used_price=500000,
            avg_new_price=0, sample_count=0,
        )
        assert rc.resale_ratio == 0.0

    def test_to_dict(self):
        rc = ResaleQuickCheck(
            product_name="Test", avg_used_price=500000,
            avg_new_price=1000000, sample_count=5,
        )
        d = rc.to_dict()
        assert d["resale_ratio"] == 0.5


class TestCandidateProduct:
    def test_create_minimal(self):
        c = CandidateProduct(name="Test", brand="Brand", category="Cat")
        assert c.in_stock is True
        assert c.presence_score == 0

    def test_to_dict(self):
        c = _make_candidate("Test", "Brand")
        d = c.to_dict()
        assert d["name"] == "Test"
        assert d["brand"] == "Brand"
        assert d["presence_score"] == 3


class TestProductScores:
    def test_weighted_total(self):
        ps = ProductScores(
            product_name="Test",
            sales_presence=1.0,
            search_interest=1.0,
            sentiment=1.0,
            price_position=1.0,
            resale_retention=1.0,
        )
        assert ps.weighted_total == pytest.approx(1.0)

    def test_weighted_total_partial(self):
        ps = ProductScores(
            product_name="Test",
            sales_presence=0.5,    # 0.5 * 0.20 = 0.10
            search_interest=0.8,   # 0.8 * 0.25 = 0.20
            sentiment=0.6,         # 0.6 * 0.25 = 0.15
            price_position=0.4,    # 0.4 * 0.15 = 0.06
            resale_retention=0.7,  # 0.7 * 0.15 = 0.105
        )
        expected = 0.10 + 0.20 + 0.15 + 0.06 + 0.105
        assert ps.weighted_total == pytest.approx(expected)

    def test_to_dict(self):
        ps = ProductScores(product_name="Test", sales_presence=0.9)
        d = ps.to_dict()
        assert d["sales_presence"] == 0.9
        assert "weighted_total" in d


class TestSelectionResult:
    def test_to_dict(self):
        candidate = _make_candidate("TestProd", "TestBrand")
        scores = ProductScores(product_name="TestProd", sales_presence=0.9)
        assignment = SlotAssignment(
            slot="stability", candidate=candidate, scores=scores,
            selection_reasons=["Best sentiment"],
        )
        validation = ValidationResult(
            check_name="brand_diversity", passed=True, detail="3 unique brands",
        )
        result = SelectionResult(
            category="로봇청소기",
            selection_date=date(2026, 2, 7),
            data_sources={"sales_rankings": ["naver"]},
            candidate_pool_size=10,
            selected_products=[assignment],
            validation=[validation],
        )
        d = result.to_dict()
        assert d["category"] == "로봇청소기"
        assert d["candidate_pool_size"] == 10
        assert len(d["selected_products"]) == 1
        assert "brand_diversity" in d["validation"]

    def test_to_json(self):
        candidate = _make_candidate("TestProd", "TestBrand")
        scores = ProductScores(product_name="TestProd")
        assignment = SlotAssignment(slot="balance", candidate=candidate, scores=scores)
        result = SelectionResult(
            category="test",
            selection_date=date(2026, 1, 1),
            data_sources={},
            candidate_pool_size=5,
            selected_products=[assignment],
            validation=[],
        )
        j = result.to_json()
        parsed = json.loads(j)
        assert parsed["category"] == "test"


# ===================================================================
# Parsing Helper Tests
# ===================================================================


class TestParsingHelpers:
    def test_parse_price_basic(self):
        assert _parse_price("1,490,000원") == 1490000

    def test_parse_price_no_unit(self):
        assert _parse_price("645,000") == 645000

    def test_parse_price_tilde(self):
        assert _parse_price("369,000원~") == 369000

    def test_parse_price_empty(self):
        assert _parse_price("") == 0

    def test_parse_count_with_parens(self):
        assert _parse_count("(2,847)") == 2847

    def test_parse_count_with_prefix(self):
        assert _parse_count("리뷰 1,523") == 1523

    def test_parse_count_empty(self):
        assert _parse_count("") == 0

    def test_parse_rating_decimal(self):
        assert _parse_rating("4.8") == pytest.approx(4.8)

    def test_parse_rating_with_text(self):
        assert _parse_rating("별점 4.5점") == pytest.approx(4.5)

    def test_parse_rating_empty(self):
        assert _parse_rating("") == 0.0


# ===================================================================
# Scraper Tests (with fixture HTML)
# ===================================================================


class TestNaverShoppingRankingScraper:
    def test_parse_api_response(self, temp_db):
        """Test parsing of Naver Shopping Search API JSON response."""
        api_json = {
            "lastBuildDate": "Fri, 07 Feb 2026 18:00:00 +0900",
            "total": 5,
            "start": 1,
            "display": 5,
            "items": [
                {
                    "title": "로보락 <b>S8</b> MaxV Ultra",
                    "lprice": "1490000",
                    "hprice": "1600000",
                    "productId": "12345",
                    "brand": "로보락",
                    "maker": "Roborock",
                    "mallName": "네이버",
                    "category1": "가전",
                    "category2": "생활가전",
                },
                {
                    "title": "삼성 비스포크 제트봇 AI",
                    "lprice": "1200000",
                    "productId": "12346",
                    "brand": "삼성전자",
                },
                {
                    "title": "LG 코드제로 R9",
                    "lprice": "890000",
                    "productId": "12347",
                    "brand": "LG전자",
                },
            ],
        }
        scraper = NaverShoppingRankingScraper(temp_db)
        # Set API keys so scraper doesn't skip
        scraper.config.naver_datalab_client_id = "test_id"
        scraper.config.naver_datalab_client_secret = "test_secret"
        mock_resp = MagicMock()
        mock_resp.json.return_value = api_json
        scraper._client.get = MagicMock(return_value=mock_resp)

        results = scraper.get_best_products("로봇청소기")
        assert len(results) == 3
        assert all(r.platform == "naver" for r in results)
        assert results[0].rank == 1
        assert results[0].price == 1490000
        # HTML tags should be stripped from title
        assert "<b>" not in results[0].product_name
        assert "S8" in results[0].product_name
        assert results[0].brand == "로보락"
        assert results[0].product_code == "12345"

    def test_skip_without_api_keys(self, temp_db):
        """Returns empty list when API keys are not configured."""
        scraper = NaverShoppingRankingScraper(temp_db)
        scraper.config.naver_datalab_client_id = ""
        scraper.config.naver_datalab_client_secret = ""
        results = scraper.get_best_products("로봇청소기")
        assert results == []


class TestDanawaRankingScraper:
    def test_parse_ranking_page(self, temp_db):
        html = (FIXTURES_DIR / "danawa_popular.html").read_text(encoding="utf-8")
        scraper = DanawaRankingScraper(temp_db)
        mock_resp = MagicMock()
        mock_resp.text = html
        scraper._client.get = MagicMock(return_value=mock_resp)

        results = scraper.get_popular_products("10204001")
        assert len(results) == 5
        assert all(r.platform == "danawa" for r in results)
        assert results[0].product_code == "98001"
        assert results[0].price == 1480000


class TestCoupangRankingScraper:
    def test_parse_search_results(self, temp_db):
        html = (FIXTURES_DIR / "coupang_search.html").read_text(encoding="utf-8")
        scraper = CoupangRankingScraper(temp_db)
        mock_resp = MagicMock()
        mock_resp.text = html
        scraper._client.get = MagicMock(return_value=mock_resp)

        results = scraper.get_best_sellers("로봇청소기")
        assert len(results) == 5
        assert all(r.platform == "coupang" for r in results)
        assert results[0].price == 949000
        assert results[0].review_count == 3201


# ===================================================================
# Candidate Aggregator Tests
# ===================================================================


class TestCandidateAggregator:
    def test_aggregate_cross_platform(self):
        naver = [
            SalesRankingEntry(product_name="로보락 Q Revo S", brand="로보락", platform="naver", rank=1, price=1490000),
            SalesRankingEntry(product_name="삼성 비스포크 제트봇 AI", brand="삼성", platform="naver", rank=2, price=1290000),
        ]
        danawa = [
            SalesRankingEntry(product_name="로보락 Q Revo S", brand="로보락", platform="danawa", rank=1, price=1480000),
            SalesRankingEntry(product_name="에코백스 T30 Pro Omni", brand="에코백스", platform="danawa", rank=3, price=640000),
        ]
        coupang = [
            SalesRankingEntry(product_name="로보락 Q Revo S 로봇청소기", brand="Roborock", platform="coupang", rank=3, price=1495000),
            SalesRankingEntry(product_name="에코백스 T30 Pro Omni 로봇청소기", brand="ECOVACS", platform="coupang", rank=2, price=645000),
        ]

        aggregator = CandidateAggregator()
        candidates = aggregator.aggregate(naver, danawa, coupang, category="로봇청소기")

        # 로보락 appears on all 3, 에코백스 on 2, 삼성 on only 1 (excluded)
        assert len(candidates) >= 2
        roborock = next((c for c in candidates if "로보락" in c.name), None)
        assert roborock is not None
        assert roborock.presence_score == 3

    def test_filter_presence_score(self):
        naver = [
            SalesRankingEntry(product_name="OnlyNaver", brand="B1", platform="naver", rank=1),
        ]
        danawa = [
            SalesRankingEntry(product_name="OnlyDanawa", brand="B2", platform="danawa", rank=1),
        ]
        coupang = [
            SalesRankingEntry(product_name="OnlyCoupang", brand="B3", platform="coupang", rank=1),
        ]

        aggregator = CandidateAggregator()
        candidates = aggregator.aggregate(naver, danawa, coupang, min_presence=2)
        # None appear on 2+ platforms
        assert len(candidates) == 0

    def test_normalize_product_name(self):
        assert "로보락" in CandidateAggregator._normalize_product_name("로보락 S8 Pro Ultra 로봇청소기")
        # Category suffix removed
        assert "로봇청소기" not in CandidateAggregator._normalize_product_name("로보락 S8 Pro Ultra 로봇청소기")


# ===================================================================
# Search Interest Tests
# ===================================================================


class TestNaverDataLabScraper:
    def test_parse_api_response(self):
        fixture = json.loads(
            (FIXTURES_DIR / "naver_datalab_response.json").read_text(encoding="utf-8")
        )
        volumes = NaverDataLabScraper._parse_api_response(fixture)
        assert "로보락 Q Revo S" in volumes
        assert volumes["드리미 L10s Pro Ultra Heat"] > volumes["LG 코드제로 R5"]

    def test_calculate_trend_rising(self):
        assert NaverDataLabScraper._calculate_trend(90.0, 70.0) == "rising"

    def test_calculate_trend_declining(self):
        assert NaverDataLabScraper._calculate_trend(30.0, 50.0) == "declining"

    def test_calculate_trend_stable(self):
        assert NaverDataLabScraper._calculate_trend(50.0, 50.0) == "stable"

    def test_calculate_trend_zero_base(self):
        assert NaverDataLabScraper._calculate_trend(50.0, 0.0) == "stable"


# ===================================================================
# Sentiment Scraper Tests
# ===================================================================


class TestSentimentScraper:
    def test_parse_ppomppu_count(self):
        html = (FIXTURES_DIR / "ppomppu_sentiment.html").read_text(encoding="utf-8")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        count = SentimentScraper._parse_ppomppu_count(soup)
        assert count == 3

    def test_parse_clien_count(self):
        html = (FIXTURES_DIR / "clien_sentiment.html").read_text(encoding="utf-8")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        count = SentimentScraper._parse_clien_count(soup)
        assert count == 4

    def test_parse_naver_cafe_count(self):
        html = (FIXTURES_DIR / "naver_cafe_sentiment.html").read_text(encoding="utf-8")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        count = SentimentScraper._parse_naver_cafe_count(soup)
        assert count == 47  # From "약 47건" in title_num


# ===================================================================
# Price Classifier Tests
# ===================================================================


class TestPriceClassifier:
    def test_assign_tiers_3_products(self):
        prices = {"A": 1500000, "B": 900000, "C": 500000}
        tiers = PriceClassifier._assign_tiers(prices)
        assert tiers["C"] == "budget"
        assert tiers["B"] == "mid"
        assert tiers["A"] == "premium"

    def test_assign_tiers_5_products(self):
        prices = {"A": 1500000, "B": 1200000, "C": 900000, "D": 700000, "E": 500000}
        tiers = PriceClassifier._assign_tiers(prices)
        # Bottom 30% (ceil(5*0.3)=2): E, D = budget
        # Top 30% (ceil(5*0.3)=2): A, B = premium
        # Middle: C = mid
        assert tiers["E"] == "budget"
        assert tiers["D"] == "budget"
        assert tiers["C"] == "mid"
        assert tiers["B"] == "premium"
        assert tiers["A"] == "premium"

    def test_assign_tiers_1_product(self):
        tiers = PriceClassifier._assign_tiers({"A": 1000000})
        assert tiers["A"] == "mid"

    def test_assign_tiers_2_products(self):
        tiers = PriceClassifier._assign_tiers({"A": 1000000, "B": 500000})
        assert tiers["B"] == "budget"
        assert tiers["A"] == "premium"

    def test_normalize_prices(self):
        prices = {"A": 1500000, "B": 900000, "C": 500000}
        normalized = PriceClassifier._normalize_prices(prices)
        assert normalized["C"] == pytest.approx(0.0)
        assert normalized["A"] == pytest.approx(1.0)
        assert 0.0 < normalized["B"] < 1.0

    def test_normalize_prices_same_price(self):
        prices = {"A": 1000000, "B": 1000000}
        normalized = PriceClassifier._normalize_prices(prices)
        assert normalized["A"] == 0.5
        assert normalized["B"] == 0.5


# ===================================================================
# Scorer Tests
# ===================================================================


class TestProductScorer:
    def test_score_candidates(self):
        candidates = [
            _make_candidate("A", "BrandA", presence=3, search_vol=100.0,
                          neg_posts=2, pos_posts=20, total_posts=30, resale_ratio=0.6),
            _make_candidate("B", "BrandB", presence=2, search_vol=50.0,
                          neg_posts=10, pos_posts=5, total_posts=30, resale_ratio=0.3),
        ]
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        assert scores["A"].sales_presence > scores["B"].sales_presence
        assert scores["A"].search_interest > scores["B"].search_interest
        assert scores["A"].sentiment > scores["B"].sentiment

    def test_empty_candidates(self):
        scorer = ProductScorer()
        assert scorer.score_candidates([]) == {}


# ===================================================================
# Slot Selector Tests
# ===================================================================


class TestSlotSelector:
    def _make_3_candidates(self):
        return [
            _make_candidate("Premium Pro", "BrandA", tier="premium", price=1500000,
                          neg_posts=2, pos_posts=25, total_posts=30, resale_ratio=0.7,
                          search_vol=70.0, presence=3),
            _make_candidate("Balance Best", "BrandB", tier="mid", price=900000,
                          neg_posts=5, pos_posts=15, total_posts=30, resale_ratio=0.5,
                          search_vol=100.0, presence=3),
            _make_candidate("Budget Value", "BrandC", tier="budget", price=500000,
                          neg_posts=8, pos_posts=10, total_posts=30, resale_ratio=0.3,
                          search_vol=40.0, presence=2),
        ]

    def test_select_3_products(self):
        candidates = self._make_3_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        selector = SlotSelector()
        assignments = selector.select(candidates, scores)

        assert len(assignments) == 3
        slots = {a.slot for a in assignments}
        assert slots == {"stability", "balance", "value"}

    def test_stability_prefers_low_complaint(self):
        candidates = self._make_3_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        selector = SlotSelector()
        assignments = selector.select(candidates, scores)

        stability = next(a for a in assignments if a.slot == "stability")
        # Premium Pro has lowest complaint_rate (2/30) and highest resale
        assert stability.candidate.name == "Premium Pro"

    def test_balance_prefers_high_search(self):
        candidates = self._make_3_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        selector = SlotSelector()
        assignments = selector.select(candidates, scores)

        balance = next(a for a in assignments if a.slot == "balance")
        # Balance Best has highest search volume (100)
        assert balance.candidate.name == "Balance Best"

    def test_value_prefers_low_price(self):
        candidates = self._make_3_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        selector = SlotSelector()
        assignments = selector.select(candidates, scores)

        value = next(a for a in assignments if a.slot == "value")
        # Budget Value is the only remaining candidate
        assert value.candidate.name == "Budget Value"

    def test_insufficient_candidates_raises(self):
        candidates = [_make_candidate("A", "B"), _make_candidate("C", "D")]
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        selector = SlotSelector()
        with pytest.raises(ValueError, match="at least 3"):
            selector.select(candidates, scores)


# ===================================================================
# Validator Tests
# ===================================================================


class TestSelectionValidator:
    def _make_config(self):
        return CategoryConfig.default_robot_vacuum()

    def _make_assignment(
        self, slot, name, brand, price=1000000, tier="mid",
        total_posts=30, in_stock=True, release_date=None,
    ):
        candidate = _make_candidate(
            name, brand, price=price, tier=tier,
            total_posts=total_posts, in_stock=in_stock,
            release_date=release_date,
        )
        scores = ProductScores(product_name=name, sales_presence=0.8)
        return SlotAssignment(slot=slot, candidate=candidate, scores=scores)

    def test_brand_diversity_pass(self):
        config = self._make_config()
        validator = SelectionValidator(config)
        assignments = [
            self._make_assignment("stability", "A", "Brand1"),
            self._make_assignment("balance", "B", "Brand2"),
            self._make_assignment("value", "C", "Brand3"),
        ]
        results = validator.validate(assignments)
        brand_check = next(r for r in results if r.check_name == "brand_diversity")
        assert brand_check.passed

    def test_brand_diversity_fail(self):
        config = self._make_config()
        validator = SelectionValidator(config)
        assignments = [
            self._make_assignment("stability", "A", "Samsung"),
            self._make_assignment("balance", "B", "Samsung"),
            self._make_assignment("value", "C", "LG"),
        ]
        results = validator.validate(assignments)
        brand_check = next(r for r in results if r.check_name == "brand_diversity")
        assert not brand_check.passed

    def test_price_spread_pass(self):
        config = self._make_config()
        validator = SelectionValidator(config)
        assignments = [
            self._make_assignment("stability", "A", "B1", price=1500000),
            self._make_assignment("balance", "B", "B2", price=900000),
            self._make_assignment("value", "C", "B3", price=500000),
        ]
        results = validator.validate(assignments)
        spread = next(r for r in results if r.check_name == "price_spread")
        assert spread.passed  # 1500000/500000 = 3.0 >= 1.3

    def test_price_spread_fail(self):
        config = self._make_config()
        validator = SelectionValidator(config)
        assignments = [
            self._make_assignment("stability", "A", "B1", price=1000000),
            self._make_assignment("balance", "B", "B2", price=950000),
            self._make_assignment("value", "C", "B3", price=900000),
        ]
        results = validator.validate(assignments)
        spread = next(r for r in results if r.check_name == "price_spread")
        assert not spread.passed  # 1000000/900000 = 1.11 < 1.3

    def test_data_sufficiency_pass(self):
        config = self._make_config()
        validator = SelectionValidator(config)
        assignments = [
            self._make_assignment("stability", "A", "B1", total_posts=50),
            self._make_assignment("balance", "B", "B2", total_posts=30),
            self._make_assignment("value", "C", "B3", total_posts=25),
        ]
        results = validator.validate(assignments)
        sufficiency = next(r for r in results if r.check_name == "data_sufficiency")
        assert sufficiency.passed

    def test_data_sufficiency_fail(self):
        config = self._make_config()
        validator = SelectionValidator(config)
        assignments = [
            self._make_assignment("stability", "A", "B1", total_posts=50),
            self._make_assignment("balance", "B", "B2", total_posts=5),
            self._make_assignment("value", "C", "B3", total_posts=30),
        ]
        results = validator.validate(assignments)
        sufficiency = next(r for r in results if r.check_name == "data_sufficiency")
        assert not sufficiency.passed

    def test_availability_pass(self):
        config = self._make_config()
        validator = SelectionValidator(config)
        assignments = [
            self._make_assignment("stability", "A", "B1", in_stock=True),
            self._make_assignment("balance", "B", "B2", in_stock=True),
            self._make_assignment("value", "C", "B3", in_stock=True),
        ]
        results = validator.validate(assignments)
        avail = next(r for r in results if r.check_name == "availability")
        assert avail.passed

    def test_availability_fail(self):
        config = self._make_config()
        validator = SelectionValidator(config)
        assignments = [
            self._make_assignment("stability", "A", "B1", in_stock=True),
            self._make_assignment("balance", "B", "B2", in_stock=False),
            self._make_assignment("value", "C", "B3", in_stock=True),
        ]
        results = validator.validate(assignments)
        avail = next(r for r in results if r.check_name == "availability")
        assert not avail.passed

    def test_validate_and_fix_brand_swap(self):
        config = self._make_config()
        validator = SelectionValidator(config)

        # Samsung appears twice
        assignments = [
            self._make_assignment("stability", "JetBot1", "Samsung", price=1300000),
            self._make_assignment("balance", "JetBot2", "Samsung", price=1100000),
            self._make_assignment("value", "CordZero", "LG", price=800000),
        ]

        # Alternative candidate
        alt = _make_candidate("Roborock S8", "Roborock", price=1400000)
        candidates = [a.candidate for a in assignments] + [alt]
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        fixed, results = validator.validate_and_fix(assignments, candidates, scores)
        brand_check = next(r for r in results if r.check_name == "brand_diversity")
        # Should have been fixed
        brands = [a.candidate.brand for a in fixed]
        assert len(set(brands)) == 3


# ===================================================================
# Category Config Tests
# ===================================================================


class TestCategoryConfig:
    def test_from_yaml(self, tmp_path):
        yaml_content = """
name: "test_category"
search_terms: ["테스트"]
negative_keywords: ["불만", "고장"]
positive_keywords: ["추천", "만족"]
price_range:
  min: 100000
  max: 500000
max_product_age_months: 12
min_community_posts: 15
danawa_category_code: "12345"
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content, encoding="utf-8")
        config = CategoryConfig.from_yaml(str(yaml_path))

        assert config.name == "test_category"
        assert config.search_terms == ["테스트"]
        assert config.price_range_min == 100000
        assert config.price_range_max == 500000
        assert config.max_product_age_months == 12
        assert config.min_community_posts == 15
        assert config.danawa_category_code == "12345"

    def test_default_robot_vacuum(self):
        config = CategoryConfig.default_robot_vacuum()
        assert config.name == "robot_vacuum"
        assert "로봇청소기" in config.search_terms
        assert config.min_community_posts == 20


# ===================================================================
# DB Tests
# ===================================================================


class TestSaveSelectionToDb:
    def test_save_selection_result(self, temp_db):
        from src.part_a.product_selector.pipeline import ProductSelectionPipeline

        candidate = _make_candidate("Test", "Brand")
        scores = ProductScores(product_name="Test")
        assignment = SlotAssignment(slot="stability", candidate=candidate, scores=scores)
        result = SelectionResult(
            category="로봇청소기",
            selection_date=date(2026, 2, 7),
            data_sources={"test": "test"},
            candidate_pool_size=10,
            selected_products=[assignment],
            validation=[],
        )

        pipeline = ProductSelectionPipeline(
            CategoryConfig.default_robot_vacuum(), temp_db
        )
        pipeline.save_to_db(result)

        # Verify in database
        conn = get_connection(temp_db)
        try:
            row = conn.execute(
                "SELECT * FROM product_selections WHERE category = ?",
                ("로봇청소기",),
            ).fetchone()
            assert row is not None
            assert row["candidate_pool_size"] == 10
            data = json.loads(row["result_json"])
            assert data["category"] == "로봇청소기"
        finally:
            conn.close()
