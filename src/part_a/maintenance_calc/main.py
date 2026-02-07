"""CLI entry point for the maintenance calculator module.

Usage:
    python -m src.part_a.maintenance_calc.main
    python -m src.part_a.maintenance_calc.main --product "로보락 S8 Pro Ultra"
    python -m src.part_a.maintenance_calc.main --all --save-db
"""

from __future__ import annotations

import argparse
import json
import logging

from ..common.config import Config
from ..database.connection import init_db
from .calculator import MaintenanceCalculator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintenance Time Calculator")
    parser.add_argument(
        "--product",
        type=str,
        help="Product name (e.g., '로보락 S8 Pro Ultra')",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Calculate for all configured products",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to product config YAML (default: config/products_robot_vacuum.yaml)",
    )
    parser.add_argument(
        "--save-db",
        action="store_true",
        help="Save results to SQLite database",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path",
    )

    args = parser.parse_args()

    if not args.product and not args.all:
        parser.error("Either --product or --all is required")

    config = Config()

    if args.save_db:
        init_db(config)

    calc = MaintenanceCalculator(config=config, config_path=args.config)

    summaries = []

    if args.all:
        logger.info("Calculating maintenance for all products...")
        summaries = calc.calculate_all_products()
    elif args.product:
        logger.info("Calculating maintenance for: %s", args.product)
        summary = calc.calculate_for_product(args.product)
        summaries.append(summary)

    for summary in summaries:
        logger.info(
            "  %s: %.1f min/month (%.1f hrs/3yr)",
            summary.product_name,
            summary.total_monthly_minutes,
            summary.total_3yr_hours,
        )
        for task in summary.tasks:
            logger.info(
                "    - %s: %g×/month × %g min = %.1f min/month",
                task.task,
                task.frequency_per_month,
                task.minutes_per_task,
                task.total_monthly_minutes,
            )

        if args.save_db:
            inserted = calc.save_to_db(summary)
            logger.info("  Saved %d tasks to database", inserted)

    if args.output:
        output_data = [s.to_dict() for s in summaries]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info("Output written to %s", args.output)


if __name__ == "__main__":
    main()
