"""CLI entry point for the product selector module (A-0).

Usage:
    # A-0: Select TOP 3 products for TCO comparison
    python -m src.part_a.product_selector.main --category "로봇청소기"
    python -m src.part_a.product_selector.main --config config/category_robot_vacuum.yaml

    # Final: A-0 TOP 3 selection (tier-based)
    python -m src.part_a.product_selector.main --mode final --keyword "드럼세탁기"
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date

from ..common.config import Config
from ..database.connection import init_db
from .category_config import CategoryConfig
from .models import FinalProduct, FinalSelectionResult
from .pipeline import ProductSelectionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _run_select(args: argparse.Namespace) -> None:
    """A-0: Product selection pipeline."""
    if not args.category and not args.config:
        raise SystemExit("Error: --category or --config is required for 'select' mode")

    config = Config()

    if args.save_db:
        init_db(config)

    if args.config:
        cat_config = CategoryConfig.from_yaml(args.config)
    else:
        cat_config = CategoryConfig.from_category_name(args.category)

    pipeline = ProductSelectionPipeline(cat_config, config)
    result = pipeline.run(force_tier=getattr(args, "tier", "") or "")

    logger.info("=== Product Selection Results: %s ===", result.category)
    logger.info("Candidate pool: %d products", result.candidate_pool_size)

    for pick in result.selected_products:
        logger.info(
            "  #%d: %s (%s) — %s원 — score=%.3f",
            pick.rank,
            pick.candidate.name,
            pick.candidate.brand,
            f"{pick.candidate.price:,}" if pick.candidate.price else "N/A",
            pick.scores.total_score,
        )
        for reason in pick.selection_reasons:
            logger.info("    - %s", reason)

    logger.info("Validation:")
    for v in result.validation:
        status = "PASS" if v.passed else "FAIL"
        logger.info("  %s: %s — %s", v.check_name, status, v.detail)

    if args.save_db:
        pipeline.save_to_db(result)
        logger.info("Saved to database")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("Output written to %s", args.output)


def _run_final(args: argparse.Namespace) -> None:
    """A-0 final selection pipeline — TOP 3 from tier-based selection only."""
    keyword = args.keyword or args.category
    if not keyword and not args.config:
        raise SystemExit("Error: --keyword, --category, or --config is required for 'final' mode")

    config = Config()

    if args.config:
        cat_config = CategoryConfig.from_yaml(args.config)
        keyword = keyword or (cat_config.search_terms[0] if cat_config.search_terms else cat_config.name)
    else:
        cat_config = CategoryConfig.from_category_name(keyword)

    # A-0: Product Selection
    logger.info("=== A-0 Product Selection ===")
    a0_pipeline = ProductSelectionPipeline(cat_config, config)
    a0_result = a0_pipeline.run(force_tier=getattr(args, "tier", "") or "")

    # Build final result directly from A-0 TOP 3
    final_products: list[FinalProduct] = []
    for sp in a0_result.selected_products[:3]:
        final_products.append(FinalProduct(
            rank=sp.rank,
            name=sp.candidate.name,
            brand=sp.candidate.brand,
            price=sp.candidate.price,
            source="a0",
            selection_reasons=list(sp.selection_reasons),
            a0_rank=sp.rank,
            a0_scores=sp.scores,
        ))

    final_result = FinalSelectionResult(
        category=a0_result.category,
        selection_date=date.today(),
        merge_case="a0_only",
        a0_result=a0_result,
        final_products=final_products,
    )

    # Log results
    logger.info("=== Final Selection Results: %s ===", final_result.category)
    for fp in final_result.final_products:
        logger.info(
            "  #%d: %s — source=%s — price=%s",
            fp.rank, fp.name, fp.source,
            f"{fp.price:,}원" if fp.price else "N/A",
        )
        for reason in fp.selection_reasons:
            logger.info("    - %s", reason)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(final_result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("Output written to %s", args.output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A-0 Product Selector"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["select", "final"],
        default="select",
        help="Pipeline mode: 'select' (A-0) or 'final' (A-0 TOP 3 output)",
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Category name (e.g., '로봇청소기')",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to category config YAML file",
    )
    parser.add_argument(
        "--keyword",
        type=str,
        help="Category keyword (e.g., '드럼세탁기')",
    )
    parser.add_argument(
        "--tier",
        type=str,
        choices=["premium", "mid", "budget"],
        default=None,
        help="Force tier selection instead of auto-selecting winning tier",
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

    if args.mode == "final":
        _run_final(args)
    else:
        _run_select(args)


if __name__ == "__main__":
    main()
