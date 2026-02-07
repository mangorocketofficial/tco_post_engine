"""Data models for the CTA (Call-to-Action) Manager module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AffiliatePlatform(str, Enum):
    """Supported affiliate platforms."""
    COUPANG = "coupang"
    NAVER = "naver"
    CUSTOM = "custom"


class CTASection(str, Enum):
    """Blog sections where CTAs are placed."""
    QUICK_PICK = "section_3"  # Section 3: Quick Pick Table
    DEEP_DIVE = "section_4"  # Section 4: TCO Deep Dive
    ACTION = "section_5"  # Section 5: Action Trigger


# Standard CTA wording per spec
CTA_DEFAULT_TEXT = "최저가 확인하기"


@dataclass
class AffiliateLink:
    """A single affiliate link for a product."""
    product_id: str
    platform: AffiliatePlatform
    base_url: str
    affiliate_tag: str = ""
    is_active: bool = True


@dataclass
class UTMParams:
    """UTM tracking parameters for click attribution."""
    source: str = "tco_blog"
    medium: str = "affiliate"
    campaign: str = ""  # Set per post (e.g., "robot_vacuum_2026")
    content: str = ""  # Set per section (e.g., "section_3_quick_pick")
    term: str = ""  # Optional: keyword

    def to_query_string(self) -> str:
        """Build UTM query string."""
        params = {
            "utm_source": self.source,
            "utm_medium": self.medium,
        }
        if self.campaign:
            params["utm_campaign"] = self.campaign
        if self.content:
            params["utm_content"] = self.content
        if self.term:
            params["utm_term"] = self.term

        return "&".join(f"{k}={v}" for k, v in params.items())


@dataclass
class CTAEntry:
    """A fully resolved CTA ready for insertion into a blog post."""
    product_id: str
    product_name: str
    section: CTASection
    display_text: str
    url: str  # Final URL with affiliate tag + UTM
    platform: AffiliatePlatform = AffiliatePlatform.COUPANG


@dataclass
class CTAPlacementPlan:
    """Complete CTA placement plan for a blog post."""
    campaign: str
    entries: list[CTAEntry] = field(default_factory=list)
    total_cta_count: int = 0

    def get_entries_by_section(self, section: CTASection) -> list[CTAEntry]:
        """Get all CTA entries for a specific section."""
        return [e for e in self.entries if e.section == section]

    def get_entries_by_product(self, product_id: str) -> list[CTAEntry]:
        """Get all CTA entries for a specific product."""
        return [e for e in self.entries if e.product_id == product_id]
