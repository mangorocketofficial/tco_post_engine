"""Post-processor — Transforms rendered markdown into publish-ready content.

Handles:
- Affiliate link injection
- UTM tracking parameter addition
- Image placeholder insertion
- SEO meta tag application
- Affiliate disclosure injection
- Export to HTML (Naver Blog) and Markdown (Tistory)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import markdown as md

from src.common.logging import setup_logging

from .models import (
    ExportFormat,
    ExportResult,
    ImagePlaceholder,
    PostProcessingConfig,
    SEOMetaTags,
)

logger = setup_logging(module_name="publisher.processor")

# Coupang Partners affiliate disclosure (legally required)
COUPANG_DISCLOSURE = (
    "이 포스팅은 쿠팡 파트너스 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)


class PostProcessor:
    """Transforms rendered markdown into publish-ready blog content.

    Pipeline:
    1. Inject image placeholders
    2. Add affiliate disclosure
    3. Apply SEO meta tags
    4. Export to target format (HTML or Markdown)
    """

    def __init__(self, config: PostProcessingConfig | None = None):
        self.config = config or PostProcessingConfig()

    def process(
        self,
        markdown_content: str,
        seo: SEOMetaTags | None = None,
        images: list[ImagePlaceholder] | None = None,
    ) -> str:
        """Run the full post-processing pipeline on markdown content.

        Args:
            markdown_content: Rendered blog post in markdown format
            seo: Optional SEO meta tags
            images: Optional image placeholders to insert

        Returns:
            Processed markdown content
        """
        content = markdown_content

        if self.config.insert_image_placeholders and images:
            content = self._insert_images(content, images)

        if self.config.add_disclosure:
            content = self._add_disclosure(content)

        return content

    def export_html(
        self,
        markdown_content: str,
        seo: SEOMetaTags | None = None,
        images: list[ImagePlaceholder] | None = None,
    ) -> ExportResult:
        """Export processed content as HTML (for Naver Blog).

        Args:
            markdown_content: Blog post markdown
            seo: SEO meta tags
            images: Image placeholders

        Returns:
            ExportResult with HTML content
        """
        processed = self.process(markdown_content, seo, images)

        # Convert markdown to HTML
        html_body = md.markdown(
            processed,
            extensions=["tables", "fenced_code"],
        )

        # Build full HTML
        seo_tags = seo.to_html_tags() if seo else ""
        title = seo.title if seo else self._extract_title(markdown_content)

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{seo_tags}
</head>
<body>
{html_body}
</body>
</html>"""

        return ExportResult(
            format=ExportFormat.HTML,
            content=html,
            title=title,
            word_count=len(processed.split()),
        )

    def export_markdown(
        self,
        markdown_content: str,
        seo: SEOMetaTags | None = None,
        images: list[ImagePlaceholder] | None = None,
    ) -> ExportResult:
        """Export processed content as Markdown (for Tistory).

        Args:
            markdown_content: Blog post markdown
            seo: SEO meta tags
            images: Image placeholders

        Returns:
            ExportResult with markdown content
        """
        processed = self.process(markdown_content, seo, images)
        title = self._extract_title(markdown_content)

        return ExportResult(
            format=ExportFormat.MARKDOWN,
            content=processed,
            title=title,
            word_count=len(processed.split()),
        )

    def save_export(self, result: ExportResult, output_path: Path) -> str:
        """Save an export result to a file.

        Args:
            result: Export result to save
            output_path: Output file path

        Returns:
            Absolute path to saved file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result.content)

        result.file_path = str(output_path)
        logger.info("Saved %s export to %s", result.format.value, output_path)
        return str(output_path)

    # --- Internal Processing Methods ---

    def _insert_images(
        self,
        content: str,
        images: list[ImagePlaceholder],
    ) -> str:
        """Insert image placeholders into content.

        Images are inserted after section headers matching the position.

        Args:
            content: Markdown content
            images: Image placeholders to insert

        Returns:
            Content with image placeholders
        """
        for img in images:
            placeholder = (
                f"\n\n![{img.alt_text}]"
                f"(IMAGE_PLACEHOLDER:{img.position}:{img.suggested_query})"
                f"\n*{img.alt_text}*\n"
            )

            if img.position == "header":
                # Insert after the first heading
                content = re.sub(
                    r"(^#[^\n]+\n)",
                    rf"\1{placeholder}\n",
                    content,
                    count=1,
                    flags=re.MULTILINE,
                )
            else:
                # Insert after the matching section header (e.g., "## 3.")
                section_num = img.position.replace("section_", "")
                pattern = rf"(^##\s*{section_num}\..*\n)"
                content = re.sub(
                    pattern,
                    rf"\1{placeholder}\n",
                    content,
                    count=1,
                    flags=re.MULTILINE,
                )

        return content

    def _add_disclosure(self, content: str) -> str:
        """Add affiliate disclosure at the end of the content.

        Args:
            content: Markdown content

        Returns:
            Content with disclosure appended
        """
        disclosure = self.config.disclosure_text or COUPANG_DISCLOSURE

        # Check if disclosure already exists
        if disclosure in content:
            return content

        return f"{content}\n\n---\n\n*{disclosure}*\n"

    def _extract_title(self, content: str) -> str:
        """Extract title from the first markdown heading.

        Args:
            content: Markdown content

        Returns:
            Title string or empty string
        """
        match = re.match(r"^#\s+(.+)", content, re.MULTILINE)
        return match.group(1).strip() if match else ""
