"""CLI entry point for the TCO engine module.

Usage:
    python -m src.part_a.tco_engine.main --category "로봇청소기"
    python -m src.part_a.tco_engine.main --product-id 1
    python -m src.part_a.tco_engine.main --category "로봇청소기" --output data/exports/tco.json
"""

from __future__ import annotations

import argparse
import json
import logging

from ..common.config import Config
from ..database.connection import init_db
from .calculator import TCOCalculator
from .exporter import TCOExporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="TCO Engine — Calculator & Export")
    parser.add_argument(
        "--category",
        type=str,
        help="Product category for full export (e.g., '로봇청소기')",
    )
    parser.add_argument(
        "--product-id",
        type=int,
        help="Single product database ID to calculate TCO for",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path",
    )

    args = parser.parse_args()

    if not args.category and not args.product_id:
        parser.error("Either --category or --product-id is required")

    config = Config()
    init_db(config)

    if args.category:
        exporter = TCOExporter(config)
        export = exporter.export_category(args.category, args.output)

        logger.info("=== TCO Category Export: %s ===", args.category)
        logger.info("Products: %d", len(export["products"]))

        for product in export["products"]:
            tco = product["tco"]
            logger.info(
                "  %s (%s): purchase=%s, resale=%s, repair=%s → real_cost=%s원",
                product["name"],
                product["brand"],
                f"{tco['purchase_price_avg']:,}",
                f"{tco['resale_value_24mo']:,}",
                f"{tco['expected_repair_cost']:,}",
                f"{tco['real_cost_3yr']:,}",
            )
            logger.info(
                "    AS: %.1f days, Maintenance: %.1f min/month",
                tco["as_turnaround_days"],
                tco["monthly_maintenance_minutes"],
            )

    elif args.product_id:
        calculator = TCOCalculator(config)
        tco = calculator.calculate_for_product(args.product_id)

        logger.info("=== TCO for %s ===", tco["product_name"])
        tco_data = tco["tco"]
        for key, value in tco_data.items():
            logger.info("  %s: %s", key, f"{value:,}" if isinstance(value, int) else value)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(tco, f, ensure_ascii=False, indent=2, default=str)
            logger.info("Output written to %s", args.output)


if __name__ == "__main__":
    main()
