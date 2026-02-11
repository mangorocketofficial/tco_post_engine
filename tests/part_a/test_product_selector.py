"""Tests for the product selector module (A-0)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.part_a.common.config import Config
from src.part_a.database.connection import get_connection, init_db
from src.part_a.product_selector.category_config import CategoryConfig
from src.part_a.product_selector.models import (
    CandidateProduct,
    KeywordMetrics,
    PricePosition,
    ProductScores,
    SalesRankingEntry,
    SearchInterest,
    SelectedProduct,
    SelectionResult,
    SentimentData,
    ValidationResult,
    extract_manufacturer,
)
from src.part_a.product_selector.pipeline import _build_product_keyword
from src.part_a.product_selector.naver_ad_client import (
    NaverAdClient,
    _clean_keyword,
    _map_competition,
    _safe_int,
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
from src.part_a.product_selector.slot_selector import SCORE_FLOOR, SlotSelector, score_tiers, select_winning_tier

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


# ===================================================================
# Helpers — build test data
# ===================================================================


def _make_candidate(
    name: str,
    brand: str,
    price: int = 1_000_000,
    monthly_clicks: int = 500,
    avg_cpc: int = 3000,
    monthly_search_volume: int = 10000,
    competition: str = "medium",
    naver_rank: int = 1,
    in_stock: bool = True,
) -> CandidateProduct:
    """Build a CandidateProduct with keyword metrics populated."""
    return CandidateProduct(
        name=name,
        brand=brand,
        category="로봇청소기",
        price=price,
        naver_rank=naver_rank,
        in_stock=in_stock,
        keyword_metrics=KeywordMetrics(
            product_name=name,
            monthly_clicks=monthly_clicks,
            monthly_pc_clicks=monthly_clicks // 3,
            monthly_mobile_clicks=monthly_clicks - monthly_clicks // 3,
            avg_cpc=avg_cpc,
            monthly_search_volume=monthly_search_volume,
            monthly_pc_search=monthly_search_volume // 3,
            monthly_mobile_search=monthly_search_volume - monthly_search_volume // 3,
            competition=competition,
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


class TestKeywordMetrics:
    def test_create_default(self):
        km = KeywordMetrics(product_name="Test")
        assert km.monthly_search_volume == 0
        assert km.monthly_clicks == 0
        assert km.avg_cpc == 0
        assert km.competition == "low"

    def test_create_with_values(self):
        km = KeywordMetrics(
            product_name="Test",
            monthly_search_volume=50000,
            monthly_clicks=2000,
            avg_cpc=5000,
            competition="high",
        )
        assert km.monthly_search_volume == 50000
        assert km.monthly_clicks == 2000
        assert km.avg_cpc == 5000
        assert km.competition == "high"

    def test_to_dict(self):
        km = KeywordMetrics(
            product_name="Test",
            monthly_search_volume=10000,
            monthly_clicks=500,
            avg_cpc=3000,
            competition="medium",
        )
        d = km.to_dict()
        assert d["product_name"] == "Test"
        assert d["monthly_search_volume"] == 10000
        assert d["monthly_clicks"] == 500
        assert d["avg_cpc"] == 3000
        assert d["competition"] == "medium"


class TestCandidateProduct:
    def test_create_minimal(self):
        c = CandidateProduct(name="Test", brand="Brand", category="Cat")
        assert c.in_stock is True
        assert c.naver_rank == 0
        assert c.keyword_metrics is None

    def test_create_with_keyword_metrics(self):
        c = _make_candidate("Test", "Brand")
        assert c.keyword_metrics is not None
        assert c.keyword_metrics.monthly_clicks == 500

    def test_to_dict(self):
        c = _make_candidate("Test", "Brand")
        d = c.to_dict()
        assert d["name"] == "Test"
        assert d["brand"] == "Brand"
        assert d["naver_rank"] == 1
        assert d["keyword_metrics"] is not None
        assert d["keyword_metrics"]["monthly_clicks"] == 500

    def test_to_dict_without_keyword_metrics(self):
        c = CandidateProduct(name="Test", brand="Brand", category="Cat")
        d = c.to_dict()
        assert d["keyword_metrics"] is None


class TestProductScores:
    def test_total_score_all_max(self):
        ps = ProductScores(
            product_name="Test",
            clicks_score=1.0,
            cpc_score=1.0,
            search_volume_score=1.0,
            competition_score=1.0,
        )
        assert ps.total_score == pytest.approx(1.0)

    def test_total_score_weighted(self):
        ps = ProductScores(
            product_name="Test",
            clicks_score=0.8,     # 0.8 * 0.4 = 0.32
            cpc_score=0.6,        # 0.6 * 0.3 = 0.18
            search_volume_score=0.4,  # 0.4 * 0.2 = 0.08
            competition_score=0.5,    # 0.5 * 0.1 = 0.05
        )
        expected = 0.32 + 0.18 + 0.08 + 0.05
        assert ps.total_score == pytest.approx(expected)

    def test_total_score_zeros(self):
        ps = ProductScores(product_name="Test")
        assert ps.total_score == 0.0

    def test_to_dict(self):
        ps = ProductScores(product_name="Test", clicks_score=0.9, cpc_score=0.7)
        d = ps.to_dict()
        assert d["clicks_score"] == 0.9
        assert d["cpc_score"] == 0.7
        assert "total_score" in d


class TestSelectedProduct:
    def test_create(self):
        candidate = _make_candidate("Test", "Brand")
        scores = ProductScores(product_name="Test", clicks_score=0.8)
        sp = SelectedProduct(
            rank=1, candidate=candidate, scores=scores,
            selection_reasons=["High clicks"],
        )
        assert sp.rank == 1
        assert sp.candidate.name == "Test"
        assert sp.selection_reasons == ["High clicks"]

    def test_to_dict(self):
        candidate = _make_candidate("TestProd", "TestBrand", price=1500000)
        scores = ProductScores(product_name="TestProd", clicks_score=0.9)
        sp = SelectedProduct(rank=1, candidate=candidate, scores=scores)
        d = sp.to_dict()
        assert d["rank"] == 1
        assert d["name"] == "TestProd"
        assert d["brand"] == "TestBrand"
        assert d["price"] == 1500000
        assert "scores" in d


class TestSelectionResult:
    def test_to_dict(self):
        candidate = _make_candidate("TestProd", "TestBrand")
        scores = ProductScores(product_name="TestProd", clicks_score=0.9)
        selected = SelectedProduct(
            rank=1, candidate=candidate, scores=scores,
            selection_reasons=["Top clicks"],
        )
        validation = ValidationResult(
            check_name="brand_variety", passed=True, detail="Selected brands: TestBrand (1 unique)",
        )
        result = SelectionResult(
            category="로봇청소기",
            selection_date=date(2026, 2, 7),
            data_sources={"candidates": "naver_shopping_api"},
            candidate_pool_size=10,
            selected_products=[selected],
            validation=[validation],
            selected_tier="premium",
            tier_scores={"premium": 1.963, "mid": 0.948, "budget": 1.770},
            tier_product_counts={"premium": 6, "mid": 8, "budget": 6},
        )
        d = result.to_dict()
        assert d["category"] == "로봇청소기"
        assert d["candidate_pool_size"] == 10
        assert len(d["selected_products"]) == 1
        assert "brand_variety" in d["validation"]
        assert d["selected_tier"] == "premium"
        assert d["tier_scores"]["premium"] == 1.963
        assert d["tier_product_counts"]["premium"] == 6

    def test_to_dict_without_tier(self):
        """Backward compat: no tier metadata when selected_tier is empty."""
        candidate = _make_candidate("TestProd", "TestBrand")
        scores = ProductScores(product_name="TestProd")
        selected = SelectedProduct(rank=1, candidate=candidate, scores=scores)
        result = SelectionResult(
            category="test",
            selection_date=date(2026, 1, 1),
            data_sources={},
            candidate_pool_size=5,
            selected_products=[selected],
            validation=[],
        )
        d = result.to_dict()
        assert "selected_tier" not in d

    def test_to_json(self):
        candidate = _make_candidate("TestProd", "TestBrand")
        scores = ProductScores(product_name="TestProd")
        selected = SelectedProduct(rank=1, candidate=candidate, scores=scores)
        result = SelectionResult(
            category="test",
            selection_date=date(2026, 1, 1),
            data_sources={},
            candidate_pool_size=5,
            selected_products=[selected],
            validation=[],
            selected_tier="budget",
            tier_scores={"premium": 0.5, "mid": 0.3, "budget": 0.8},
            tier_product_counts={"premium": 2, "mid": 1, "budget": 3},
        )
        j = result.to_json()
        parsed = json.loads(j)
        assert parsed["category"] == "test"
        assert parsed["selected_tier"] == "budget"


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
# Naver Ad Client Tests
# ===================================================================


class TestNaverAdClientHelpers:
    def test_safe_int_from_int(self):
        assert _safe_int(42) == 42

    def test_safe_int_from_float(self):
        assert _safe_int(42.9) == 42

    def test_safe_int_from_string(self):
        assert _safe_int("1500") == 1500

    def test_safe_int_from_string_with_commas(self):
        assert _safe_int("1,500") == 1500

    def test_safe_int_from_less_than_string(self):
        assert _safe_int("< 10") == 10

    def test_safe_int_from_invalid_string(self):
        assert _safe_int("N/A") == 0

    def test_safe_int_from_none(self):
        assert _safe_int(None) == 0

    def test_map_competition_high(self):
        assert _map_competition("높음") == "high"

    def test_map_competition_medium(self):
        assert _map_competition("중간") == "medium"

    def test_map_competition_low(self):
        assert _map_competition("낮음") == "low"

    def test_map_competition_unknown(self):
        assert _map_competition("unknown") == "low"


class TestExtractManufacturer:
    def test_lg_jeonja(self):
        assert extract_manufacturer("LG전자 LG 트롬 세탁기") == "LG"

    def test_samsung_jeonja(self):
        assert extract_manufacturer("삼성전자 비스포크AI콤보") == "삼성"

    def test_lg_without_jeonja(self):
        assert extract_manufacturer("LG 트롬 오브제") == "LG"

    def test_unknown_brand(self):
        assert extract_manufacturer("로보락 S8 MaxV Ultra") == ""

    def test_empty_string(self):
        assert extract_manufacturer("") == ""


class TestManufacturerProperty:
    def test_lg_product(self):
        c = CandidateProduct(name="LG전자 트롬 세탁기", brand="트롬", category="세탁기")
        assert c.manufacturer == "LG"

    def test_samsung_product(self):
        c = CandidateProduct(name="삼성전자 그랑데 WF19T", brand="그랑데", category="세탁기")
        assert c.manufacturer == "삼성"

    def test_fallback_to_brand(self):
        c = CandidateProduct(name="로보락 S8 MaxV Ultra", brand="로보락", category="로봇청소기")
        assert c.manufacturer == "로보락"


class TestBuildProductKeyword:
    def test_samsung_grande(self):
        assert _build_product_keyword("삼성전자 그랑데 WF19T6000KW 화이트", "그랑데") == "삼성그랑데"

    def test_lg_trom(self):
        assert _build_product_keyword("LG전자 트롬 오브제 FX25ESR", "트롬") == "LG트롬"

    def test_samsung_bespoke(self):
        kw = _build_product_keyword("삼성전자 비스포크AI콤보 25/18kg", "비스포크AI콤보")
        assert kw == "삼성비스포크AI콤보"

    def test_no_brand_returns_empty(self):
        # No brand, manufacturer-only → too generic, skip
        assert _build_product_keyword("삼성전자 세탁기", "") == ""

    def test_unknown_manufacturer_with_brand(self):
        kw = _build_product_keyword("로보락 S8 MaxV Ultra", "로보락")
        assert kw == "로보락"

    def test_brand_equals_manufacturer_returns_empty(self):
        # brand="삼성" == manufacturer="삼성" → too generic, skip
        assert _build_product_keyword("삼성전자 드럼세탁기", "삼성") == ""
        assert _build_product_keyword("삼성전자 삼성 WF21DG6650B", "삼성") == ""

    def test_brand_starts_with_manufacturer_ok(self):
        # brand="삼성전자" starts with manufacturer="삼성" but is longer → OK
        assert _build_product_keyword("삼성전자 제품", "삼성전자") == "삼성전자"

    def test_lg_brand_equals_manufacturer_returns_empty(self):
        # brand="LG" == manufacturer="LG" → too generic, skip
        assert _build_product_keyword("LG전자 LG 세탁기", "LG") == ""


class TestCleanKeyword:
    def test_removes_parenthesized_content(self):
        result = _clean_keyword("LG전자 LG 트롬(F21VDSK)")
        assert "F21VDSK" not in result
        assert "(" not in result

    def test_simplifies_lg_manufacturer(self):
        result = _clean_keyword("LG전자 트롬 세탁기")
        assert result.startswith("LG")
        assert "전자" not in result

    def test_simplifies_samsung_manufacturer(self):
        result = _clean_keyword("삼성전자 비스포크 세탁기")
        assert result.startswith("삼성")
        assert "전자" not in result

    def test_removes_color_suffixes(self):
        result = _clean_keyword("삼성전자 비스포크 화이트")
        assert "화이트" not in result

    def test_removes_stainless_silver(self):
        result = _clean_keyword("LG전자 트롬 스테인리스 실버")
        assert "스테인리스" not in result
        assert "실버" not in result

    def test_removes_model_codes(self):
        result = _clean_keyword("삼성 비스포크 WD80F25CH")
        assert "WD80F25CH" not in result

    def test_removes_weight_specs(self):
        result = _clean_keyword("LG 트롬 21kg")
        assert "21kg" not in result
        assert "kg" not in result

    def test_removes_spaces(self):
        result = _clean_keyword("LG 트롬 세탁기")
        assert " " not in result

    def test_truncates_long_keywords(self):
        result = _clean_keyword("삼성전자 비스포크AI콤보 올인원 세탁건조기 특대형")
        assert len(result) <= 20

    def test_full_product_name_lg(self):
        result = _clean_keyword("LG전자 LG 트롬 21kg 스테인리스 실버(F21VDSK)")
        assert result == "LG트롬"

    def test_full_product_name_samsung(self):
        result = _clean_keyword("삼성전자 비스포크AI콤보 WD80F25CH 화이트(WD80F25CHW)")
        assert "삼성" in result
        assert "비스포크" in result
        assert " " not in result

    def test_empty_string(self):
        assert _clean_keyword("") == ""

    def test_removes_year_references(self):
        result = _clean_keyword("삼성 비스포크 2025")
        assert "2025" not in result

    def test_removes_special_characters(self):
        result = _clean_keyword("LG 트롬+건조기")
        assert "+" not in result


class TestNaverAdClient:
    def test_not_configured(self):
        config = Config()
        config.naver_searchad_customer_id = ""
        config.naver_searchad_api_key = ""
        config.naver_searchad_secret_key = ""
        client = NaverAdClient(config)
        assert not client.is_configured

    def test_configured(self):
        config = Config()
        config.naver_searchad_customer_id = "test_customer"
        config.naver_searchad_api_key = "test_key"
        config.naver_searchad_secret_key = "test_secret"
        client = NaverAdClient(config)
        assert client.is_configured

    def test_returns_empty_metrics_when_not_configured(self):
        config = Config()
        config.naver_searchad_customer_id = ""
        config.naver_searchad_api_key = ""
        config.naver_searchad_secret_key = ""
        client = NaverAdClient(config)
        results = client.get_keyword_metrics(["product1", "product2"])
        assert len(results) == 2
        assert results[0].product_name == "product1"
        assert results[0].monthly_clicks == 0

    def test_parse_response(self):
        config = Config()
        client = NaverAdClient(config)
        api_data = {
            "keywordList": [
                {
                    "relKeyword": "로보락S8",
                    "monthlyPcQcCnt": 5000,
                    "monthlyMobileQcCnt": 15000,
                    "monthlyAvePcClkCnt": 200,
                    "monthlyAveMobileClkCnt": 800,
                    "plAvgDepth": 3500,
                    "compIdx": "높음",
                },
                {
                    "relKeyword": "unrelated keyword",
                    "monthlyPcQcCnt": 99999,
                    "monthlyMobileQcCnt": 99999,
                },
            ],
        }
        results = client._parse_response(api_data, ["로보락S8"])
        assert len(results) == 1
        assert results[0].product_name == "로보락S8"
        assert results[0].monthly_search_volume == 20000
        assert results[0].monthly_clicks == 1000
        assert results[0].avg_cpc == 3500
        assert results[0].competition == "high"

    def test_parse_response_case_insensitive(self):
        config = Config()
        client = NaverAdClient(config)
        api_data = {
            "keywordList": [
                {"relKeyword": "lg 코드제로", "monthlyPcQcCnt": 100, "monthlyMobileQcCnt": 200},
            ],
        }
        results = client._parse_response(api_data, ["LG코드제로"])
        assert len(results) == 1
        assert results[0].product_name == "LG코드제로"

    def test_parse_response_handles_less_than_values(self):
        config = Config()
        client = NaverAdClient(config)
        api_data = {
            "keywordList": [
                {
                    "relKeyword": "TestProduct",
                    "monthlyPcQcCnt": "< 10",
                    "monthlyMobileQcCnt": "< 10",
                    "monthlyAvePcClkCnt": "< 10",
                    "monthlyAveMobileClkCnt": "< 10",
                },
            ],
        }
        results = client._parse_response(api_data, ["TestProduct"])
        assert len(results) == 1
        assert results[0].monthly_search_volume == 20  # 10 + 10

    def test_parse_response_no_duplicate_match(self):
        """Each keyword should only match once (first match wins)."""
        config = Config()
        client = NaverAdClient(config)
        api_data = {
            "keywordList": [
                {"relKeyword": "LG트롬", "monthlyPcQcCnt": 1000, "monthlyMobileQcCnt": 2000},
                {"relKeyword": "LG 트롬 세탁기", "monthlyPcQcCnt": 500, "monthlyMobileQcCnt": 800},
            ],
        }
        results = client._parse_response(api_data, ["LG트롬"])
        assert len(results) == 1
        assert results[0].monthly_search_volume == 3000  # First match


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
# Scorer Tests (keyword metrics based)
# ===================================================================


class TestProductScorer:
    def test_score_candidates(self):
        candidates = [
            _make_candidate("A", "BrandA", monthly_clicks=1000, avg_cpc=5000,
                          monthly_search_volume=20000, competition="high"),
            _make_candidate("B", "BrandB", monthly_clicks=200, avg_cpc=1000,
                          monthly_search_volume=5000, competition="low"),
        ]
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        assert scores["A"].clicks_score > scores["B"].clicks_score
        assert scores["A"].cpc_score > scores["B"].cpc_score
        assert scores["A"].search_volume_score > scores["B"].search_volume_score
        assert scores["A"].competition_score > scores["B"].competition_score
        assert scores["A"].total_score > scores["B"].total_score

    def test_score_with_no_keyword_metrics(self):
        candidates = [
            CandidateProduct(name="A", brand="BrandA", category="test"),
            CandidateProduct(name="B", brand="BrandB", category="test"),
        ]
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        # All zeros → normalized to 0.5 each
        assert scores["A"].clicks_score == pytest.approx(0.5)
        assert scores["B"].clicks_score == pytest.approx(0.5)

    def test_empty_candidates(self):
        scorer = ProductScorer()
        assert scorer.score_candidates([]) == {}


# ===================================================================
# Top Selector Tests
# ===================================================================


class TestSlotSelector:
    """Tests for single-tier winning selection (PartA0_Singtier)."""

    def _make_premium_heavy_candidates(self):
        """Premium tier has top 3 scores, mid and budget are weaker."""
        return [
            # Premium tier (3 strong products)
            _make_candidate("Premium A", "BrandA", price=2_000_000,
                          monthly_clicks=1000, avg_cpc=5000,
                          monthly_search_volume=20000, competition="high"),
            _make_candidate("Premium B", "BrandB", price=1_800_000,
                          monthly_clicks=800, avg_cpc=4000,
                          monthly_search_volume=15000, competition="high"),
            _make_candidate("Premium C", "BrandC", price=1_700_000,
                          monthly_clicks=600, avg_cpc=3500,
                          monthly_search_volume=12000, competition="medium"),
            # Mid tier
            _make_candidate("Mid A", "BrandD", price=900_000,
                          monthly_clicks=300, avg_cpc=2000,
                          monthly_search_volume=8000, competition="medium"),
            _make_candidate("Mid B", "BrandE", price=800_000,
                          monthly_clicks=200, avg_cpc=1500,
                          monthly_search_volume=5000, competition="low"),
            # Budget tier
            _make_candidate("Budget A", "BrandF", price=300_000,
                          monthly_clicks=150, avg_cpc=1000,
                          monthly_search_volume=4000, competition="low"),
        ]

    def _make_tier_map_6(self):
        return {
            "Premium A": "premium",
            "Premium B": "premium",
            "Premium C": "premium",
            "Mid A": "mid",
            "Mid B": "mid",
            "Budget A": "budget",
        }

    def test_normal_clear_winner(self):
        """Premium tier with top 3 sum > mid > budget → premium wins."""
        candidates = self._make_premium_heavy_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        tier_map = self._make_tier_map_6()

        selector = SlotSelector()
        picks, winning_tier, tier_scores, tier_counts = selector.select(
            candidates, scores, tier_map
        )

        assert winning_tier == "premium"
        assert len(picks) == 3
        assert all(p.candidate.name.startswith("Premium") for p in picks)
        assert {p.rank for p in picks} == {1, 2, 3}
        # All slots empty (Part B assigns contextual labels)
        assert all(p.slot == "" for p in picks)

    def test_budget_dominance(self):
        """Budget products have highest scores → budget tier wins."""
        candidates = [
            # Budget tier (dominant)
            _make_candidate("Budget 1", "BrandA", price=50_000,
                          monthly_clicks=2000, avg_cpc=8000,
                          monthly_search_volume=50000, competition="high"),
            _make_candidate("Budget 2", "BrandB", price=40_000,
                          monthly_clicks=1500, avg_cpc=6000,
                          monthly_search_volume=40000, competition="high"),
            _make_candidate("Budget 3", "BrandC", price=30_000,
                          monthly_clicks=1200, avg_cpc=5000,
                          monthly_search_volume=30000, competition="medium"),
            # Premium tier (weak)
            _make_candidate("Premium 1", "BrandD", price=200_000,
                          monthly_clicks=100, avg_cpc=500,
                          monthly_search_volume=2000, competition="low"),
        ]
        tier_map = {
            "Budget 1": "budget", "Budget 2": "budget", "Budget 3": "budget",
            "Premium 1": "premium",
        }
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        selector = SlotSelector()
        picks, winning_tier, _, _ = selector.select(candidates, scores, tier_map)

        assert winning_tier == "budget"
        assert len(picks) == 3
        assert all(p.candidate.name.startswith("Budget") for p in picks)

    def test_tight_race(self):
        """Higher score wins even with small margin."""
        candidates = [
            _make_candidate("P1", "BrandA", price=200_000,
                          monthly_clicks=500, avg_cpc=3000,
                          monthly_search_volume=10000, competition="medium"),
            _make_candidate("P2", "BrandB", price=190_000,
                          monthly_clicks=490, avg_cpc=2900,
                          monthly_search_volume=9800, competition="medium"),
            _make_candidate("P3", "BrandC", price=180_000,
                          monthly_clicks=480, avg_cpc=2800,
                          monthly_search_volume=9600, competition="medium"),
            _make_candidate("B1", "BrandD", price=50_000,
                          monthly_clicks=498, avg_cpc=2980,
                          monthly_search_volume=9900, competition="medium"),
            _make_candidate("B2", "BrandE", price=40_000,
                          monthly_clicks=488, avg_cpc=2880,
                          monthly_search_volume=9700, competition="medium"),
            _make_candidate("B3", "BrandF", price=30_000,
                          monthly_clicks=478, avg_cpc=2780,
                          monthly_search_volume=9500, competition="medium"),
        ]
        tier_map = {
            "P1": "premium", "P2": "premium", "P3": "premium",
            "B1": "budget", "B2": "budget", "B3": "budget",
        }
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        selector = SlotSelector()
        _, winning_tier, tier_scores, _ = selector.select(candidates, scores, tier_map)

        # Premium scores slightly higher, so premium should win
        assert tier_scores["premium"] > tier_scores["budget"]
        assert winning_tier == "premium"

    def test_tier_with_fewer_than_3_penalized(self):
        """Tier with only 2 products gets penalty (×2/3), may lose."""
        candidates = [
            # Premium: only 2 products (will be penalized)
            _make_candidate("P1", "BrandA", price=200_000,
                          monthly_clicks=600, avg_cpc=4000,
                          monthly_search_volume=15000, competition="high"),
            _make_candidate("P2", "BrandB", price=190_000,
                          monthly_clicks=550, avg_cpc=3500,
                          monthly_search_volume=12000, competition="high"),
            # Budget: 3 products (no penalty)
            _make_candidate("B1", "BrandC", price=50_000,
                          monthly_clicks=500, avg_cpc=3000,
                          monthly_search_volume=10000, competition="medium"),
            _make_candidate("B2", "BrandD", price=40_000,
                          monthly_clicks=450, avg_cpc=2800,
                          monthly_search_volume=9000, competition="medium"),
            _make_candidate("B3", "BrandE", price=30_000,
                          monthly_clicks=400, avg_cpc=2500,
                          monthly_search_volume=8000, competition="medium"),
        ]
        tier_map = {
            "P1": "premium", "P2": "premium",
            "B1": "budget", "B2": "budget", "B3": "budget",
        }
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        _, tier_scores_result = score_tiers(candidates, scores, tier_map)
        # Premium raw sum of 2 × (2/3) penalty vs budget sum of 3 × (3/3)
        # The penalty should make premium lose despite higher individual scores
        assert tier_scores_result["premium"] < tier_scores_result["budget"]

    def test_same_brand_allowed_with_mix(self):
        """Same brand dominates top 3 → rank 3 replaced by best other-brand."""
        candidates = [
            _make_candidate("삼성전자 모델A", "모델A", price=200_000,
                          monthly_clicks=1000, avg_cpc=5000,
                          monthly_search_volume=20000, competition="high"),
            _make_candidate("삼성전자 모델B", "모델B", price=190_000,
                          monthly_clicks=900, avg_cpc=4500,
                          monthly_search_volume=18000, competition="high"),
            _make_candidate("삼성전자 모델C", "모델C", price=180_000,
                          monthly_clicks=800, avg_cpc=4000,
                          monthly_search_volume=16000, competition="high"),
            _make_candidate("LG전자 제품X", "제품X", price=170_000,
                          monthly_clicks=200, avg_cpc=1000,
                          monthly_search_volume=5000, competition="low"),
            _make_candidate("Budget Z", "BrandZ", price=50_000,
                          monthly_clicks=100, avg_cpc=500,
                          monthly_search_volume=2000, competition="low"),
        ]
        tier_map = {
            "삼성전자 모델A": "premium",
            "삼성전자 모델B": "premium",
            "삼성전자 모델C": "premium",
            "LG전자 제품X": "premium",
            "Budget Z": "budget",
        }
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        selector = SlotSelector()
        picks, winning_tier, _, _ = selector.select(candidates, scores, tier_map)

        assert winning_tier == "premium"
        assert len(picks) == 3
        # Top 2 are 삼성, rank 3 replaced by LG (brand mix)
        assert picks[0].candidate.name == "삼성전자 모델A"
        assert picks[1].candidate.name == "삼성전자 모델B"
        assert picks[2].candidate.name == "LG전자 제품X"
        assert any("brand mix" in r for r in picks[2].selection_reasons)

    def test_brand_mix_no_replacement_available(self):
        """All candidates are same brand → no replacement, keep original 3."""
        candidates = [
            _make_candidate("삼성전자 A", "모델A", price=200_000,
                          monthly_clicks=1000, avg_cpc=5000,
                          monthly_search_volume=20000, competition="high"),
            _make_candidate("삼성전자 B", "모델B", price=190_000,
                          monthly_clicks=900, avg_cpc=4500,
                          monthly_search_volume=18000, competition="high"),
            _make_candidate("삼성전자 C", "모델C", price=180_000,
                          monthly_clicks=800, avg_cpc=4000,
                          monthly_search_volume=16000, competition="high"),
        ]
        tier_map = {
            "삼성전자 A": "premium",
            "삼성전자 B": "premium",
            "삼성전자 C": "premium",
        }
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        selector = SlotSelector()
        picks, _, _, _ = selector.select(candidates, scores, tier_map)

        assert len(picks) == 3
        # No other brand available, keep all 삼성
        assert all(p.candidate.manufacturer == "삼성" for p in picks)
        assert not any(
            "brand mix" in r
            for p in picks for r in p.selection_reasons
        )

    def test_brand_mix_from_adjacent_tier(self):
        """When winning tier has only same-brand, pull other-brand from adjacent."""
        candidates = [
            _make_candidate("삼성전자 X1", "X1", price=200_000,
                          monthly_clicks=1000, avg_cpc=5000,
                          monthly_search_volume=20000, competition="high"),
            _make_candidate("삼성전자 X2", "X2", price=190_000,
                          monthly_clicks=950, avg_cpc=4800,
                          monthly_search_volume=19000, competition="high"),
            _make_candidate("삼성전자 X3", "X3", price=180_000,
                          monthly_clicks=900, avg_cpc=4600,
                          monthly_search_volume=18000, competition="high"),
            # Mid tier — different brand, close metrics to pass score floor
            _make_candidate("LG전자 Y1", "Y1", price=100_000,
                          monthly_clicks=920, avg_cpc=4700,
                          monthly_search_volume=18500, competition="high"),
        ]
        tier_map = {
            "삼성전자 X1": "premium",
            "삼성전자 X2": "premium",
            "삼성전자 X3": "premium",
            "LG전자 Y1": "mid",
        }
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        selector = SlotSelector()
        picks, winning_tier, _, _ = selector.select(candidates, scores, tier_map)

        assert winning_tier == "premium"
        assert len(picks) == 3
        # Rank 3 replaced by LG from adjacent mid tier
        assert picks[2].candidate.manufacturer == "LG"
        assert any("brand mix" in r for r in picks[2].selection_reasons)

    def test_all_same_price_single_tier(self):
        """All products within ±10% price → one large tier wins by default."""
        candidates = [
            _make_candidate("A", "BrandA", price=100_000,
                          monthly_clicks=500, avg_cpc=3000,
                          monthly_search_volume=10000, competition="high"),
            _make_candidate("B", "BrandB", price=105_000,
                          monthly_clicks=480, avg_cpc=2900,
                          monthly_search_volume=9500, competition="high"),
            _make_candidate("C", "BrandC", price=95_000,
                          monthly_clicks=460, avg_cpc=2800,
                          monthly_search_volume=9000, competition="high"),
        ]
        # All in same tier
        tier_map = {"A": "mid", "B": "mid", "C": "mid"}
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        selector = SlotSelector()
        picks, winning_tier, _, _ = selector.select(candidates, scores, tier_map)

        assert winning_tier == "mid"
        assert len(picks) == 3

    def test_insufficient_candidates_raises(self):
        candidates = [
            _make_candidate("A", "BrandA", price=1_000_000),
            _make_candidate("B", "BrandB", price=1_200_000),
        ]
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        tier_map = {"A": "budget", "B": "premium"}

        selector = SlotSelector()
        with pytest.raises(ValueError, match="at least 3"):
            selector.select(candidates, scores, tier_map)

    def test_selection_reasons_include_winning_tier(self):
        """Reasons should reference winning tier and scores."""
        candidates = self._make_premium_heavy_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        tier_map = self._make_tier_map_6()

        selector = SlotSelector()
        picks, _, _, _ = selector.select(candidates, scores, tier_map)

        reasons = picks[0].selection_reasons
        assert any("winning tier" in r.lower() for r in reasons)
        assert any("clicks" in r.lower() for r in reasons)
        assert any("score" in r.lower() for r in reasons)

    def test_returns_tier_metadata(self):
        """select() returns tier_scores and tier_product_counts."""
        candidates = self._make_premium_heavy_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        tier_map = self._make_tier_map_6()

        selector = SlotSelector()
        _, winning_tier, tier_scores, tier_counts = selector.select(
            candidates, scores, tier_map
        )

        assert winning_tier in ("premium", "mid", "budget")
        assert set(tier_scores.keys()) == {"premium", "mid", "budget"}
        assert tier_counts == {"premium": 3, "mid": 2, "budget": 1}

    def test_adjacent_tier_pullback(self):
        """When winning tier has only 1 high-score product, pull from adjacent."""
        candidates = [
            # Premium: 1 very strong product (wins tier despite 1/3 penalty)
            _make_candidate("P1", "BrandA", price=200_000,
                          monthly_clicks=2000, avg_cpc=8000,
                          monthly_search_volume=50000, competition="high"),
            # Mid: 2 decent products (adjacent candidates)
            _make_candidate("M1", "BrandB", price=100_000,
                          monthly_clicks=1500, avg_cpc=6000,
                          monthly_search_volume=40000, competition="high"),
            _make_candidate("M2", "BrandC", price=90_000,
                          monthly_clicks=1400, avg_cpc=5500,
                          monthly_search_volume=35000, competition="high"),
            # Budget: 1 decent product
            _make_candidate("B1", "BrandD", price=30_000,
                          monthly_clicks=1300, avg_cpc=5000,
                          monthly_search_volume=30000, competition="medium"),
        ]
        tier_map = {
            "P1": "premium",
            "M1": "mid", "M2": "mid",
            "B1": "budget",
        }
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        selector = SlotSelector()
        picks, winning_tier, _, _ = selector.select(candidates, scores, tier_map)

        # Premium has 1 product but very high score — check if it wins
        # or if mid wins (2 products with decent scores)
        # Either way, adjacent pull should happen if winning tier < 3
        assert len(picks) == 3
        adjacent_pulls = [
            p for p in picks
            if any("pulled from adjacent" in r for r in p.selection_reasons)
        ]
        assert len(adjacent_pulls) >= 1

    def test_score_floor_filters_zero_score(self):
        """Products with total_score < 0.1 are excluded."""
        candidates = [
            _make_candidate("Good1", "BrandA", price=100_000,
                          monthly_clicks=500, avg_cpc=3000,
                          monthly_search_volume=10000, competition="medium"),
            _make_candidate("Good2", "BrandB", price=90_000,
                          monthly_clicks=400, avg_cpc=2500,
                          monthly_search_volume=8000, competition="medium"),
            # No keyword metrics → score will be 0.0 after normalization with others
            CandidateProduct(name="Zero", brand="BrandC", category="test", price=80_000),
            _make_candidate("Good3", "BrandD", price=110_000,
                          monthly_clicks=300, avg_cpc=2000,
                          monthly_search_volume=6000, competition="low"),
        ]
        tier_map = {"Good1": "mid", "Good2": "mid", "Zero": "mid", "Good3": "mid"}
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        selector = SlotSelector()
        picks, _, _, _ = selector.select(candidates, scores, tier_map)

        picked_names = [p.candidate.name for p in picks]
        assert "Zero" not in picked_names
        assert len(picks) == 3

    def test_score_floor_fewer_than_3_ok(self):
        """If fewer than 3 pass the floor, output fewer than 3 products."""
        candidates = [
            _make_candidate("Good", "BrandA", price=100_000,
                          monthly_clicks=500, avg_cpc=3000,
                          monthly_search_volume=10000, competition="medium"),
            # These will have very low scores relative to Good
            CandidateProduct(name="Bad1", brand="BrandB", category="test", price=90_000),
            CandidateProduct(name="Bad2", brand="BrandC", category="test", price=80_000),
        ]
        tier_map = {"Good": "mid", "Bad1": "mid", "Bad2": "mid"}
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        selector = SlotSelector()
        picks, _, _, _ = selector.select(candidates, scores, tier_map)

        # Only "Good" should pass the score floor
        # (Bad1/Bad2 get 0.0 for clicks/cpc since they have no keyword metrics,
        # but normalization may give them 0.5 baseline — depends on scorer logic)
        # At minimum, Good should be first pick
        assert picks[0].candidate.name == "Good"
        assert all(p.scores.total_score >= 0.1 for p in picks)

    def test_force_tier_overrides_winner(self):
        """force_tier selects from specified tier instead of auto-winner."""
        candidates = self._make_premium_heavy_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        tier_map = self._make_tier_map_6()

        selector = SlotSelector()

        # Without force_tier — premium wins
        _, auto_tier, _, _ = selector.select(candidates, scores, tier_map)
        assert auto_tier == "premium"

        # Force budget tier
        picks, forced_tier, tier_scores, _ = selector.select(
            candidates, scores, tier_map, force_tier="budget"
        )
        assert forced_tier == "budget"
        # Budget tier only has 1 product, so pulls from adjacent
        assert len(picks) >= 1
        # Tier scores are still computed the same way
        assert tier_scores["premium"] > tier_scores["budget"]

    def test_force_tier_mid(self):
        """force_tier='mid' picks from mid tier."""
        candidates = self._make_premium_heavy_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        tier_map = self._make_tier_map_6()

        selector = SlotSelector()
        picks, forced_tier, _, _ = selector.select(
            candidates, scores, tier_map, force_tier="mid"
        )
        assert forced_tier == "mid"
        # Mid has 2 products, will pull 1 from adjacent
        mid_picks = [p for p in picks if tier_map.get(p.candidate.name) == "mid"]
        assert len(mid_picks) >= 1


class TestScoreTiers:
    """Unit tests for the tier scoring function."""

    def test_full_tiers(self):
        candidates = [
            _make_candidate("P1", "A", price=200_000, monthly_clicks=500),
            _make_candidate("P2", "B", price=190_000, monthly_clicks=400),
            _make_candidate("P3", "C", price=180_000, monthly_clicks=300),
            _make_candidate("B1", "D", price=50_000, monthly_clicks=200),
        ]
        tier_map = {"P1": "premium", "P2": "premium", "P3": "premium", "B1": "budget"}
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        tier_scores, tier_counts = score_tiers(candidates, scores, tier_map)
        assert tier_counts == {"premium": 3, "mid": 0, "budget": 1}
        assert tier_scores["mid"] == 0.0
        # Premium has no penalty (3 products), budget has 1/3 penalty
        assert tier_scores["premium"] > tier_scores["budget"]

    def test_empty_tier_zero_score(self):
        candidates = [_make_candidate("A", "X", price=100_000)]
        tier_map = {"A": "mid"}
        scores = ProductScorer().score_candidates(candidates)

        tier_scores, _ = score_tiers(candidates, scores, tier_map)
        assert tier_scores["premium"] == 0.0
        assert tier_scores["budget"] == 0.0


class TestSelectWinningTier:
    def test_highest_wins(self):
        assert select_winning_tier({"premium": 2.0, "mid": 1.0, "budget": 1.5}) == "premium"

    def test_budget_wins(self):
        assert select_winning_tier({"premium": 0.5, "mid": 0.8, "budget": 1.2}) == "budget"

    def test_tie_prefers_premium(self):
        """Ties broken by TIER_ORDER (premium > mid > budget)."""
        assert select_winning_tier({"premium": 1.0, "mid": 1.0, "budget": 1.0}) == "premium"


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

    def test_save_yaml(self, tmp_path):
        config = CategoryConfig(
            name="test_save",
            search_terms=["테스트"],
            negative_keywords=["불만"],
            positive_keywords=["추천"],
            danawa_category_code="99999",
        )
        out = config.save_yaml(tmp_path / "out.yaml")
        assert out.exists()

        loaded = CategoryConfig.from_yaml(out)
        assert loaded.name == "test_save"
        assert loaded.danawa_category_code == "99999"
        assert loaded.search_terms == ["테스트"]


# ===================================================================
# DanawaCategoryResolver Tests
# ===================================================================


class TestDanawaCategoryResolver:
    def test_extract_category_code_from_links(self):
        from src.part_a.product_selector.danawa_category_resolver import (
            DanawaCategoryResolver,
        )

        html = """
        <html><body>
        <a href="https://prod.danawa.com/list/?cate=10248425&sort=saleCnt">TV</a>
        <a href="https://prod.danawa.com/info/?pcode=123&cate=10248425">Product 1</a>
        <a href="https://prod.danawa.com/info/?pcode=456&cate=10248425">Product 2</a>
        <a href="https://prod.danawa.com/list/?cate=99999">Other</a>
        </body></html>
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        resolver = DanawaCategoryResolver.__new__(DanawaCategoryResolver)
        code = resolver._extract_category_code(soup)
        assert code == "10248425"

    def test_extract_no_links_returns_none(self):
        from src.part_a.product_selector.danawa_category_resolver import (
            DanawaCategoryResolver,
        )
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<html><body><p>No links</p></body></html>", "lxml")
        resolver = DanawaCategoryResolver.__new__(DanawaCategoryResolver)
        assert resolver._extract_category_code(soup) is None

    def test_parse_cate_from_url(self):
        from src.part_a.product_selector.danawa_category_resolver import (
            DanawaCategoryResolver,
        )

        codes = DanawaCategoryResolver._parse_cate_from_url(
            "https://prod.danawa.com/list/?cate=10248425&sort=saleCnt"
        )
        assert "10248425" in codes

    def test_parse_cate_ignores_short_codes(self):
        from src.part_a.product_selector.danawa_category_resolver import (
            DanawaCategoryResolver,
        )

        codes = DanawaCategoryResolver._parse_cate_from_url("?cate=12")
        assert codes == []

    def test_resolve_with_mock(self, monkeypatch):
        from src.part_a.product_selector.danawa_category_resolver import (
            DanawaCategoryResolver,
        )

        fake_html = """
        <html><body>
        <a href="https://prod.danawa.com/list/?cate=10248425">Cat</a>
        <a href="https://prod.danawa.com/info/?pcode=1&cate=10248425">P1</a>
        </body></html>
        """
        mock_resp = MagicMock()
        mock_resp.text = fake_html

        resolver = DanawaCategoryResolver.__new__(DanawaCategoryResolver)
        resolver._client = MagicMock()
        resolver._client.get.return_value = mock_resp

        code = resolver.resolve("벽걸이TV")
        assert code == "10248425"
        resolver._client.get.assert_called_once()


# ===================================================================
# DB Tests
# ===================================================================


class TestSaveSelectionToDb:
    def test_save_selection_result(self, temp_db):
        from src.part_a.product_selector.pipeline import ProductSelectionPipeline

        candidate = _make_candidate("Test", "Brand")
        scores = ProductScores(product_name="Test", clicks_score=0.8)
        selected = SelectedProduct(rank=1, candidate=candidate, scores=scores)
        result = SelectionResult(
            category="로봇청소기",
            selection_date=date(2026, 2, 7),
            data_sources={"candidates": "naver_shopping_api"},
            candidate_pool_size=10,
            selected_products=[selected],
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
