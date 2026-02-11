# CTA Manager — Affiliate link storage, placement rules, UTM tracking
"""
CTA Manager module for managing affiliate links and CTA placement.

Enforces placement rules: exactly 1 CTA per product in Sections 3, 4, and 5.
All links include UTM parameters for click attribution.
"""

from .manager import CTAManager
from .image_scraper import CoupangImageScraper
from .models import (
    AffiliateLink,
    AffiliatePlatform,
    CTAEntry,
    CTAPlacementPlan,
    CTASection,
    CTA_DEFAULT_TEXT,
    UTMParams,
)

__all__ = [
    "CTAManager",
    "CoupangImageScraper",
    "AffiliateLink",
    "AffiliatePlatform",
    "CTAEntry",
    "CTAPlacementPlan",
    "CTASection",
    "CTA_DEFAULT_TEXT",
    "UTMParams",
]
