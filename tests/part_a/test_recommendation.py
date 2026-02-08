"""Tests for A-0.1 Blog Recommendation Pipeline.

Tests cover:
- BlogSearchResult / ProductMention / RecommendationResult models
- BlogRecommendationScraper (Naver Blog API + Google SerpAPI)
- ProductNameExtractor (DeepSeek wrapper)
- RecommendationPipeline (full orchestration)
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.part_a.product_selector.blog_recommendation_scraper import (
    BlogRecommendationScraper,
)
from src.part_a.product_selector.models import (
    BlogSearchResult,
    ProductMention,
    RecommendationResult,
)
from src.part_a.product_selector.product_name_extractor import ProductNameExtractor
from src.part_a.product_selector.recommendation_pipeline import RecommendationPipeline


# ======================================================================
# Model tests
# ======================================================================


class TestBlogSearchResult:
    def test_create(self):
        r = BlogSearchResult(
            title="가성비 드럼세탁기 추천 TOP5",
            snippet="LG 트롬 오브제컬렉션이 가장 좋습니다...",
            link="https://blog.naver.com/test/123",
            source="naver",
            rank=1,
        )
        assert r.title == "가성비 드럼세탁기 추천 TOP5"
        assert r.source == "naver"
        assert r.rank == 1

    def test_to_dict(self):
        r = BlogSearchResult(
            title="Test", snippet="Snippet", link="https://example.com",
            source="google", rank=5,
        )
        d = r.to_dict()
        assert d["source"] == "google"
        assert d["rank"] == 5
        assert "link" in d


class TestProductMention:
    def test_create(self):
        m = ProductMention(
            product_name="LG 트롬 오브제컬렉션 FX25KSR",
            normalized_name="lg 트롬 오브제컬렉션 fx25ksr",
            mention_count=7,
            sources=["https://blog.naver.com/1", "https://blog.naver.com/2"],
        )
        assert m.mention_count == 7
        assert len(m.sources) == 2

    def test_to_dict(self):
        m = ProductMention(
            product_name="삼성 그랑데 AI",
            normalized_name="삼성 그랑데 ai",
            mention_count=5,
        )
        d = m.to_dict()
        assert d["product_name"] == "삼성 그랑데 AI"
        assert d["mention_count"] == 5
        assert d["sources"] == []

    def test_default_sources_empty(self):
        m = ProductMention("A", "a", 1)
        assert m.sources == []


class TestRecommendationResult:
    def test_create(self):
        r = RecommendationResult(
            keyword="드럼세탁기",
            search_query="가성비 드럼세탁기",
            total_blogs_searched=100,
            total_products_extracted=200,
            top_products=[
                ProductMention("LG 트롬", "lg 트롬", 12),
                ProductMention("삼성 그랑데", "삼성 그랑데", 8),
            ],
            search_date="2026-02-08T12:00:00",
        )
        assert r.keyword == "드럼세탁기"
        assert len(r.top_products) == 2
        assert r.top_products[0].mention_count == 12

    def test_to_dict(self):
        r = RecommendationResult(
            keyword="로봇청소기",
            search_query="가성비 로봇청소기",
            total_blogs_searched=50,
            total_products_extracted=60,
            top_products=[ProductMention("로보락 S8", "로보락 s8", 10)],
            search_date="2026-02-08",
        )
        d = r.to_dict()
        assert d["keyword"] == "로봇청소기"
        assert d["total_blogs_searched"] == 50
        assert len(d["top_products"]) == 1

    def test_to_json(self):
        r = RecommendationResult(
            keyword="TV",
            search_query="가성비 TV",
            total_blogs_searched=10,
            total_products_extracted=20,
            top_products=[],
            search_date="2026-02-08",
        )
        j = r.to_json()
        assert '"keyword": "TV"' in j


# ======================================================================
# BlogRecommendationScraper tests
# ======================================================================


class TestBlogRecommendationScraper:

    # -- No-key graceful degradation --

    @patch.dict(os.environ, {"SERPAPI_KEY": "", "NAVER_CLIENT_ID": "", "NAVER_CLIENT_SECRET": ""}, clear=False)
    def test_no_keys_returns_empty(self):
        scraper = BlogRecommendationScraper(serpapi_key="", naver_client_id="", naver_client_secret="")
        results = scraper.search_all("드럼세탁기")
        assert results == []

    @patch.dict(os.environ, {"NAVER_CLIENT_ID": "", "NAVER_CLIENT_SECRET": ""}, clear=False)
    def test_search_naver_no_key(self):
        scraper = BlogRecommendationScraper(naver_client_id="", naver_client_secret="")
        assert scraper.search_naver("test") == []

    @patch.dict(os.environ, {"SERPAPI_KEY": ""}, clear=False)
    def test_search_google_no_key(self):
        scraper = BlogRecommendationScraper(serpapi_key="")
        assert scraper.search_google("test") == []

    # -- Naver Blog API tests --

    @patch.object(BlogRecommendationScraper, "_fetch_naver_page")
    def test_search_naver_parses_results(self, mock_fetch):
        mock_fetch.return_value = [
            {"title": "<b>블로그</b>1", "description": "LG 트롬 <b>추천</b>합니다", "link": "https://blog.naver.com/1"},
            {"title": "블로그2", "description": "삼성 그랑데 강추", "link": "https://blog.naver.com/2"},
        ]
        scraper = BlogRecommendationScraper(naver_client_id="test_id", naver_client_secret="test_secret")
        results = scraper.search_naver("가성비 드럼세탁기", num_results=2)

        assert len(results) == 2
        assert results[0].title == "블로그1"  # HTML stripped
        assert results[0].snippet == "LG 트롬 추천합니다"  # HTML stripped
        assert results[0].source == "naver"
        assert results[0].rank == 1
        assert results[1].rank == 2

    @patch.object(BlogRecommendationScraper, "_fetch_naver_page")
    def test_naver_pagination(self, mock_fetch):
        """50 results from Naver: single request (display=50)."""
        items = [
            {"title": f"Blog {i}", "description": f"Desc {i}", "link": f"https://blog.naver.com/{i}"}
            for i in range(50)
        ]
        mock_fetch.return_value = items
        scraper = BlogRecommendationScraper(naver_client_id="id", naver_client_secret="secret")
        results = scraper.search_naver("가성비 세탁기", num_results=50)

        assert len(results) == 50
        assert mock_fetch.call_count == 1
        assert results[0].rank == 1
        assert results[49].rank == 50

    @patch.object(BlogRecommendationScraper, "_fetch_naver_page")
    def test_naver_stops_when_no_more_results(self, mock_fetch):
        """If API returns fewer items than requested, stop paginating."""
        mock_fetch.return_value = [
            {"title": f"B{i}", "description": f"D{i}", "link": f"https://naver.com/{i}"}
            for i in range(30)
        ]
        scraper = BlogRecommendationScraper(naver_client_id="id", naver_client_secret="secret")
        results = scraper.search_naver("test", num_results=50)

        assert len(results) == 30
        assert mock_fetch.call_count == 1  # Stopped after partial page

    @patch.object(BlogRecommendationScraper, "_fetch_naver_page")
    def test_naver_api_error_graceful(self, mock_fetch):
        mock_fetch.side_effect = Exception("Naver API error")
        scraper = BlogRecommendationScraper(naver_client_id="id", naver_client_secret="secret")
        results = scraper.search_naver("test", num_results=50)
        assert results == []

    # -- Google SerpAPI tests --

    @patch.object(BlogRecommendationScraper, "_fetch_google_page")
    def test_search_google_parses_results(self, mock_fetch):
        mock_fetch.return_value = [
            {"title": "Google Blog", "snippet": "Good product", "link": "https://example.com/1"},
        ]
        scraper = BlogRecommendationScraper(serpapi_key="test_key")
        results = scraper.search_google("가성비 세탁기", num_results=1)

        assert len(results) == 1
        assert results[0].source == "google"

    @patch.object(BlogRecommendationScraper, "_fetch_google_page")
    def test_google_pagination(self, mock_fetch):
        """15 results should fetch 2 pages (10 + 5)."""
        page1 = [{"title": f"R{i}", "snippet": f"S{i}", "link": f"https://g.com/{i}"} for i in range(10)]
        page2 = [{"title": f"R{10+i}", "snippet": f"S{10+i}", "link": f"https://g.com/{10+i}"} for i in range(10)]

        mock_fetch.side_effect = [page1, page2]
        scraper = BlogRecommendationScraper(serpapi_key="test_key")
        results = scraper.search_google("test", num_results=15)

        assert len(results) == 15
        assert mock_fetch.call_count == 2

    @patch.object(BlogRecommendationScraper, "_fetch_google_page")
    def test_google_stops_on_empty_page(self, mock_fetch):
        mock_fetch.return_value = []
        scraper = BlogRecommendationScraper(serpapi_key="test_key")
        results = scraper.search_google("test", num_results=50)
        assert results == []
        assert mock_fetch.call_count == 1

    @patch.object(BlogRecommendationScraper, "_fetch_google_page")
    def test_google_api_error_graceful(self, mock_fetch):
        mock_fetch.side_effect = Exception("SerpAPI error")
        scraper = BlogRecommendationScraper(serpapi_key="test_key")
        results = scraper.search_google("test", num_results=10)
        assert results == []

    # -- Combined search --

    @patch.object(BlogRecommendationScraper, "_fetch_google_page")
    @patch.object(BlogRecommendationScraper, "_fetch_naver_page")
    def test_search_all_combines_sources(self, mock_naver, mock_google):
        mock_naver.return_value = [
            {"title": f"N{i}", "description": f"ND{i}", "link": f"https://naver.com/{i}"}
            for i in range(3)
        ]
        mock_google.return_value = [
            {"title": f"G{i}", "snippet": f"GS{i}", "link": f"https://google.com/{i}"}
            for i in range(2)
        ]

        scraper = BlogRecommendationScraper(
            serpapi_key="sk", naver_client_id="id", naver_client_secret="secret",
        )
        results = scraper.search_all("세탁기", naver_count=3, google_count=2)

        assert len(results) == 5
        naver_count = sum(1 for r in results if r.source == "naver")
        google_count = sum(1 for r in results if r.source == "google")
        assert naver_count == 3
        assert google_count == 2

    # -- HTML stripping --

    def test_strip_html(self):
        assert BlogRecommendationScraper._strip_html("<b>가성비</b> 세탁기") == "가성비 세탁기"
        assert BlogRecommendationScraper._strip_html("no tags") == "no tags"
        assert BlogRecommendationScraper._strip_html("") == ""

    # -- Missing fields --

    @patch.object(BlogRecommendationScraper, "_fetch_naver_page")
    def test_missing_fields_handled(self, mock_fetch):
        mock_fetch.return_value = [{"title": "Only Title"}]
        scraper = BlogRecommendationScraper(naver_client_id="id", naver_client_secret="secret")
        results = scraper.search_naver("test", num_results=1)

        assert len(results) == 1
        assert results[0].snippet == ""
        assert results[0].link == ""


# ======================================================================
# ProductNameExtractor tests
# ======================================================================


class TestProductNameExtractor:
    def test_no_api_key_returns_empty(self):
        extractor = ProductNameExtractor(api_key="")
        results = extractor.extract_from_snippets([], "드럼세탁기")
        assert results == []

    def test_empty_snippets_returns_empty(self):
        extractor = ProductNameExtractor(api_key="test_key")
        results = extractor.extract_from_snippets([], "드럼세탁기")
        assert results == []

    def test_build_prompt_contains_keyword(self):
        extractor = ProductNameExtractor(api_key="test_key")
        snippets = [
            BlogSearchResult("제목", "내용", "https://example.com", "naver", 1),
        ]
        prompt = extractor._build_prompt(snippets, "드럼세탁기")
        assert "드럼세탁기" in prompt
        assert "제목" in prompt
        assert "내용" in prompt
        assert "JSON" in prompt

    def test_build_prompt_multiple_snippets(self):
        extractor = ProductNameExtractor(api_key="test_key")
        snippets = [
            BlogSearchResult(f"제목{i}", f"내용{i}", f"https://example.com/{i}", "naver", i)
            for i in range(3)
        ]
        prompt = extractor._build_prompt(snippets, "세탁기")
        assert "[1]" in prompt
        assert "[2]" in prompt
        assert "[3]" in prompt

    def test_parse_response_valid_json(self):
        extractor = ProductNameExtractor(api_key="test_key")
        raw = '["LG 트롬 오브제컬렉션", "삼성 그랑데 AI"]'
        result = extractor._parse_response(raw)
        assert len(result) == 2
        assert "LG 트롬 오브제컬렉션" in result

    def test_parse_response_markdown_code_block(self):
        extractor = ProductNameExtractor(api_key="test_key")
        raw = '```json\n["LG 트롬", "삼성 비스포크"]\n```'
        result = extractor._parse_response(raw)
        assert len(result) == 2

    def test_parse_response_empty_array(self):
        extractor = ProductNameExtractor(api_key="test_key")
        assert extractor._parse_response("[]") == []

    def test_parse_response_invalid_json(self):
        extractor = ProductNameExtractor(api_key="test_key")
        assert extractor._parse_response("not valid json at all") == []

    def test_parse_response_strips_whitespace(self):
        extractor = ProductNameExtractor(api_key="test_key")
        raw = '["  LG 트롬  ", " 삼성 그랑데 "]'
        result = extractor._parse_response(raw)
        assert result == ["LG 트롬", "삼성 그랑데"]

    def test_parse_response_filters_empty_strings(self):
        extractor = ProductNameExtractor(api_key="test_key")
        raw = '["LG 트롬", "", "  ", "삼성"]'
        result = extractor._parse_response(raw)
        assert result == ["LG 트롬", "삼성"]

    @patch("src.part_a.product_selector.product_name_extractor.ProductNameExtractor._extract_batch")
    def test_extract_from_snippets_batches(self, mock_batch):
        """12 snippets should produce 3 batches (5+5+2)."""
        mock_batch.return_value = [{"product_name": "LG 트롬", "source_links": []}]

        extractor = ProductNameExtractor(api_key="test_key")
        snippets = [
            BlogSearchResult(f"T{i}", f"S{i}", f"https://example.com/{i}", "naver", i)
            for i in range(12)
        ]
        results = extractor.extract_from_snippets(snippets, "세탁기")

        assert mock_batch.call_count == 3  # ceil(12/5) = 3
        assert len(results) == 3  # 1 result per batch

    @patch("src.part_a.product_selector.product_name_extractor.ProductNameExtractor._extract_batch")
    def test_batch_error_continues(self, mock_batch):
        """If one batch fails, other batches still process."""
        mock_batch.side_effect = [
            [{"product_name": "A", "source_links": []}],
            Exception("API Error"),
            [{"product_name": "C", "source_links": []}],
        ]

        extractor = ProductNameExtractor(api_key="test_key")
        snippets = [
            BlogSearchResult(f"T{i}", f"S{i}", f"https://example.com/{i}", "naver", i)
            for i in range(15)
        ]
        results = extractor.extract_from_snippets(snippets, "세탁기")

        assert len(results) == 2  # Batch 1 + Batch 3 succeeded


# ======================================================================
# RecommendationPipeline tests
# ======================================================================


class TestRecommendationPipeline:
    def test_normalize_name_basic(self):
        norm = RecommendationPipeline._normalize_name("LG 트롬 오브제컬렉션")
        assert norm == "lg 트롬 오브제컬렉션"

    def test_normalize_name_strips_parentheses(self):
        norm = RecommendationPipeline._normalize_name("삼성 그랑데 AI (화이트)")
        assert norm == "삼성 그랑데 ai"

    def test_normalize_name_strips_brackets(self):
        norm = RecommendationPipeline._normalize_name("LG 트롬 [21kg]")
        assert norm == "lg 트롬"

    def test_normalize_name_collapses_whitespace(self):
        norm = RecommendationPipeline._normalize_name("LG  트롬   오브제")
        assert norm == "lg 트롬 오브제"

    def test_normalize_name_empty(self):
        assert RecommendationPipeline._normalize_name("") == ""
        assert RecommendationPipeline._normalize_name("  ") == ""

    def test_normalize_name_unicode(self):
        norm = RecommendationPipeline._normalize_name("삼성 그랑데（화이트）")
        assert "화이트" not in norm

    @patch.object(ProductNameExtractor, "extract_from_snippets")
    @patch.object(BlogRecommendationScraper, "search_all")
    def test_full_pipeline(self, mock_search, mock_extract):
        mock_search.return_value = [
            BlogSearchResult("Blog 1", "LG 트롬 추천", "https://a.com/1", "naver", 1),
            BlogSearchResult("Blog 2", "삼성 그랑데 추천", "https://a.com/2", "naver", 2),
            BlogSearchResult("Blog 3", "LG 트롬 최고", "https://a.com/3", "google", 3),
        ]
        mock_extract.return_value = [
            {"product_name": "LG 트롬 오브제컬렉션", "source_links": ["https://a.com/1"]},
            {"product_name": "삼성 그랑데 AI", "source_links": ["https://a.com/2"]},
            {"product_name": "LG 트롬 오브제컬렉션", "source_links": ["https://a.com/3"]},
            {"product_name": "LG 트롬 오브제컬렉션", "source_links": ["https://a.com/3"]},
        ]

        pipeline = RecommendationPipeline(serpapi_key="test", deepseek_key="test")
        result = pipeline.run("드럼세탁기", top_n=2)

        assert result.keyword == "드럼세탁기"
        assert result.search_query == "가성비 드럼세탁기"
        assert result.total_blogs_searched == 3
        assert result.total_products_extracted == 4
        assert len(result.top_products) == 2
        assert result.top_products[0].product_name == "LG 트롬 오브제컬렉션"
        assert result.top_products[0].mention_count == 3
        assert result.top_products[1].product_name == "삼성 그랑데 AI"
        assert result.top_products[1].mention_count == 1

    @patch.object(ProductNameExtractor, "extract_from_snippets")
    @patch.object(BlogRecommendationScraper, "search_all")
    def test_no_blogs_found(self, mock_search, mock_extract):
        mock_search.return_value = []

        pipeline = RecommendationPipeline(serpapi_key="test", deepseek_key="test")
        result = pipeline.run("미존재카테고리")

        assert result.total_blogs_searched == 0
        assert result.top_products == []
        mock_extract.assert_not_called()

    @patch.object(ProductNameExtractor, "extract_from_snippets")
    @patch.object(BlogRecommendationScraper, "search_all")
    def test_no_products_extracted(self, mock_search, mock_extract):
        mock_search.return_value = [
            BlogSearchResult("Blog", "No products here", "https://a.com", "naver", 1),
        ]
        mock_extract.return_value = []

        pipeline = RecommendationPipeline(serpapi_key="test", deepseek_key="test")
        result = pipeline.run("드럼세탁기")

        assert result.total_blogs_searched == 1
        assert result.total_products_extracted == 0
        assert result.top_products == []

    @patch.object(ProductNameExtractor, "extract_from_snippets")
    @patch.object(BlogRecommendationScraper, "search_all")
    def test_deduplication_by_normalization(self, mock_search, mock_extract):
        """Same product with different casing/suffixes should be counted together."""
        mock_search.return_value = [
            BlogSearchResult("B1", "S1", "https://a.com/1", "naver", 1),
        ]
        mock_extract.return_value = [
            {"product_name": "LG 트롬 오브제컬렉션 (화이트)", "source_links": ["https://a.com/1"]},
            {"product_name": "LG 트롬 오브제컬렉션 (실버)", "source_links": ["https://a.com/1"]},
            {"product_name": "lg 트롬 오브제컬렉션", "source_links": ["https://a.com/1"]},
        ]

        pipeline = RecommendationPipeline(serpapi_key="test", deepseek_key="test")
        result = pipeline.run("드럼세탁기", top_n=2)

        assert len(result.top_products) == 1
        assert result.top_products[0].mention_count == 3

    @patch.object(ProductNameExtractor, "extract_from_snippets")
    @patch.object(BlogRecommendationScraper, "search_all")
    def test_top_n_limiting(self, mock_search, mock_extract):
        mock_search.return_value = [
            BlogSearchResult("B", "S", "https://a.com", "naver", 1),
        ]
        mock_extract.return_value = [
            {"product_name": "Product A", "source_links": []},
            {"product_name": "Product A", "source_links": []},
            {"product_name": "Product A", "source_links": []},
            {"product_name": "Product B", "source_links": []},
            {"product_name": "Product B", "source_links": []},
            {"product_name": "Product C", "source_links": []},
        ]

        pipeline = RecommendationPipeline(serpapi_key="test", deepseek_key="test")
        result = pipeline.run("세탁기", top_n=2)

        assert len(result.top_products) == 2
        assert result.top_products[0].product_name == "Product A"
        assert result.top_products[0].mention_count == 3
        assert result.top_products[1].product_name == "Product B"
        assert result.top_products[1].mention_count == 2

    # -- Model code extraction tests --

    def test_extract_model_code_basic(self):
        assert RecommendationPipeline._extract_model_code("삼성전자 그랑데 WF19T6000KW") == "WF19T6000KW"

    def test_extract_model_code_with_hyphen(self):
        code = RecommendationPipeline._extract_model_code("LG 트롬 GR-B267CEB")
        assert code == "GRB267CEB"

    def test_extract_model_code_empty(self):
        assert RecommendationPipeline._extract_model_code("") == ""

    def test_extract_model_code_no_model(self):
        assert RecommendationPipeline._extract_model_code("LG 트롬 오브제컬렉션") == ""

    def test_extract_model_code_short_token_ignored(self):
        """Tokens under 5 chars should not be treated as model codes."""
        assert RecommendationPipeline._extract_model_code("삼성 AB1") == ""

    def test_extract_model_code_digits_only_ignored(self):
        """Pure numeric tokens are not model codes."""
        assert RecommendationPipeline._extract_model_code("삼성 세탁기 12345678") == ""

    def test_extract_model_code_letters_only_ignored(self):
        """Pure alphabetic tokens are not model codes."""
        assert RecommendationPipeline._extract_model_code("Samsung Grande ABCDEF") == ""

    # -- Model-code-based grouping tests --

    @patch.object(ProductNameExtractor, "extract_from_snippets")
    @patch.object(BlogRecommendationScraper, "search_all")
    def test_model_code_grouping(self, mock_search, mock_extract):
        """Same model code with different brand prefixes should be grouped."""
        mock_search.return_value = [
            BlogSearchResult("B1", "S1", "https://a.com/1", "naver", 1),
        ]
        mock_extract.return_value = [
            {"product_name": "삼성전자 그랑데 WF19T6000KW", "source_links": ["https://a.com/1"]},
            {"product_name": "삼성 WF19T6000KW", "source_links": ["https://a.com/2"]},
            {"product_name": "삼성전자 드럼세탁기 WF19T6000KW", "source_links": ["https://a.com/3"]},
            {"product_name": "LG전자 트롬 F21VDSK", "source_links": ["https://a.com/4"]},
            {"product_name": "LG 트롬 오브제 F21VDSK", "source_links": ["https://a.com/5"]},
        ]

        pipeline = RecommendationPipeline(serpapi_key="test", deepseek_key="test")
        result = pipeline.run("드럼세탁기", top_n=2)

        assert len(result.top_products) == 2
        # WF19T6000KW group should have 3 mentions
        assert result.top_products[0].mention_count == 3
        assert "WF19T6000KW" in result.top_products[0].product_name
        # F21VDSK group should have 2 mentions
        assert result.top_products[1].mention_count == 2
        assert "F21VDSK" in result.top_products[1].product_name

    @patch.object(ProductNameExtractor, "extract_from_snippets")
    @patch.object(BlogRecommendationScraper, "search_all")
    def test_mixed_model_and_no_model(self, mock_search, mock_extract):
        """Products with model codes and without should both be counted."""
        mock_search.return_value = [
            BlogSearchResult("B1", "S1", "https://a.com/1", "naver", 1),
        ]
        mock_extract.return_value = [
            {"product_name": "삼성 WF19T6000KW", "source_links": []},
            {"product_name": "삼성전자 WF19T6000KW", "source_links": []},
            {"product_name": "LG 트롬 오브제컬렉션", "source_links": []},
            {"product_name": "LG 트롬 오브제컬렉션", "source_links": []},
            {"product_name": "LG 트롬 오브제컬렉션", "source_links": []},
        ]

        pipeline = RecommendationPipeline(serpapi_key="test", deepseek_key="test")
        result = pipeline.run("세탁기", top_n=2)

        assert len(result.top_products) == 2
        # "LG 트롬 오브제컬렉션" (no model code, normalized grouping) = 3 mentions
        assert result.top_products[0].mention_count == 3
        # WF19T6000KW group = 2 mentions
        assert result.top_products[1].mention_count == 2

    @patch.object(ProductNameExtractor, "extract_from_snippets")
    @patch.object(BlogRecommendationScraper, "search_all")
    def test_result_serializable(self, mock_search, mock_extract):
        mock_search.return_value = [
            BlogSearchResult("B", "S", "https://a.com", "naver", 1),
        ]
        mock_extract.return_value = [
            {"product_name": "LG 트롬", "source_links": ["https://a.com"]},
        ]

        pipeline = RecommendationPipeline(serpapi_key="test", deepseek_key="test")
        result = pipeline.run("세탁기")

        json_str = result.to_json()
        assert "LG 트롬" in json_str
        assert "세탁기" in json_str
