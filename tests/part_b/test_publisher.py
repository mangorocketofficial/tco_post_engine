"""Tests for the publisher module.

Tests cover:
- SEO meta tag generation
- Post-processing pipeline (images, disclosure)
- HTML export (Naver Blog format)
- Markdown export (Tistory format)
- File saving
- Platform publishers (Naver, Tistory)
- Full pipeline with mocked ContentWriter
- Export-only mode
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.part_b.publisher.models import (
    ExportFormat,
    ExportResult,
    ImagePlaceholder,
    PostProcessingConfig,
    PublishPlatform,
    PublishResult,
    SEOMetaTags,
)
from src.part_b.publisher.processor import PostProcessor, COUPANG_DISCLOSURE
from src.part_b.publisher.platforms import (
    NaverBlogPublisher,
    TistoryPublisher,
    _sanitize_filename,
)
from src.part_b.publisher.pipeline import PublishPipeline


# === Fixtures ===


SAMPLE_MARKDOWN = """# 2026년 로봇청소기 추천 TOP 3 — 3년 실제 비용 비교

## 0. 1분 요약

로봇청소기 3대를 비교했습니다.

## 1. 이 분석을 신뢰할 수 있는 이유

데이터 447건을 분석했습니다.

## 로봇청소기 고를 때 진짜 중요한 기준 3가지

스펙만 보면 안 됩니다.

## 3. 한눈에 보는 추천 TOP 3

