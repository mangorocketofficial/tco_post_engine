"""CLI entry point for the product selector module (A-0).

Usage:
    python -m src.part_a.product_selector.main --category "로봇청소기"
    python -m src.part_a.product_selector.main --config config/category_robot_vacuum.yaml
    python -m src.part_a.product_selector.main --category "로봇청소기" --save-db --output data/selection.json
"""

from __future__ import annotations

import argparse
import json
import logging

from ..common.config import Config
from ..database.connection import init_db
from .category_config import CategoryConfig
from .pipeline import ProductSelectionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A-0 Product Selector — select optimal 3 products for TCO comparison"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Category name (e.g., '로봇청소기'). Uses default config.",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to category config YAML file",
    )
    parser.add_argument(
        "--save-db",
        action="store_true",
        help="Save selection result to SQLite database",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path",
    )

    args = parser.parse_args()

    if not args.category and not args.config:
        parser.error("Either --category or --config is required")

    config = Config()

    if args.save_db:
        init_db(config)

    # Load category config
    if args.config:
        cat_config = CategoryConfig.from_yaml(args.config)
    else:
        cat_config = CategoryConfig.default_robot_vacuum()

    # Run pipeline
    pipeline = ProductSelectionPipeline(cat_config, config)
    result = pipeline.run()

    # Log results
    logger.info("=== Product Selection Results: %s ===", result.category)
    logger.info("Candidate pool: %d products", result.candidate_pool_size)

    for slot in result.selected_products:
        tier = (
            slot.candidate.price_position.price_tier
            if slot.candidate.price_position
            else "N/A"
        )
        logger.info(
            "  [%s] %s (%s) — %s tier",
            slot.slot.upper(),
            slot.candidate.name,
            slot.candidate.brand,
            tier,
        )
        for reason in slot.selection_reasons:
            logger.info("    - %s", reason)

    logger.info("Validation:")
    for v in result.validation:
        status = "PASS" if v.passed else "FAIL"
        logger.info("  %s: %s — %s", v.check_name, status, v.detail)

    # Save
    if args.save_db:
        pipeline.save_to_db(result)
        logger.info("Saved to database")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("Output written to %s", args.output)


if __name__ == "__main__":
    main()
