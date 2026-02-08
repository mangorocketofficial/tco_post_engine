"""CLI entry point for the product selector module (A-0 / A-0.1 / Final).

Usage:
    # A-0: Select TOP 3 products for TCO comparison
    python -m src.part_a.product_selector.main --category "로봇청소기"
    python -m src.part_a.product_selector.main --config config/category_robot_vacuum.yaml

    # A-0.1: Find most recommended products from blog search
    python -m src.part_a.product_selector.main --mode recommend --keyword "드럼세탁기"
    python -m src.part_a.product_selector.main --mode recommend --keyword "드럼세탁기" --top-n 3

    # Final: Merge A-0 + A-0.1 into final Top 3
    python -m src.part_a.product_selector.main --mode final --keyword "드럼세탁기"
"""

from __future__ import annotations

import argparse
import json
import logging

from ..common.config import Config
from ..database.connection import init_db
from .category_config import CategoryConfig
from .final_selector import FinalSelector
from .pipeline import ProductSelectionPipeline
from .recommendation_pipeline import RecommendationPipeline

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
    result = pipeline.run()

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


def _run_recommend(args: argparse.Namespace) -> None:
    """A-0.1: Blog recommendation pipeline."""
    if not args.keyword:
        raise SystemExit("Error: --keyword is required for 'recommend' mode")

    pipeline = RecommendationPipeline()
    result = pipeline.run(args.keyword, top_n=args.top_n)

    logger.info("=== Recommendation Results ===")
    logger.info("Keyword: %s", result.keyword)
    logger.info("Query: %s", result.search_query)
    logger.info("Blogs searched: %d", result.total_blogs_searched)
    logger.info("Products extracted: %d", result.total_products_extracted)

    for i, p in enumerate(result.top_products, 1):
        logger.info("  Top %d: %s (mentioned %d times)", i, p.product_name, p.mention_count)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("Output written to %s", args.output)


def _run_final(args: argparse.Namespace) -> None:
    """Integrated A-0 + A-0.1 final selection pipeline."""
    keyword = args.keyword or args.category
    if not keyword and not args.config:
        raise SystemExit("Error: --keyword, --category, or --config is required for 'final' mode")

    config = Config()

    if args.config:
        cat_config = CategoryConfig.from_yaml(args.config)
        keyword = keyword or (cat_config.search_terms[0] if cat_config.search_terms else cat_config.name)
    else:
        cat_config = CategoryConfig.from_category_name(keyword)

    # Phase 1: A-0
    logger.info("=== Phase 1: A-0 Product Selection ===")
    a0_pipeline = ProductSelectionPipeline(cat_config, config)
    a0_result = a0_pipeline.run()

    # Phase 2: A-0.1
    logger.info("=== Phase 2: A-0.1 Blog Recommendation ===")
    a0_1_pipeline = RecommendationPipeline()
    a0_1_result = a0_1_pipeline.run(keyword, top_n=2)

    # Phase 3: Merge
    logger.info("=== Phase 3: Final Merge ===")
    selector = FinalSelector()
    final_result = selector.merge(a0_result, a0_1_result)

    # Log results
    logger.info("=== Final Selection Results: %s ===", final_result.category)
    logger.info("Merge case: %s", final_result.merge_case)
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
        description="A-0 Product Selector / A-0.1 Recommendation / Final Merge"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["select", "recommend", "final"],
        default="select",
        help="Pipeline mode: 'select' (A-0), 'recommend' (A-0.1), or 'final' (merged)",
    )
    parser.add_argument(
        "--category",
        type=str,
        help="[select] Category name (e.g., '로봇청소기')",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="[select] Path to category config YAML file",
    )
    parser.add_argument(
        "--keyword",
        type=str,
        help="[recommend] Category keyword (e.g., '드럼세탁기')",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=2,
        help="[recommend] Number of top products to return (default: 2)",
    )
    parser.add_argument(
        "--save-db",
        action="store_true",
        help="[select] Save selection result to SQLite database",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path",
    )

    args = parser.parse_args()

    if args.mode == "recommend":
        _run_recommend(args)
    elif args.mode == "final":
        _run_final(args)
    else:
        _run_select(args)


if __name__ == "__main__":
    main()
