"""Full publishing pipeline — TCO data to publish-ready output.

Orchestrates the complete flow:
TCO data → ContentWriter → Template render → PostProcessor → Export/Publish

Usage:
    pipeline = PublishPipeline()
    results = pipeline.run(tco_data_path, platforms=["naver", "tistory"])
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.common.config import DATA_EXPORTS_DIR
from src.common.logging import setup_logging
from src.part_b.content_writer.writer import ContentWriter
from src.part_b.content_writer.models import WriterConfig
from src.part_b.cta_manager.manager import CTAManager
from src.part_b.template_engine import render_blog_post

from .models import ExportResult, PublishPlatform, PublishResult, SEOMetaTags
from .platforms import NaverBlogPublisher, TistoryPublisher
from .processor import PostProcessor

logger = setup_logging(module_name="publisher.pipeline")


class PublishPipeline:
    """End-to-end pipeline from TCO data to published blog post.

    Steps:
    1. Generate blog content from TCO data (ContentWriter)
    2. Apply CTA links (CTAManager)
    3. Render with Jinja2 templates (TemplateEngine)
    4. Post-process: images, disclosure, SEO (PostProcessor)
    5. Export/Publish to target platforms
    """

    def __init__(
        self,
        writer: ContentWriter | None = None,
        cta_manager: CTAManager | None = None,
        processor: PostProcessor | None = None,
    ):
        self.writer = writer or ContentWriter()
        self.cta_manager = cta_manager or CTAManager()
        self.processor = processor or PostProcessor()

    def run(
        self,
        tco_data_path: Path | None = None,
        tco_data_dict: dict | None = None,
        platforms: list[str] | None = None,
        campaign: str = "",
    ) -> list[PublishResult]:
        """Execute the full publishing pipeline.

        Args:
            tco_data_path: Path to TCO data JSON from Part A
            tco_data_dict: Pre-loaded TCO data dictionary
            platforms: Target platforms ("naver", "tistory"). Defaults to both.
            campaign: Campaign name for UTM tracking

        Returns:
            List of PublishResult for each platform
        """
        platforms = platforms or ["naver", "tistory"]

        # Step 1: Generate blog content
        logger.info("Step 1: Generating blog content...")
        blog_data = self.writer.generate(
            tco_data_path=tco_data_path,
            tco_data_dict=tco_data_dict,
        )

        # Step 2: Apply CTA links if manager has links
        if self.cta_manager.link_count > 0:
            logger.info("Step 2: Applying CTA links...")
            product_ids = [p.product_id for p in blog_data.products]
            product_names = {p.product_id: p.name for p in blog_data.products}
            plan = self.cta_manager.create_placement_plan(
                product_ids, campaign=campaign, product_names=product_names,
            )
            for product in blog_data.products:
                entries = plan.get_entries_by_product(product.product_id)
                if entries:
                    product.cta_link = entries[0].url

        # Step 3: Render with templates
        logger.info("Step 3: Rendering with templates...")
        rendered_md = render_blog_post(blog_data)

        # Step 4: Build SEO tags
        seo = SEOMetaTags(
            title=blog_data.title,
            description=self._build_seo_description(blog_data),
            keywords=self._build_seo_keywords(blog_data),
            og_title=blog_data.title,
            og_description=self._build_seo_description(blog_data),
        )

        # Step 5: Export/Publish
        logger.info("Step 5: Publishing to %s...", ", ".join(platforms))
        results = []

        if "naver" in platforms:
            html_export = self.processor.export_html(rendered_md, seo)
            publisher = NaverBlogPublisher()
            result = publisher.publish(html_export.content, blog_data.title)
            results.append(result)

        if "tistory" in platforms:
            md_export = self.processor.export_markdown(rendered_md, seo)
            publisher = TistoryPublisher()
            result = publisher.publish(md_export.content, blog_data.title)
            results.append(result)

        logger.info("Pipeline complete: %d platforms published", len(results))
        return results

    def export_only(
        self,
        markdown_content: str,
        title: str = "",
        seo: SEOMetaTags | None = None,
    ) -> dict[str, ExportResult]:
        """Export processed content without full pipeline.

        Useful when you already have rendered markdown and just want to
        export to multiple formats.

        Args:
            markdown_content: Rendered blog post markdown
            title: Post title (extracted from content if empty)
            seo: Optional SEO meta tags

        Returns:
            Dictionary mapping format name to ExportResult
        """
        return {
            "html": self.processor.export_html(markdown_content, seo),
            "markdown": self.processor.export_markdown(markdown_content, seo),
        }

    def _build_seo_description(self, blog_data) -> str:
        """Build SEO meta description from blog data."""
        products = ", ".join(p.name for p in blog_data.products[:3])
        return (
            f"{blog_data.category} TCO 비교 분석 — {products}. "
            f"3년 실제 비용 데이터 기반 추천."
        )[:160]

    def _build_seo_keywords(self, blog_data) -> list[str]:
        """Build SEO keywords from blog data."""
        keywords = [
            blog_data.category,
            f"{blog_data.category} 추천",
            f"{blog_data.category} 비교",
            "TCO",
            "3년 비용",
            "실제 비용",
        ]
        for p in blog_data.products[:3]:
            keywords.append(p.name)
        return keywords
