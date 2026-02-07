"""Tests for the cta_manager module.

Tests cover:
- Affiliate link registration and storage
- UTM parameter generation
- CTA placement rules (1 CTA per product per section 3/4/5)
- URL building with tracking
- Link persistence (JSON save/load)
- Placement plan creation and querying
- CTA link application to product data
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.part_b.cta_manager.models import (
    AffiliateLink,
    AffiliatePlatform,
    CTAEntry,
    CTAPlacementPlan,
    CTASection,
    CTA_DEFAULT_TEXT,
    UTMParams,
)
from src.part_b.cta_manager.manager import CTAManager


# === Fixtures ===


@pytest.fixture
def manager() -> CTAManager:
    """Create a CTAManager with sample links."""
    mgr = CTAManager()
    mgr.register_link(
        "roborock-q-revo-s",
        "https://link.coupang.com/re/AFFILIATE_roborock",
        AffiliatePlatform.COUPANG,
        affiliate_tag="mangorocket",
    )
    mgr.register_link(
        "samsung-bespoke-jet-ai",
        "https://link.coupang.com/re/AFFILIATE_samsung",
        AffiliatePlatform.COUPANG,
        affiliate_tag="mangorocket",
    )
    mgr.register_link(
        "ecovacs-x2-combo",
        "https://link.coupang.com/re/AFFILIATE_ecovacs",
        AffiliatePlatform.COUPANG,
        affiliate_tag="mangorocket",
    )
    return mgr


@pytest.fixture
def product_ids() -> list[str]:
    return [
        "roborock-q-revo-s",
        "samsung-bespoke-jet-ai",
        "ecovacs-x2-combo",
    ]


@pytest.fixture
def product_names() -> dict[str, str]:
    return {
        "roborock-q-revo-s": "로보락 Q Revo S",
        "samsung-bespoke-jet-ai": "삼성 비스포크 제트 AI",
        "ecovacs-x2-combo": "에코백스 X2 콤보",
    }


# === Test: Models ===


class TestModels:
    def test_utm_params_to_query_string(self):
        utm = UTMParams(
            source="tco_blog",
            medium="affiliate",
            campaign="robot_vacuum_2026",
            content="section_3_cta",
        )
        qs = utm.to_query_string()
        assert "utm_source=tco_blog" in qs
        assert "utm_medium=affiliate" in qs
        assert "utm_campaign=robot_vacuum_2026" in qs
        assert "utm_content=section_3_cta" in qs

    def test_utm_params_minimal(self):
        utm = UTMParams()
        qs = utm.to_query_string()
        assert "utm_source=tco_blog" in qs
        assert "utm_medium=affiliate" in qs
        assert "utm_campaign" not in qs

    def test_cta_default_text(self):
        assert CTA_DEFAULT_TEXT == "최저가 확인하기"

    def test_cta_section_values(self):
        assert CTASection.QUICK_PICK.value == "section_3"
        assert CTASection.DEEP_DIVE.value == "section_4"
        assert CTASection.ACTION.value == "section_5"

    def test_placement_plan_query_by_section(self):
        plan = CTAPlacementPlan(
            campaign="test",
            entries=[
                CTAEntry(
                    product_id="p1",
                    product_name="Product 1",
                    section=CTASection.QUICK_PICK,
                    display_text="Click",
                    url="https://example.com",
                ),
                CTAEntry(
                    product_id="p1",
                    product_name="Product 1",
                    section=CTASection.DEEP_DIVE,
                    display_text="Click",
                    url="https://example.com",
                ),
            ],
        )
        section_3 = plan.get_entries_by_section(CTASection.QUICK_PICK)
        assert len(section_3) == 1
        assert section_3[0].section == CTASection.QUICK_PICK

    def test_placement_plan_query_by_product(self):
        plan = CTAPlacementPlan(
            campaign="test",
            entries=[
                CTAEntry(
                    product_id="p1",
                    product_name="P1",
                    section=CTASection.QUICK_PICK,
                    display_text="Click",
                    url="https://example.com",
                ),
                CTAEntry(
                    product_id="p2",
                    product_name="P2",
                    section=CTASection.QUICK_PICK,
                    display_text="Click",
                    url="https://example.com",
                ),
            ],
        )
        p1_entries = plan.get_entries_by_product("p1")
        assert len(p1_entries) == 1


# === Test: Link Registration ===


class TestLinkRegistration:
    def test_register_link(self):
        mgr = CTAManager()
        link = mgr.register_link("product-1", "https://example.com", AffiliatePlatform.COUPANG)
        assert link.product_id == "product-1"
        assert link.base_url == "https://example.com"
        assert mgr.link_count == 1

    def test_register_multiple_links(self, manager):
        assert manager.link_count == 3

    def test_get_link(self, manager):
        link = manager.get_link("roborock-q-revo-s")
        assert link is not None
        assert link.affiliate_tag == "mangorocket"

    def test_get_nonexistent_link(self, manager):
        assert manager.get_link("nonexistent") is None

    def test_remove_link(self, manager):
        assert manager.remove_link("roborock-q-revo-s")
        assert manager.link_count == 2
        assert manager.get_link("roborock-q-revo-s") is None

    def test_remove_nonexistent_link(self, manager):
        assert not manager.remove_link("nonexistent")

    def test_overwrite_link(self, manager):
        manager.register_link("roborock-q-revo-s", "https://new-url.com")
        link = manager.get_link("roborock-q-revo-s")
        assert link.base_url == "https://new-url.com"
        assert manager.link_count == 3  # No duplicate


# === Test: URL Building ===


class TestURLBuilding:
    def test_build_tracked_url_includes_utm(self, manager):
        url = manager.build_tracked_url(
            "roborock-q-revo-s",
            CTASection.QUICK_PICK,
            campaign="robot_vacuum_2026",
        )
        assert "utm_source=tco_blog" in url
        assert "utm_medium=affiliate" in url
        assert "utm_campaign=robot_vacuum_2026" in url
        assert "section_3_cta" in url

    def test_build_tracked_url_includes_affiliate_tag(self, manager):
        url = manager.build_tracked_url(
            "roborock-q-revo-s",
            CTASection.QUICK_PICK,
        )
        assert "tag=mangorocket" in url

    def test_build_tracked_url_different_sections(self, manager):
        url_s3 = manager.build_tracked_url("roborock-q-revo-s", CTASection.QUICK_PICK)
        url_s4 = manager.build_tracked_url("roborock-q-revo-s", CTASection.DEEP_DIVE)
        url_s5 = manager.build_tracked_url("roborock-q-revo-s", CTASection.ACTION)

        assert "section_3_cta" in url_s3
        assert "section_4_cta" in url_s4
        assert "section_5_cta" in url_s5
        assert url_s3 != url_s4 != url_s5

    def test_build_tracked_url_unknown_product(self, manager):
        with pytest.raises(KeyError, match="No affiliate link"):
            manager.build_tracked_url("nonexistent", CTASection.QUICK_PICK)


# === Test: Placement Plan ===


class TestPlacementPlan:
    def test_plan_creates_3_entries_per_product(self, manager, product_ids):
        plan = manager.create_placement_plan(product_ids, campaign="test")

        # 3 products × 3 sections = 9 CTAs
        assert plan.total_cta_count == 9
        assert len(plan.entries) == 9

    def test_plan_one_cta_per_product_per_section(self, manager, product_ids):
        """Critical: exactly 1 CTA per product in each section."""
        plan = manager.create_placement_plan(product_ids, campaign="test")

        for product_id in product_ids:
            for section in [CTASection.QUICK_PICK, CTASection.DEEP_DIVE, CTASection.ACTION]:
                matching = [
                    e for e in plan.entries
                    if e.product_id == product_id and e.section == section
                ]
                assert len(matching) == 1, (
                    f"Expected exactly 1 CTA for {product_id} in {section.value}, "
                    f"got {len(matching)}"
                )

    def test_plan_uses_default_cta_text(self, manager, product_ids):
        plan = manager.create_placement_plan(product_ids)
        for entry in plan.entries:
            assert entry.display_text == CTA_DEFAULT_TEXT

    def test_plan_custom_cta_text(self, manager, product_ids):
        plan = manager.create_placement_plan(product_ids, cta_text="가격 보기")
        for entry in plan.entries:
            assert entry.display_text == "가격 보기"

    def test_plan_includes_product_names(self, manager, product_ids, product_names):
        plan = manager.create_placement_plan(
            product_ids, product_names=product_names
        )
        roborock_entries = plan.get_entries_by_product("roborock-q-revo-s")
        assert roborock_entries[0].product_name == "로보락 Q Revo S"

    def test_plan_skips_unregistered_products(self, manager):
        plan = manager.create_placement_plan(
            ["roborock-q-revo-s", "unknown-product"],
            campaign="test",
        )
        # Only 1 registered product × 3 sections = 3
        assert plan.total_cta_count == 3

    def test_plan_campaign_in_urls(self, manager, product_ids):
        plan = manager.create_placement_plan(product_ids, campaign="spring_2026")
        for entry in plan.entries:
            assert "spring_2026" in entry.url

    def test_empty_plan_for_no_products(self, manager):
        plan = manager.create_placement_plan([])
        assert plan.total_cta_count == 0
        assert len(plan.entries) == 0


# === Test: Apply CTA Links ===


class TestApplyCTALinks:
    def test_apply_sets_cta_link(self, manager, product_ids):
        plan = manager.create_placement_plan(product_ids, campaign="test")
        products = [
            {"product_id": "roborock-q-revo-s", "name": "Roborock"},
            {"product_id": "samsung-bespoke-jet-ai", "name": "Samsung"},
        ]

        result = manager.apply_cta_links(products, plan)

        assert result[0]["cta_link"] != ""
        assert "utm_source" in result[0]["cta_link"]
        assert result[1]["cta_link"] != ""

    def test_apply_uses_section3_url(self, manager, product_ids):
        plan = manager.create_placement_plan(product_ids, campaign="test")
        products = [{"product_id": "roborock-q-revo-s"}]

        result = manager.apply_cta_links(products, plan)
        assert "section_3_cta" in result[0]["cta_link"]

    def test_apply_skips_unmatched_products(self, manager, product_ids):
        plan = manager.create_placement_plan(product_ids, campaign="test")
        products = [{"product_id": "unknown-product"}]

        result = manager.apply_cta_links(products, plan)
        assert "cta_link" not in result[0]


# === Test: Link Persistence ===


class TestLinkPersistence:
    def test_save_and_load_links(self, manager, tmp_path):
        save_path = tmp_path / "affiliate_links.json"

        manager.save_links(save_path)
        assert save_path.exists()

        # Verify JSON structure
        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["links"]) == 3

        # Load into new manager
        new_manager = CTAManager(links_path=save_path)
        assert new_manager.link_count == 3

        link = new_manager.get_link("roborock-q-revo-s")
        assert link is not None
        assert link.affiliate_tag == "mangorocket"

    def test_load_from_nonexistent_file(self):
        mgr = CTAManager(links_path=Path("/nonexistent.json"))
        assert mgr.link_count == 0

    def test_save_creates_parent_dirs(self, manager, tmp_path):
        save_path = tmp_path / "nested" / "dir" / "links.json"
        manager.save_links(save_path)
        assert save_path.exists()