| 제품 | 3년 비용 | 포인트 | 링크 |
|------|---------|--------|------|
| 로보락 Q Revo S | 534,000원 | 가성비 | [최저가 확인하기](https://link.coupang.com/roborock) |

## 4. 상세 분석

### 4-1. 로보락 Q Revo S

추천합니다.

## 5. 지금 확인해야 하는 이유

가격이 변동 중입니다.

## 6. 자주 묻는 질문

**Q: 배터리 교체비는?**
A: 15-20만원 범위입니다.
"""


@pytest.fixture
def sample_seo() -> SEOMetaTags:
    return SEOMetaTags(
        title="2026년 로봇청소기 추천 TOP 3",
        description="로봇청소기 TCO 비교 분석. 3년 실제 비용 데이터 기반 추천.",
        keywords=["로봇청소기", "로봇청소기 추천", "TCO"],
        og_title="2026년 로봇청소기 추천 TOP 3",
        og_description="3년 실제 비용으로 비교한 로봇청소기 추천",
    )


@pytest.fixture
def sample_images() -> list[ImagePlaceholder]:
    return [
        ImagePlaceholder(
            alt_text="로봇청소기 비교",
            position="header",
            suggested_query="robot vacuum comparison",
        ),
        ImagePlaceholder(
            alt_text="추천 TOP 3 테이블",
            position="section_3",
            suggested_query="product comparison table",
        ),
    ]


@pytest.fixture
def processor() -> PostProcessor:
    return PostProcessor()


# === Test: SEO Meta Tags ===


class TestSEOMetaTags:
    def test_to_html_tags(self, sample_seo):
        html = sample_seo.to_html_tags()
        assert '<title>2026년 로봇청소기 추천 TOP 3</title>' in html
        assert 'name="description"' in html
        assert 'name="keywords"' in html
        assert 'property="og:title"' in html

    def test_empty_seo(self):
        seo = SEOMetaTags()
        html = seo.to_html_tags()
        assert html == ""

    def test_partial_seo(self):
        seo = SEOMetaTags(title="Test Title")
        html = seo.to_html_tags()
        assert "<title>Test Title</title>" in html
        assert "og:" not in html


# === Test: Post Processor ===


class TestPostProcessor:
    def test_process_adds_disclosure(self, processor):
        result = processor.process(SAMPLE_MARKDOWN)
        assert COUPANG_DISCLOSURE in result

    def test_process_no_duplicate_disclosure(self, processor):
        content = f"{SAMPLE_MARKDOWN}\n\n*{COUPANG_DISCLOSURE}*\n"
        result = processor.process(content)
        assert result.count(COUPANG_DISCLOSURE) == 1

    def test_process_with_images(self, processor, sample_images):
        result = processor.process(SAMPLE_MARKDOWN, images=sample_images)
        assert "IMAGE_PLACEHOLDER:header" in result
        assert "IMAGE_PLACEHOLDER:section_3" in result

    def test_process_config_disable_disclosure(self):
        config = PostProcessingConfig(add_disclosure=False)
        proc = PostProcessor(config=config)
        result = proc.process(SAMPLE_MARKDOWN)
        assert COUPANG_DISCLOSURE not in result

    def test_process_config_disable_images(self, sample_images):
        config = PostProcessingConfig(insert_image_placeholders=False)
        proc = PostProcessor(config=config)
        result = proc.process(SAMPLE_MARKDOWN, images=sample_images)
        assert "IMAGE_PLACEHOLDER" not in result

    def test_extract_title(self, processor):
        title = processor._extract_title(SAMPLE_MARKDOWN)
        assert "로봇청소기 추천 TOP 3" in title


# === Test: HTML Export ===


class TestHTMLExport:
    def test_export_html_structure(self, processor, sample_seo):
        result = processor.export_html(SAMPLE_MARKDOWN, seo=sample_seo)

        assert result.format == ExportFormat.HTML
        assert "<!DOCTYPE html>" in result.content
        assert '<html lang="ko">' in result.content
        assert "<body>" in result.content
        assert result.title == "2026년 로봇청소기 추천 TOP 3"

    def test_export_html_contains_content(self, processor):
        result = processor.export_html(SAMPLE_MARKDOWN)
        # Markdown tables should be converted to HTML tables
        assert "<table>" in result.content or "<h1>" in result.content

    def test_export_html_includes_seo(self, processor, sample_seo):
        result = processor.export_html(SAMPLE_MARKDOWN, seo=sample_seo)
        assert 'name="description"' in result.content
        assert 'name="keywords"' in result.content

    def test_export_html_word_count(self, processor):
        result = processor.export_html(SAMPLE_MARKDOWN)
        assert result.word_count > 0

    def test_export_html_includes_disclosure(self, processor):
        result = processor.export_html(SAMPLE_MARKDOWN)
        assert "쿠팡 파트너스" in result.content


# === Test: Markdown Export ===


class TestMarkdownExport:
    def test_export_markdown_format(self, processor):
        result = processor.export_markdown(SAMPLE_MARKDOWN)
        assert result.format == ExportFormat.MARKDOWN
        assert "# " in result.content  # Still markdown

    def test_export_markdown_title(self, processor):
        result = processor.export_markdown(SAMPLE_MARKDOWN)
        assert "로봇청소기" in result.title

    def test_export_markdown_includes_disclosure(self, processor):
        result = processor.export_markdown(SAMPLE_MARKDOWN)
        assert COUPANG_DISCLOSURE in result.content

    def test_export_markdown_word_count(self, processor):
        result = processor.export_markdown(SAMPLE_MARKDOWN)
        assert result.word_count > 0


# === Test: File Saving ===


class TestFileSaving:
    def test_save_html_export(self, processor, tmp_path):
        result = processor.export_html(SAMPLE_MARKDOWN)
        output = tmp_path / "test.html"

        path = processor.save_export(result, output)
        assert output.exists()
        assert result.file_path == str(output)

        content = output.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_save_markdown_export(self, processor, tmp_path):
        result = processor.export_markdown(SAMPLE_MARKDOWN)
        output = tmp_path / "test.md"

        processor.save_export(result, output)
        assert output.exists()

    def test_save_creates_dirs(self, processor, tmp_path):
        result = processor.export_html(SAMPLE_MARKDOWN)
        output = tmp_path / "nested" / "dir" / "test.html"

        processor.save_export(result, output)
        assert output.exists()


# === Test: Platform Publishers ===


class TestNaverBlogPublisher:
    def test_publish_creates_file(self, tmp_path):
        with patch("src.part_b.publisher.platforms.DATA_EXPORTS_DIR", tmp_path):
            publisher = NaverBlogPublisher()
            result = publisher.publish("<html><body>Test</body></html>", "테스트 제목")

            assert result.success
            assert result.platform == PublishPlatform.NAVER
            assert result.published_at != ""


class TestTistoryPublisher:
    def test_publish_creates_file(self, tmp_path):
        with patch("src.part_b.publisher.platforms.DATA_EXPORTS_DIR", tmp_path):
            publisher = TistoryPublisher()
            result = publisher.publish("# Test\n\nContent", "테스트 제목")

            assert result.success
            assert result.platform == PublishPlatform.TISTORY
            assert result.published_at != ""


class TestSanitizeFilename:
    def test_basic_sanitization(self):
        assert _sanitize_filename("Hello World") == "Hello_World"

    def test_korean_text(self):
        result = _sanitize_filename("2026년 로봇청소기 추천")
        assert "2026" in result

    def test_special_characters(self):
        result = _sanitize_filename("Test: file/name?")
        assert "/" not in result
        assert ":" not in result
        assert "?" not in result

    def test_length_limit(self):
        long_title = "A" * 100
        assert len(_sanitize_filename(long_title)) <= 50


# === Test: Full Pipeline ===


class TestPublishPipeline:
    def test_export_only(self):
        pipeline = PublishPipeline()
        results = pipeline.export_only(SAMPLE_MARKDOWN, title="Test")

        assert "html" in results
        assert "markdown" in results
        assert results["html"].format == ExportFormat.HTML
        assert results["markdown"].format == ExportFormat.MARKDOWN

    def test_export_only_includes_disclosure(self):
        pipeline = PublishPipeline()
        results = pipeline.export_only(SAMPLE_MARKDOWN)
        assert COUPANG_DISCLOSURE in results["markdown"].content


# === Test: Integration with PostProcessor ===


class TestIntegration:
    def test_processor_handles_html_content(self, processor):
        """PostProcessor should handle pre-generated HTML content."""
        html_content = "<h1>테스트 블로그</h1><p>1,154,000원 비용 분석</p>"

        html_result = processor.export_html(html_content)
        md_result = processor.export_markdown(html_content)

        assert html_result.format == ExportFormat.HTML
        assert "테스트 블로그" in html_result.content
        assert md_result.format == ExportFormat.MARKDOWN
