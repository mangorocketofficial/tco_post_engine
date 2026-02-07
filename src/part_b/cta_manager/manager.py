"""CTA Manager — Affiliate link management and CTA placement.

Manages product→affiliate URL mappings, applies placement rules
(exactly 1 CTA per product per section in Sections 3, 4, 5),
and generates UTM-tracked URLs for click attribution.

Usage:
    manager = CTAManager()
    manager.register_link("roborock-q-revo-s", "https://link.coupang.com/...")
    plan = manager.create_placement_plan(products, campaign="robot_vacuum_2026")
    products_with_cta = manager.apply_cta_links(products, plan)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs, urljoin

from src.common.logging import setup_logging

from .models import (
    AffiliateLink,
    AffiliatePlatform,
    CTAEntry,
    CTAPlacementPlan,
    CTASection,
    CTA_DEFAULT_TEXT,
    UTMParams,
)

logger = setup_logging(module_name="cta_manager")


class CTAManager:
    """Manages affiliate links, CTA placement rules, and UTM tracking.

    The manager enforces the placement rule: exactly 1 CTA per product
    in Section 3 (Quick Pick), Section 4 (Deep Dive), and Section 5 (Action Trigger).
    """

    def __init__(self, links_path: Path | None = None):
        """Initialize the CTA manager.

        Args:
            links_path: Optional path to JSON file with affiliate links.
                        If provided, links are loaded from the file.
        """
        self._links: dict[str, AffiliateLink] = {}
        if links_path and links_path.exists():
            self.load_links(links_path)

    @property
    def link_count(self) -> int:
        """Number of registered affiliate links."""
        return len(self._links)

    # --- Link Registration ---

    def register_link(
        self,
        product_id: str,
        base_url: str,
        platform: AffiliatePlatform = AffiliatePlatform.COUPANG,
        affiliate_tag: str = "",
    ) -> AffiliateLink:
        """Register an affiliate link for a product.

        Args:
            product_id: Product identifier
            base_url: Base affiliate URL
            platform: Affiliate platform
            affiliate_tag: Optional affiliate tracking tag

        Returns:
            Created AffiliateLink object
        """
        link = AffiliateLink(
            product_id=product_id,
            platform=platform,
            base_url=base_url,
            affiliate_tag=affiliate_tag,
        )
        self._links[product_id] = link
        logger.info("Registered affiliate link for %s", product_id)
        return link

    def get_link(self, product_id: str) -> AffiliateLink | None:
        """Get the affiliate link for a product."""
        return self._links.get(product_id)

    def remove_link(self, product_id: str) -> bool:
        """Remove an affiliate link. Returns True if removed."""
        if product_id in self._links:
            del self._links[product_id]
            return True
        return False

    # --- Link Persistence ---

    def load_links(self, path: Path) -> int:
        """Load affiliate links from a JSON file.

        Args:
            path: Path to JSON file

        Returns:
            Number of links loaded
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for entry in data.get("links", []):
            self.register_link(
                product_id=entry["product_id"],
                base_url=entry["base_url"],
                platform=AffiliatePlatform(entry.get("platform", "coupang")),
                affiliate_tag=entry.get("affiliate_tag", ""),
            )
            count += 1

        logger.info("Loaded %d affiliate links from %s", count, path)
        return count

    def save_links(self, path: Path) -> None:
        """Save affiliate links to a JSON file.

        Args:
            path: Output path for JSON file
        """
        data = {
            "links": [
                {
                    "product_id": link.product_id,
                    "platform": link.platform.value,
                    "base_url": link.base_url,
                    "affiliate_tag": link.affiliate_tag,
                }
                for link in self._links.values()
            ]
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("Saved %d affiliate links to %s", len(self._links), path)

    # --- URL Building ---

    def build_tracked_url(
        self,
        product_id: str,
        section: CTASection,
        campaign: str = "",
    ) -> str:
        """Build a fully tracked affiliate URL with UTM parameters.

        Args:
            product_id: Product identifier
            section: Blog section for the CTA
            campaign: Campaign name for UTM tracking

        Returns:
            Complete URL with affiliate tag and UTM parameters

        Raises:
            KeyError: If no affiliate link registered for the product
        """
        link = self._links.get(product_id)
        if link is None:
            raise KeyError(f"No affiliate link registered for {product_id}")

        # Build UTM params
        utm = UTMParams(
            campaign=campaign,
            content=f"{section.value}_cta",
        )

        # Construct URL
        url = link.base_url

        # Add affiliate tag if present
        if link.affiliate_tag:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}tag={link.affiliate_tag}"

        # Add UTM parameters
        utm_string = utm.to_query_string()
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{utm_string}"

        return url

    # --- CTA Placement ---

    def create_placement_plan(
        self,
        product_ids: list[str],
        campaign: str = "",
        cta_text: str = CTA_DEFAULT_TEXT,
        product_names: dict[str, str] | None = None,
    ) -> CTAPlacementPlan:
        """Create a CTA placement plan for a blog post.

        Enforces the rule: exactly 1 CTA per product in each of
        Section 3 (Quick Pick), Section 4 (Deep Dive), Section 5 (Action Trigger).

        Args:
            product_ids: List of product IDs to include
            campaign: Campaign name for UTM tracking
            cta_text: CTA button/link text (default: "최저가 확인하기")
            product_names: Optional mapping of product_id → display name

        Returns:
            CTAPlacementPlan with all entries
        """
        product_names = product_names or {}
        entries: list[CTAEntry] = []
        sections = [CTASection.QUICK_PICK, CTASection.DEEP_DIVE, CTASection.ACTION]

        for product_id in product_ids:
            link = self._links.get(product_id)
            if link is None or not link.is_active:
                logger.warning(
                    "No active affiliate link for %s, skipping CTA", product_id
                )
                continue

            for section in sections:
                url = self.build_tracked_url(product_id, section, campaign)
                entry = CTAEntry(
                    product_id=product_id,
                    product_name=product_names.get(product_id, product_id),
                    section=section,
                    display_text=cta_text,
                    url=url,
                    platform=link.platform,
                )
                entries.append(entry)

        plan = CTAPlacementPlan(
            campaign=campaign,
            entries=entries,
            total_cta_count=len(entries),
        )

        logger.info(
            "Created CTA plan: %d entries for %d products",
            len(entries),
            len(product_ids),
        )
        return plan

    def apply_cta_links(
        self,
        products: list[dict],
        plan: CTAPlacementPlan,
    ) -> list[dict]:
        """Apply CTA links from a placement plan to product data.

        Sets the `cta_link` field on each product using the Section 3 URL
        (primary CTA link used in templates).

        Args:
            products: List of product data dicts
            plan: CTA placement plan

        Returns:
            Products with cta_link field populated
        """
        # Build lookup: product_id → Section 3 URL
        section3_urls = {
            e.product_id: e.url
            for e in plan.get_entries_by_section(CTASection.QUICK_PICK)
        }

        for product in products:
            pid = product.get("product_id", "")
            if pid in section3_urls:
                product["cta_link"] = section3_urls[pid]

        return products


# Convenience alias
CTADefaultText = CTA_DEFAULT_TEXT
