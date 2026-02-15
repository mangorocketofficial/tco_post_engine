"""Tests for the Supabase Publisher module (Step D)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.part_b.publisher.supabase_publisher import (
    FAQItem,
    PublishSummary,
    SupabasePostRow,
    SupabasePublisher,
    count_words,
    extract_body_content,
    extract_description,
    extract_faq_items,
    extract_title,
    _extract_first_coupang_link,
    _match_product_to_tco,
    _brand_to_ascii,
    _extract_model_ascii,
)


# ---------------------------------------------------------------------------
# Fixtures — minimal HTML/JSON samples
# ---------------------------------------------------------------------------

SAMPLE_BLOG_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="가습기 3종 비교 분석: 3년 실비용 기준 추천">
    <title>2026년 가습기 추천 TOP 3 | 리뷰 142건 분석</title>
    <style>
        * { box-sizing: border-box; }
        .cta-button { background: #FF6B35; color: #fff; padding: 14px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; border: 1px solid #E5E7EB; }
    </style>
</head>
<body style="font-family: sans-serif; color: #1F2937;">
<div class="container" style="max-width:768px; margin:0 auto;">
    <section>
        <h1 style="font-size:1.7em;">2026년 가습기 추천 TOP 3</h1>
        <p>리뷰 142건 분석 결과입니다.</p>
    </section>
    <section>
        <h2>추천 제품</h2>
        <a href="https://link.coupang.com/abc123" class="cta-button">최저가 확인하기</a>
        <a href="https://link.coupang.com/def456" class="cta-button">최저가 확인하기</a>
    </section>
    <section>
        <h2>FAQ</h2>
        <details>
            <summary>가습기 전기세가 많이 나오나요?</summary>
            <p>가열식은 월 5,000~8,000원, 초음파식은 월 1,000~2,000원 수준입니다.</p>
        </details>
        <details>
            <summary>가습기 물때 청소는 어떻게 하나요?</summary>
            <p>구연산 세척을 주 1회 권장합니다.</p>
        </details>
    </section>
</div>
</body>
</html>"""

SAMPLE_REVIEW_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="description" content="조지루시 가열식 가습기 리뷰 58건 분석. 3년 실비용 329,000원.">
    <title>조지루시 가열식 가습기 4L, 사도 될까? — 리뷰 58건 분석 [2026]</title>
</head>
<body style="margin:0; font-family:sans-serif; color:#333;">
<div style="max-width:720px; margin:0 auto; padding:24px;">
    <h1 style="font-size:1.6em;">조지루시 가열식 가습기 4L 리뷰</h1>
    <p>이 글은 직접 사용 리뷰가 아닙니다. 실사용자 리뷰 58건을 분석한 정리글입니다.</p>
    <section>
        <h2>구매 동기</h2>
        <p>가열식 살균이 주요 구매 이유입니다.</p>
    </section>
    <section>
        <h2>정리</h2>
        <p>비교 분석은 <a href="{비교글_url}">비교 글</a>을 참고하세요.</p>
        <p>다른 리뷰: <a href="{리뷰글_케어미스트_url}">케어미스트 리뷰</a></p>
    </section>
