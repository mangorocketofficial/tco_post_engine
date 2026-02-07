"""Data models for the publisher module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PublishPlatform(str, Enum):
    """Supported publishing platforms."""
    NAVER = "naver"
    TISTORY = "tistory"


class ExportFormat(str, Enum):
    """Output export formats."""
    HTML = "html"
    MARKDOWN = "markdown"


@dataclass
class SEOMetaTags:
    """SEO metadata for blog post."""
    title: str = ""
    description: str = ""  # 150-160 chars
    keywords: list[str] = field(default_factory=list)
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    canonical_url: str = ""

    def to_html_tags(self) -> str:
        """Generate HTML meta tags."""
        tags = []
        if self.title:
            tags.append(f'<title>{self.title}</title>')
        if self.description:
            tags.append(f'<meta name="description" content="{self.description}">')
        if self.keywords:
            tags.append(f'<meta name="keywords" content="{", ".join(self.keywords)}">')
        if self.og_title:
            tags.append(f'<meta property="og:title" content="{self.og_title}">')
        if self.og_description:
            tags.append(f'<meta property="og:description" content="{self.og_description}">')
        if self.og_image:
            tags.append(f'<meta property="og:image" content="{self.og_image}">')
        if self.canonical_url:
            tags.append(f'<link rel="canonical" href="{self.canonical_url}">')
        return "\n".join(tags)


@dataclass
class ImagePlaceholder:
    """Image placeholder for post-processing."""
    alt_text: str
    position: str  # "header", "section_3", "section_4", etc.
    suggested_query: str = ""  # Search query for stock image
    width: int = 800
    height: int = 450


@dataclass
class PostProcessingConfig:
    """Configuration for post-processing pipeline."""
    inject_affiliate_links: bool = True
    add_utm_tracking: bool = True
    insert_image_placeholders: bool = True
    apply_seo_meta: bool = True
    add_disclosure: bool = True
    disclosure_text: str = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."


@dataclass
class PublishResult:
    """Result of publishing a post."""
    success: bool
    platform: PublishPlatform
    post_url: str = ""
    post_id: str = ""
    error: str = ""
    published_at: str = ""


@dataclass
class ExportResult:
    """Result of exporting a post to a format."""
    format: ExportFormat
    content: str
    file_path: str = ""
    title: str = ""
    word_count: int = 0
