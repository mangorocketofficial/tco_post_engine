"""CLI entry point for the TCO engine module.

v4 pipeline (JSON mode — consumable-based):
    python -m src.part_a.tco_engine.main \\
        --category "정수기" \\
        --a0-data data/processed/a0_selected_water_purifier.json \\
        --a2-data data/processed/a2_consumable_water_purifier.json \\
        --a5-data data/processed/a5_reviews_water_purifier.json \\
        --output data/exports/tco_water_purifier.json
"""

from __future__ import annotations

import argparse
import logging

from .exporter import TCOExporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TCO Engine -- Calculator & Export (v4, consumable-based)"
    )
    parser.add_argument(
        "--category",
        type=str,
        required=True,
        help="Product category (e.g., '정수기', '에어프라이어')",
    )
    parser.add_argument(
        "--a0-data",
        type=str,
        required=True,
        help="A0 selected products JSON",
    )
    parser.add_argument(
        "--a2-data",
        type=str,
        required=True,
        help="A2 consumable data JSON",
    )
    parser.add_argument(
        "--a5-data",
        type=str,
        help="A5 review insights JSON (optional, enriches export)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--tco-years",
        type=int,
        default=None,
        help="TCO calculation period in years (default: from config YAML, fallback 3)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Category YAML config path (auto-resolves tco_years)",
    )

    args = parser.parse_args()

    # Resolve tco_years and domain: CLI arg > YAML config > defaults
    tco_years = args.tco_years
    domain = "tech"
    if args.config:
        from ..product_selector.category_config import CategoryConfig
        cat_config = CategoryConfig.from_yaml(args.config)
        if tco_years is None:
            tco_years = cat_config.tco_years
        domain = getattr(cat_config, "domain", "tech") or "tech"
    if tco_years is None:
        tco_years = 3

    logger.info("=== TCO Engine v4 (consumable-based) ===")
    logger.info("Category: %s (domain: %s)", args.category, domain)
    logger.info("TCO years: %d", tco_years)
    logger.info("A0: %s", args.a0_data)
    logger.info("A2: %s", args.a2_data)
    logger.info("A5: %s", args.a5_data or "(not provided)")

    export = TCOExporter.export_from_files(
        category=args.category,
        a0_path=args.a0_data,
        a2_path=args.a2_data,
        a5_path=args.a5_data,
        output_path=args.output,
        tco_years=tco_years,
        domain=domain,
    )

    logger.info("=== TCO Category Export: %s ===", args.category)
    logger.info("Products: %d", len(export["products"]))
    logger.info("Selected tier: %s", export.get("selected_tier", "N/A"))

    for product in export["products"]:
        tco = product["tco"]
        logger.info(
            "  %s (%s): purchase=%s, consumable_%dyr=%s -> real_cost=%s",
            product["name"],
            product["brand"],
            f"{tco['purchase_price']:,}",
            tco.get("tco_years", tco_years),
            f"{tco['consumable_cost_total']:,}",
            f"{tco['real_cost_total']:,}",
        )

    # Print verification result
    verification = export.get("_verification", {})
    if verification.get("errors"):
        logger.error("!!! TCO VERIFICATION FAILED !!!")
        for err in verification["errors"]:
            logger.error("  %s", err)
    else:
        logger.info("TCO verification: PASSED")

    # Print summary
    summary = export.get("summary", {})
    if summary:
        cheapest = summary.get("cheapest", {})
        expensive = summary.get("most_expensive", {})
        logger.info(
            "Summary: %s (%s) ~ %s (%s), diff=%s%%",
            cheapest.get("name", ""),
            f"{cheapest.get('real_cost_total', 0):,}",
            expensive.get("name", ""),
            f"{expensive.get('real_cost_total', 0):,}",
            summary.get("cost_difference_pct", 0),
        )


if __name__ == "__main__":
    main()