</div>
</body>
</html>"""

SAMPLE_TCO_DATA = {
    "category": "가습기",
    "generated_at": "2026-02-09T13:31:31",
    "selected_tier": "premium",
    "tier_scores": {"premium": 1.817, "mid": 0.515, "budget": 1.03},
    "tier_product_counts": {"premium": 10, "mid": 4, "budget": 6},
    "credibility": {
        "product_count": 3,
        "total_reviews_analyzed": 142,
        "review_sources": ["쿠팡", "네이버쇼핑"],
    },
    "products": [
        {
            "product_id": "1",
            "name": "조지루시 가열식 가습기 대용량 4L",
            "brand": "조지루시",
            "tco": {
                "purchase_price": 329000,
                "annual_consumable_cost": 0,
                "consumable_cost_total": 0,
                "real_cost_total": 329000,
                "tco_years": 3,
            },
        },
        {
            "product_id": "2",
            "name": "케어미스트 저온 가열식 가습기",
            "brand": "케어미스트",
            "tco": {
                "purchase_price": 149000,
                "annual_consumable_cost": 12000,
                "consumable_cost_total": 36000,
                "real_cost_total": 185000,
                "tco_years": 3,
            },
        },
        {
            "product_id": "3",
            "name": "스텐팟 6L 대용량 스텐 가열식 가습기",
            "brand": "스텐팟",
            "tco": {
                "purchase_price": 348000,
                "annual_consumable_cost": 0,
                "consumable_cost_total": 0,
                "real_cost_total": 348000,
                "tco_years": 3,
            },
        },
    ],
}

SAMPLE_CTA_DATA = {
    "products": [
        {
            "product_name": "조지루시 가열식 가습기 대용량 4L",
            "base_url": "https://link.coupang.com/zojirushi",
        },
        {
            "product_name": "케어미스트 저온 가열식 가습기",
            "base_url": "https://link.coupang.com/caremist",
        },
    ]
}


# ---------------------------------------------------------------------------
# TestHTMLExtraction
# ---------------------------------------------------------------------------

class TestExtractBodyContent:
    def test_extracts_body_inner_html(self):
        result = extract_body_content(SAMPLE_BLOG_HTML)
        # <h1> is stripped to avoid duplicate title display on blog platform
        assert "<h1" not in result
        assert "<!DOCTYPE" not in result
        assert "<html" not in result
        assert "<head>" not in result

    def test_includes_style_block(self):
        result = extract_body_content(SAMPLE_BLOG_HTML)
        assert "<style>" in result
        assert ".cta-button" in result

    def test_preserves_inline_styles(self):
        result = extract_body_content(SAMPLE_BLOG_HTML)
        assert 'style="max-width:768px' in result

    def test_no_style_block_when_absent(self):
        result = extract_body_content(SAMPLE_REVIEW_HTML)
        assert "<style>" not in result
        # <h1> stripped to avoid duplicate title
        assert "<h1" not in result

    def test_returns_input_if_no_body(self):
        fragment = "<h2>Hello</h2><p>World</p>"
        result = extract_body_content(fragment)
        assert "World" in result


class TestExtractTitle:
    def test_from_title_tag(self):
        title = extract_title(SAMPLE_BLOG_HTML)
        assert title == "2026년 가습기 추천 TOP 3 | 리뷰 142건 분석"

    def test_fallback_to_h1(self):
        html = "<html><body><h1>Fallback Title</h1></body></html>"
        assert extract_title(html) == "Fallback Title"

    def test_empty_when_no_title_or_h1(self):
        html = "<html><body><p>No title here</p></body></html>"
        assert extract_title(html) == ""

    def test_review_title(self):
        title = extract_title(SAMPLE_REVIEW_HTML)
        assert "조지루시" in title
        assert "2026" in title


class TestExtractDescription:
    def test_from_meta_tag(self):
        desc = extract_description(SAMPLE_BLOG_HTML)
        assert "가습기 3종 비교 분석" in desc

    def test_empty_when_missing(self):
        html = "<html><head></head><body></body></html>"
        assert extract_description(html) == ""

    def test_review_description(self):
        desc = extract_description(SAMPLE_REVIEW_HTML)
        assert "조지루시" in desc
        assert "329,000원" in desc


class TestExtractFaqItems:
    def test_parses_faq_items(self):
        items = extract_faq_items(SAMPLE_BLOG_HTML)
        assert len(items) == 2
        assert "전기세" in items[0].question
        assert "가열식" in items[0].answer
        assert "물때" in items[1].question

    def test_empty_when_no_details(self):
        html = "<html><body><p>No FAQ</p></body></html>"
        items = extract_faq_items(html)
        assert items == []

    def test_faq_item_schema(self):
        items = extract_faq_items(SAMPLE_BLOG_HTML)
        for item in items:
            assert isinstance(item, FAQItem)
            assert isinstance(item.question, str)
            assert isinstance(item.answer, str)
            assert len(item.question) > 0
            assert len(item.answer) > 0


# ---------------------------------------------------------------------------
# TestWordCount
# ---------------------------------------------------------------------------

class TestCountWords:
    def test_strips_html_tags(self):
        html = "<h1>제목</h1><p>본문 내용 입니다</p>"
        assert count_words(html) == 4  # 제목, 본문, 내용, 입니다

    def test_handles_empty(self):
        assert count_words("") == 0
        assert count_words("<div></div>") == 0

    def test_handles_nested_tags(self):
        html = "<div><p><strong>중요한</strong> 내용</p></div>"
        assert count_words(html) == 2


# ---------------------------------------------------------------------------
# TestSlugGeneration
# ---------------------------------------------------------------------------

class TestSlugGeneration:
    def test_comparison_slug(self):
        assert SupabasePublisher.generate_comparison_slug("robot-vacuum") == "robot-vacuum-best"

    def test_comparison_slug_pet(self):
        assert SupabasePublisher.generate_comparison_slug("pet-water-fountain") == "pet-water-fountain-best"

    def test_review_slug_mapped_brand(self):
        slug = SupabasePublisher.generate_review_slug(
            "로보락 S9 MaxV Ultra", "로보락", "robot-vacuum"
        )
        assert slug == "robot-vacuum-roborock-s9-maxv-ultra-review"

    def test_review_slug_model_extraction(self):
        slug = SupabasePublisher.generate_review_slug(
            "드리미 X50s Pro Ultra 화이트, 단품", "드리미", "robot-vacuum"
        )
        assert slug == "robot-vacuum-dreame-x50s-pro-ultra-review"

    def test_review_slug_strips_parenthetical(self):
        slug = SupabasePublisher.generate_review_slug(
            "로보락 S9 MaxV Ultra (S90VER+EWFD32HRR) 화이트", "로보락", "robot-vacuum"
        )
        assert "s90ver" not in slug
        assert slug.endswith("-review")

    def test_review_slug_no_double_hyphens(self):
        slug = SupabasePublisher.generate_review_slug(
            "브랜드  여러   공백 Model", "브랜드", "cat"
        )
        assert "--" not in slug

    def test_review_slug_is_ascii_safe(self):
        slug = SupabasePublisher.generate_review_slug(
            "다이슨 스팟앤스크럽 Ai 로봇 청소기", "다이슨", "robot-vacuum"
        )
        assert all(ord(c) < 128 for c in slug), f"Non-ASCII in slug: {slug}"
        assert slug == "robot-vacuum-dyson-ai-review"


class TestBrandToAscii:
    def test_known_brand(self):
        assert _brand_to_ascii("로보락") == "roborock"
        assert _brand_to_ascii("다이슨") == "dyson"

    def test_unknown_brand_with_ascii(self):
        result = _brand_to_ascii("LG전자")
        assert all(ord(c) < 128 for c in result)

    def test_pure_korean_brand_fallback(self):
        result = _brand_to_ascii("케어미스트")
        assert all(ord(c) < 128 for c in result)
        assert len(result) > 0


class TestExtractModelAscii:
    def test_strips_korean(self):
        model = _extract_model_ascii("S9 MaxV Ultra 화이트", "")
        assert model == "s9-maxv-ultra"

    def test_strips_parenthetical(self):
        model = _extract_model_ascii("S9 MaxV (S90VER) Ultra", "")
        assert "s90ver" not in model

    def test_strips_brackets(self):
        model = _extract_model_ascii("X50s Pro [단품]", "")
        assert model == "x50s-pro"

    def test_removes_brand(self):
        model = _extract_model_ascii("로보락 S9 MaxV Ultra", "로보락")
        assert model == "s9-maxv-ultra"


# ---------------------------------------------------------------------------
# TestCoupangLinkExtraction
# ---------------------------------------------------------------------------

class TestExtractFirstCoupangLink:
    def test_finds_coupang_link(self):
        link = _extract_first_coupang_link(SAMPLE_BLOG_HTML)
        assert link == "https://link.coupang.com/abc123"

    def test_returns_none_when_no_link(self):
        html = '<html><body><a href="https://naver.com">Naver</a></body></html>'
        assert _extract_first_coupang_link(html) is None


# ---------------------------------------------------------------------------
# TestProductMatching
# ---------------------------------------------------------------------------

class TestMatchProductToTco:
    def test_matches_by_name_substring(self):
        products = SAMPLE_TCO_DATA["products"]
        result = _match_product_to_tco("조지루시 가열식 가습기 4L 리뷰", products)
        assert result is not None
        assert result["brand"] == "조지루시"

    def test_matches_by_brand(self):
        products = SAMPLE_TCO_DATA["products"]
        result = _match_product_to_tco("케어미스트 저온 가열식 가습기 리뷰", products)
        assert result is not None
        assert result["brand"] == "케어미스트"

    def test_returns_none_for_unknown(self):
        products = SAMPLE_TCO_DATA["products"]
        result = _match_product_to_tco("알 수 없는 제품 리뷰", products)
        assert result is None


# ---------------------------------------------------------------------------
# TestSupabasePostRow
# ---------------------------------------------------------------------------

class TestSupabasePostRow:
    def test_to_supabase_dict_required_fields(self):
        row = SupabasePostRow(
            slug="test-slug",
            title="Test Title",
            content="<p>Content</p>",
            category="test",
        )
        d = row.to_supabase_dict()
        assert d["slug"] == "test-slug"
        assert d["title"] == "Test Title"
        assert d["content"] == "<p>Content</p>"
        assert d["category"] == "test"

    def test_none_fields_omitted(self):
        row = SupabasePostRow(
            slug="s", title="t", content="c", category="cat",
            description=None, coupang_url=None, product_name=None,
        )
        d = row.to_supabase_dict()
        assert "description" not in d
        assert "coupang_url" not in d
        assert "product_name" not in d

    def test_faq_serialization(self):
        row = SupabasePostRow(
            slug="s", title="t", content="c", category="cat",
            faq=[FAQItem(question="Q1?", answer="A1"), FAQItem(question="Q2?", answer="A2")],
        )
        d = row.to_supabase_dict()
        assert len(d["faq"]) == 2
        assert d["faq"][0] == {"question": "Q1?", "answer": "A1"}

    def test_empty_faq_included(self):
        row = SupabasePostRow(slug="s", title="t", content="c", category="cat", faq=[])
        d = row.to_supabase_dict()
        assert d["faq"] == []

    def test_tags_and_keywords(self):
        row = SupabasePostRow(
            slug="s", title="t", content="c", category="cat",
            tags=["a", "b"], seo_keywords=["x", "y"],
        )
        d = row.to_supabase_dict()
        assert d["tags"] == ["a", "b"]
        assert d["seo_keywords"] == ["x", "y"]


# ---------------------------------------------------------------------------
# TestBuildComparisonPost
# ---------------------------------------------------------------------------

class TestBuildComparisonPost:
    def setup_method(self):
        self.publisher = SupabasePublisher(supabase_url="http://test", supabase_key="test")

    def test_builds_comparison_post(self):
        post = self.publisher.build_comparison_post(SAMPLE_TCO_DATA, SAMPLE_BLOG_HTML)
        assert post.slug == "pending"  # Real slug assigned by publish_category
        assert "2026년 가습기 추천 TOP 3" in post.title
        assert post.category == "가습기"
        assert post.product_name is None
        assert post.product_price is None

    def test_content_is_fragment(self):
        post = self.publisher.build_comparison_post(SAMPLE_TCO_DATA, SAMPLE_BLOG_HTML)
        assert "<!DOCTYPE" not in post.content
        assert "<html" not in post.content
        # <h1> stripped to avoid duplicate title on blog platform
        assert "<h1" not in post.content

    def test_includes_style_block(self):
        post = self.publisher.build_comparison_post(SAMPLE_TCO_DATA, SAMPLE_BLOG_HTML)
        assert "<style>" in post.content
        assert ".cta-button" in post.content

    def test_faq_extracted(self):
        post = self.publisher.build_comparison_post(SAMPLE_TCO_DATA, SAMPLE_BLOG_HTML)
        assert len(post.faq) == 2
        assert "전기세" in post.faq[0].question

    def test_coupang_url_extracted(self):
        post = self.publisher.build_comparison_post(SAMPLE_TCO_DATA, SAMPLE_BLOG_HTML)
        assert post.coupang_url == "https://link.coupang.com/abc123"

    def test_tags_include_brands(self):
        post = self.publisher.build_comparison_post(SAMPLE_TCO_DATA, SAMPLE_BLOG_HTML)
        assert "가습기" in post.tags
        assert "TCO" in post.tags
        assert "비교" in post.tags
        # At least one brand should be present
        brands_in_tags = [t for t in post.tags if t in ["조지루시", "케어미스트", "스텐팟"]]
        assert len(brands_in_tags) >= 1

    def test_seo_keywords_generated(self):
        post = self.publisher.build_comparison_post(SAMPLE_TCO_DATA, SAMPLE_BLOG_HTML)
        assert "가습기 추천" in post.seo_keywords
        assert "3년 실비용" in post.seo_keywords

    def test_word_count_positive(self):
        post = self.publisher.build_comparison_post(SAMPLE_TCO_DATA, SAMPLE_BLOG_HTML)
        assert post.word_count > 0

    def test_description_extracted(self):
        post = self.publisher.build_comparison_post(SAMPLE_TCO_DATA, SAMPLE_BLOG_HTML)
        assert post.description is not None
        assert "가습기" in post.description


# ---------------------------------------------------------------------------
# TestBuildReviewPost
# ---------------------------------------------------------------------------

class TestBuildReviewPost:
    def setup_method(self):
        self.publisher = SupabasePublisher(supabase_url="http://test", supabase_key="test")
        self.product = SAMPLE_TCO_DATA["products"][0]

    def test_builds_review_post(self):
        post = self.publisher.build_review_post(
            SAMPLE_TCO_DATA, SAMPLE_REVIEW_HTML, self.product, SAMPLE_CTA_DATA,
        )
        assert post.slug == "pending"  # Real slug assigned by publish_category
        assert "조지루시" in post.title
        assert post.category == "가습기"

    def test_product_fields_mapped(self):
        post = self.publisher.build_review_post(
            SAMPLE_TCO_DATA, SAMPLE_REVIEW_HTML, self.product, SAMPLE_CTA_DATA,
        )
        assert post.product_name == "조지루시 가열식 가습기 대용량 4L"
        assert post.product_price == 329000

    def test_cta_from_cta_data(self):
        post = self.publisher.build_review_post(
            SAMPLE_TCO_DATA, SAMPLE_REVIEW_HTML, self.product, SAMPLE_CTA_DATA,
        )
        assert post.coupang_url == "https://link.coupang.com/zojirushi"

    def test_no_faq_for_reviews(self):
        post = self.publisher.build_review_post(
            SAMPLE_TCO_DATA, SAMPLE_REVIEW_HTML, self.product,
        )
        assert post.faq == []

    def test_tags_include_brand(self):
        post = self.publisher.build_review_post(
            SAMPLE_TCO_DATA, SAMPLE_REVIEW_HTML, self.product,
        )
        assert "조지루시" in post.tags
        assert "리뷰" in post.tags

    def test_content_no_style_block(self):
        post = self.publisher.build_review_post(
            SAMPLE_TCO_DATA, SAMPLE_REVIEW_HTML, self.product,
        )
        assert "<style>" not in post.content
        # <h1> stripped to avoid duplicate title on blog platform
        assert "<h1" not in post.content


# ---------------------------------------------------------------------------
# TestCleanupStalePlaceholders
# ---------------------------------------------------------------------------

class TestCleanupStalePlaceholders:
    def setup_method(self):
        self.publisher = SupabasePublisher(supabase_url="http://test", supabase_key="test")

    def test_replaces_comparison_placeholder(self):
        post = SupabasePostRow(
            slug="가습기-추천-비교",
            title="비교 글",
            content='<a href="{비교글_url}">비교 글</a>',
            category="가습기",
        )
        posts = self.publisher._cleanup_stale_placeholders([post])
        assert "{비교글_url}" not in posts[0].content
        assert "#" in posts[0].content

    def test_replaces_review_placeholder(self):
        post = SupabasePostRow(
            slug="조지루시-가열식-가습기-대용량-4l-리뷰",
            title="리뷰",
            content='<a href="{리뷰글_케어미스트_url}">케어미스트 리뷰</a>',
            category="가습기",
            product_name="조지루시 가열식 가습기 대용량 4L",
        )
        posts = self.publisher._cleanup_stale_placeholders([post])
        assert "{리뷰글_케어미스트_url}" not in posts[0].content
        assert "#" in posts[0].content

    def test_no_change_when_no_placeholders(self):
        post = SupabasePostRow(
            slug="가습기-추천-비교",
            title="비교 글",
            content='<a href="/posts/가습기-추천-비교">비교 글</a>',
            category="가습기",
        )
        original_content = post.content
        posts = self.publisher._cleanup_stale_placeholders([post])
        assert posts[0].content == original_content


# ---------------------------------------------------------------------------
# TestPublishCategory — Full pipeline
# ---------------------------------------------------------------------------

class TestPublishCategory:
    def setup_method(self):
        self.publisher = SupabasePublisher(supabase_url="http://test", supabase_key="test")

    def test_dry_run_no_supabase_call(self, tmp_path):
        """Dry run builds posts but does not call Supabase."""
        tco_path = tmp_path / "tco_test.json"
        tco_path.write_text(json.dumps(SAMPLE_TCO_DATA), encoding="utf-8")
        blog_path = tmp_path / "blog_test.html"
        blog_path.write_text(SAMPLE_BLOG_HTML, encoding="utf-8")

        summary = self.publisher.publish_category(
            tco_data_path=str(tco_path),
            blog_html_path=str(blog_path),
            publish=False,
            category_slug="humidifier",
        )
        assert summary.total_posts == 1  # Comparison only
        assert summary.inserted == 0
        assert len(summary.errors) == 0
        assert summary.posts[0]["slug"] == "humidifier-best"

    def test_dry_run_with_reviews(self, tmp_path):
        """Dry run with review directory includes review posts."""
        tco_path = tmp_path / "tco_test.json"
        tco_path.write_text(json.dumps(SAMPLE_TCO_DATA), encoding="utf-8")
        blog_path = tmp_path / "blog_test.html"
        blog_path.write_text(SAMPLE_BLOG_HTML, encoding="utf-8")
        review_path = tmp_path / "review_가습기_조지루시.html"
        review_path.write_text(SAMPLE_REVIEW_HTML, encoding="utf-8")

        summary = self.publisher.publish_category(
            tco_data_path=str(tco_path),
            blog_html_path=str(blog_path),
            review_dir=str(tmp_path),
            publish=False,
            category_slug="humidifier",
        )
        assert summary.total_posts == 2  # Comparison + 1 review
        slugs = [p["slug"] for p in summary.posts]
        assert slugs[0] == "humidifier-best"
        assert slugs[1].startswith("humidifier-zojirushi-")
        assert slugs[1].endswith("-review")
        # All slugs must be ASCII-safe
        for slug in slugs:
            assert all(ord(c) < 128 for c in slug), f"Non-ASCII in slug: {slug}"

    def test_missing_tco_file(self):
        summary = self.publisher.publish_category(
            tco_data_path="/nonexistent/tco.json",
            blog_html_path="/nonexistent/blog.html",
            publish=False,
        )
        assert len(summary.errors) > 0
        assert summary.total_posts == 0

    def test_missing_blog_html(self, tmp_path):
        tco_path = tmp_path / "tco.json"
        tco_path.write_text(json.dumps(SAMPLE_TCO_DATA), encoding="utf-8")

        summary = self.publisher.publish_category(
            tco_data_path=str(tco_path),
            blog_html_path="/nonexistent/blog.html",
            publish=False,
        )
        assert len(summary.errors) > 0

    def test_unmatched_review_skipped(self, tmp_path):
        """Review file that can't match a product is skipped."""
        tco_path = tmp_path / "tco_test.json"
        tco_path.write_text(json.dumps(SAMPLE_TCO_DATA), encoding="utf-8")
        blog_path = tmp_path / "blog_test.html"
        blog_path.write_text(SAMPLE_BLOG_HTML, encoding="utf-8")

        # Review with unrecognizable product name
        unmatched_html = SAMPLE_REVIEW_HTML.replace("조지루시", "알수없는브랜드")
        unmatched_html = unmatched_html.replace("가열식 가습기 4L", "미지의 제품")
        review_path = tmp_path / "review_가습기_unknown.html"
        review_path.write_text(unmatched_html, encoding="utf-8")

        summary = self.publisher.publish_category(
            tco_data_path=str(tco_path),
            blog_html_path=str(blog_path),
            review_dir=str(tmp_path),
            publish=False,
        )
        assert summary.skipped >= 1

    @patch("src.part_b.publisher.supabase_publisher.SupabasePublisher._get_client")
    def test_publish_calls_upsert(self, mock_get_client, tmp_path):
        """With --publish, calls Supabase upsert (default update_existing=True)."""
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_get_client.return_value = mock_client

        tco_path = tmp_path / "tco.json"
        tco_path.write_text(json.dumps(SAMPLE_TCO_DATA), encoding="utf-8")
        blog_path = tmp_path / "blog.html"
        blog_path.write_text(SAMPLE_BLOG_HTML, encoding="utf-8")

        summary = self.publisher.publish_category(
            tco_data_path=str(tco_path),
            blog_html_path=str(blog_path),
            publish=True,
            category_slug="humidifier",
        )
        assert summary.updated == 1
        mock_client.table.assert_called_with("posts")

    def test_pet_domain_uses_category_slug(self, tmp_path):
        """Pet domain uses same category-based slug convention."""
        pet_tco = {**SAMPLE_TCO_DATA, "domain": "pet", "tco_years": 2}
        tco_path = tmp_path / "tco_pet.json"
        tco_path.write_text(json.dumps(pet_tco), encoding="utf-8")
        blog_path = tmp_path / "blog_pet.html"
        blog_path.write_text(SAMPLE_BLOG_HTML, encoding="utf-8")

        summary = self.publisher.publish_category(
            tco_data_path=str(tco_path),
            blog_html_path=str(blog_path),
            publish=False,
            category_slug="pet-water-fountain",
        )
        assert summary.posts[0]["slug"] == "pet-water-fountain-best"

    def test_baby_domain_uses_category_slug(self, tmp_path):
        """Baby domain uses same category-based slug convention."""
        baby_tco = {**SAMPLE_TCO_DATA, "domain": "baby", "tco_years": 2}
        tco_path = tmp_path / "tco_baby.json"
        tco_path.write_text(json.dumps(baby_tco), encoding="utf-8")
        blog_path = tmp_path / "blog_baby.html"
        blog_path.write_text(SAMPLE_BLOG_HTML, encoding="utf-8")

        summary = self.publisher.publish_category(
            tco_data_path=str(tco_path),
            blog_html_path=str(blog_path),
            publish=False,
            category_slug="diaper-pail",
        )
        assert summary.posts[0]["slug"] == "diaper-pail-best"

    def test_baby_domain_tag_in_comparison(self):
        """Baby domain should include 육아용품 tag in comparison post."""
        baby_tco = {**SAMPLE_TCO_DATA, "domain": "baby"}
        pub = SupabasePublisher(supabase_url="http://test", supabase_key="key", domain="baby")
        row = pub.build_comparison_post(baby_tco, SAMPLE_BLOG_HTML)
        assert "육아용품" in row.tags

    def test_baby_domain_tag_in_review(self):
        """Baby domain should include 육아용품 tag in review post."""
        baby_tco = {**SAMPLE_TCO_DATA, "domain": "baby"}
        pub = SupabasePublisher(supabase_url="http://test", supabase_key="key", domain="baby")
        product_data = baby_tco["products"][0]
        row = pub.build_review_post(baby_tco, SAMPLE_REVIEW_HTML, product_data)
        assert "육아용품" in row.tags

    @patch("src.part_b.publisher.supabase_publisher.SupabasePublisher._get_client")
    def test_update_existing_uses_upsert(self, mock_get_client, tmp_path):
        """--update-existing triggers upsert instead of insert."""
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_get_client.return_value = mock_client

        tco_path = tmp_path / "tco.json"
        tco_path.write_text(json.dumps(SAMPLE_TCO_DATA), encoding="utf-8")
        blog_path = tmp_path / "blog.html"
        blog_path.write_text(SAMPLE_BLOG_HTML, encoding="utf-8")

        summary = self.publisher.publish_category(
            tco_data_path=str(tco_path),
            blog_html_path=str(blog_path),
            publish=True,
            update_existing=True,
            category_slug="humidifier",
        )
        assert summary.updated == 1
        mock_client.table.return_value.upsert.assert_called_once()


