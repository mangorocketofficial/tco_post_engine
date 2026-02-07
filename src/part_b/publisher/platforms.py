"""Platform-specific publishing clients for Naver Blog and Tistory.

MVP: File-based export (write HTML/markdown files for manual upload).
Phase 2: Direct API publishing via platform APIs.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.common.config import DATA_EXPORTS_DIR
from src.common.logging import setup_logging

from .models import ExportFormat, PublishPlatform, PublishResult

logger = setup_logging(module_name="publisher.platforms")


class NaverBlogPublisher:
    """Publisher for Naver Blog platform.

    MVP: Exports HTML file for manual upload.
    Phase 2: Uses Naver Blog API for automated publishing.
    """

    PLATFORM = PublishPlatform.NAVER

    def __init__(self, blog_id: str = ""):
        """Initialize Naver Blog publisher.

        Args:
            blog_id: Naver blog ID (for API publishing in Phase 2)
        """
        self.blog_id = blog_id or os.getenv("NAVER_BLOG_ID", "")

    def publish(self, html_content: str, title: str) -> PublishResult:
        """Publish content to Naver Blog.

        MVP: Saves to export directory. Phase 2: API call.

        Args:
            html_content: Full HTML content
            title: Post title

        Returns:
            PublishResult with file path
        """
        # MVP: Export to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = _sanitize_filename(title)
        filename = f"naver_{safe_title}_{timestamp}.html"
        output_path = DATA_EXPORTS_DIR / "naver" / filename

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info("Naver Blog HTML exported: %s", output_path)

        return PublishResult(
            success=True,
            platform=self.PLATFORM,
            post_url=str(output_path),
            published_at=datetime.now().isoformat(),
        )


class TistoryPublisher:
    """Publisher for Tistory platform.

    MVP: Exports markdown file for manual upload.
    Phase 2: Uses Tistory API for automated publishing.
    """

    PLATFORM = PublishPlatform.TISTORY

    def __init__(self, blog_name: str = ""):
        """Initialize Tistory publisher.

        Args:
            blog_name: Tistory blog name (for API publishing in Phase 2)
        """
        self.blog_name = blog_name or os.getenv("TISTORY_BLOG_NAME", "")

    def publish(self, markdown_content: str, title: str) -> PublishResult:
        """Publish content to Tistory.

        MVP: Saves to export directory. Phase 2: API call.

        Args:
            markdown_content: Markdown content
            title: Post title

        Returns:
            PublishResult with file path
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = _sanitize_filename(title)
        filename = f"tistory_{safe_title}_{timestamp}.md"
        output_path = DATA_EXPORTS_DIR / "tistory" / filename

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logger.info("Tistory markdown exported: %s", output_path)

        return PublishResult(
            success=True,
            platform=self.PLATFORM,
            post_url=str(output_path),
            published_at=datetime.now().isoformat(),
        )


def _sanitize_filename(title: str) -> str:
    """Sanitize a title for use as a filename.

    Args:
        title: Raw title string

    Returns:
        Safe filename string
    """
    # Remove or replace problematic characters
    safe = title.replace(" ", "_")
    safe = "".join(c for c in safe if c.isalnum() or c in ("_", "-"))
    return safe[:50]  # Limit length
