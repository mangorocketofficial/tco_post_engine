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
    ResaleQuickCheck,
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
from src.part_a.product_selector.slot_selector import TopSelector

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
            check_name="brand_diversity", passed=True, detail="3 unique brands",
        )
        result = SelectionResult(
            category="로봇청소기",
            selection_date=date(2026, 2, 7),
            data_sources={"candidates": "naver_shopping_api"},
            candidate_pool_size=10,
            selected_products=[selected],
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
        selected = SelectedProduct(rank=1, candidate=candidate, scores=scores)
        result = SelectionResult(
            category="test",
            selection_date=date(2026, 1, 1),
            data_sources={},
            candidate_pool_size=5,
            selected_products=[selected],
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


class TestTopSelector:
    def _make_3_candidates(self):
        return [
            _make_candidate("High Score", "BrandA",
                          monthly_clicks=1000, avg_cpc=5000,
                          monthly_search_volume=20000, competition="high"),
            _make_candidate("Mid Score", "BrandB",
                          monthly_clicks=500, avg_cpc=3000,
                          monthly_search_volume=10000, competition="medium"),
            _make_candidate("Low Score", "BrandC",
                          monthly_clicks=100, avg_cpc=1000,
                          monthly_search_volume=3000, competition="low"),
        ]

    def test_select_3_products(self):
        candidates = self._make_3_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        selector = TopSelector()
        picks = selector.select(candidates, scores)

        assert len(picks) == 3
        ranks = {p.rank for p in picks}
        assert ranks == {1, 2, 3}

    def test_rank_order_by_score(self):
        candidates = self._make_3_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        selector = TopSelector()
        picks = selector.select(candidates, scores)

        # Highest score should be rank 1
        assert picks[0].rank == 1
        assert picks[0].candidate.name == "High Score"
        assert picks[1].rank == 2
        assert picks[1].candidate.name == "Mid Score"
        assert picks[2].rank == 3
        assert picks[2].candidate.name == "Low Score"

    def test_brand_diversity_enforcement(self):
        # Two products from same manufacturer (삼성전자)
        candidates = [
            _make_candidate("삼성전자 비스포크 Top", "비스포크",
                          monthly_clicks=1000, avg_cpc=5000),
            _make_candidate("삼성전자 그랑데 Second", "그랑데",
                          monthly_clicks=900, avg_cpc=4500),
            _make_candidate("LG전자 트롬 Product", "트롬",
                          monthly_clicks=500, avg_cpc=3000),
            _make_candidate("위니아 Product", "위니아",
                          monthly_clicks=200, avg_cpc=1000),
        ]
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        selector = TopSelector()
        picks = selector.select(candidates, scores)

        assert len(picks) == 3
        # manufacturer diversity: should have 삼성, LG, 위니아
        manufacturers = [p.candidate.manufacturer for p in picks]
        assert len(set(manufacturers)) == 3

    def test_brand_diversity_relaxed_when_needed(self):
        # Only 2 unique manufacturers but need 3 picks
        candidates = [
            _make_candidate("삼성전자 A1", "비스포크", monthly_clicks=1000),
            _make_candidate("삼성전자 A2", "그랑데", monthly_clicks=800),
            _make_candidate("LG전자 B1", "트롬", monthly_clicks=500),
        ]
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        selector = TopSelector()
        picks = selector.select(candidates, scores)

        assert len(picks) == 3
        # Should have relaxed brand constraint for 3rd pick
        relaxed = [p for p in picks if "(brand diversity relaxed)" in p.selection_reasons]
        assert len(relaxed) == 1

    def test_insufficient_candidates_raises(self):
        candidates = [
            _make_candidate("A", "BrandA"),
            _make_candidate("B", "BrandB"),
        ]
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        selector = TopSelector()
        with pytest.raises(ValueError, match="at least 3"):
            selector.select(candidates, scores)

    def test_selection_reasons_include_metrics(self):
        candidates = self._make_3_candidates()
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        selector = TopSelector()
        picks = selector.select(candidates, scores)

        # First pick should have keyword metric reasons
        reasons = picks[0].selection_reasons
        assert any("clicks" in r.lower() for r in reasons)
        assert any("score" in r.lower() for r in reasons)


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
