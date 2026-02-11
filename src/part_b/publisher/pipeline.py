"""Publishing pipeline — accepts pre-generated HTML and publishes to platforms.

Simplified flow (v2):
Pre-generated HTML → PostProcessor (SEO, disclosure) → Export/Publish

Usage:
    pipeline = PublishPipeline()
    results = pipeline.run(html_content, title="...", platforms=["naver", "tistory"])
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.common.config import DATA_EXPORTS_DIR
from src.common.logging import setup_logging
from src.part_b.cta_manager.manager import CTAManager

from .models import ExportResult, PublishPlatform, PublishResult, SEOMetaTags
from .platforms import NaverBlogPublisher, TistoryPublisher
from .processor import PostProcessor

logger = setup_logging(module_name="publisher.pipeline")


class PublishPipeline:
    """Pipeline from pre-generated HTML to published blog post.

    Steps:
    1. Post-process: disclosure, SEO (PostProcessor)
    2. Export/Publish to target platforms
    """

    def __init__(
        self,
        cta_manager: CTAManager | None = None,
        processor: PostProcessor | None = None,
    ):
        self.cta_manager = cta_manager or CTAManager()
        self.processor = processor or PostProcessor()

    def run(
        self,
        html_content: str,
        title: str = "",
        platforms: list[str] | None = None,
        seo: SEOMetaTags | None = None,
    ) -> list[PublishResult]:
        """Execute the publishing pipeline with pre-generated HTML.

        Args:
            html_content: Pre-generated HTML blog content
            title: Post title
            platforms: Target platforms ("naver", "tistory"). Defaults to both.
            seo: Optional SEO meta tags

        Returns:
            List of PublishResult for each platform
        """
        platforms = platforms or ["naver", "tistory"]

        if not seo:
            seo = SEOMetaTags(title=title, og_title=title)

        logger.info("Publishing to %s...", ", ".join(platforms))
        results = []

        if "naver" in platforms:
            html_export = self.processor.export_html(html_content, seo)
            publisher = NaverBlogPublisher()
            result = publisher.publish(html_export.content, title)
            results.append(result)

        if "tistory" in platforms:
            html_export = self.processor.export_html(html_content, seo)
            publisher = TistoryPublisher()
            result = publisher.publish(html_export.content, title)
            results.append(result)

        logger.info("Pipeline complete: %d platforms published", len(results))
        return results

    def export_only(
        self,
        html_content: str,
        title: str = "",
        seo: SEOMetaTags | None = None,
    ) -> dict[str, ExportResult]:
        """Export processed content without publishing.

        Args:
            html_content: Pre-generated HTML blog content
            title: Post title (extracted from content if empty)
            seo: Optional SEO meta tags

        Returns:
            Dictionary mapping format name to ExportResult
        """
        return {
            "html": self.processor.export_html(html_content, seo),
            "markdown": self.processor.export_markdown(html_content, seo),
        }