# ---------------------------------------------------------------------------
# TestSupabasePublisherInit
# ---------------------------------------------------------------------------

class TestSupabasePublisherInit:
    def test_init_with_explicit_params(self):
        pub = SupabasePublisher(supabase_url="http://test", supabase_key="key")
        assert pub._supabase_url == "http://test"
        assert pub._supabase_key == "key"

    def test_init_from_env(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "http://env-url")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "env-key")
        pub = SupabasePublisher()
        assert pub._supabase_url == "http://env-url"
        assert pub._supabase_key == "env-key"

    def test_lazy_client_init(self):
        pub = SupabasePublisher(supabase_url="http://test", supabase_key="key")
        assert pub._client is None  # Not initialized yet

    def test_get_client_raises_without_credentials(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
        monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_URL", raising=False)
        monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", raising=False)
        pub = SupabasePublisher(supabase_url="", supabase_key="")
        with pytest.raises(ValueError, match="SUPABASE_URL"):
            pub._get_client()

    def test_init_baby_domain_from_env(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_BABY_URL", "http://baby-url")
        monkeypatch.setenv("SUPABASE_BABY_SERVICE_KEY", "baby-key")
        pub = SupabasePublisher(domain="baby")
        assert pub._supabase_url == "http://baby-url"
        assert pub._supabase_key == "baby-key"

    def test_get_client_raises_baby_without_credentials(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_BABY_URL", raising=False)
        monkeypatch.delenv("SUPABASE_BABY_SERVICE_KEY", raising=False)
        pub = SupabasePublisher(supabase_url="", supabase_key="", domain="baby")
        with pytest.raises(ValueError, match="SUPABASE_BABY_URL"):
            pub._get_client()


# ---------------------------------------------------------------------------
# TestPublishSummary
# ---------------------------------------------------------------------------

class TestPublishSummary:
    def test_default_values(self):
        s = PublishSummary()
        assert s.total_posts == 0
        assert s.inserted == 0
        assert s.errors == []
        assert s.posts == []

    def test_accumulates_counts(self):
        s = PublishSummary(total_posts=4, inserted=2, updated=1, skipped=1)
        assert s.total_posts == 4
