"""Test A0 product selector with electric razor keyword."""
import json
import logging
from pathlib import Path

from src.part_a.common.config import Config
from src.part_a.product_selector.category_config import CategoryConfig
from src.part_a.product_selector.pipeline import ProductSelectionPipeline

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Run A0 product selector with 전기면도기 keyword."""
    logger.info("=" * 80)
    logger.info("Testing A0 Product Selector: 전기면도기")
    logger.info("=" * 80)

    # Create a minimal category config for testing
    category_config = CategoryConfig.from_category_name("전기면도기")

    # Initialize config and pipeline
    config = Config()
    pipeline = ProductSelectionPipeline(
        category_config=category_config,
        config=config,
        recommendation_result=None,  # No A0.1 for now
    )

    try:
        # Run the pipeline
        result = pipeline.run()

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("RESULTS")
        logger.info("=" * 80)

        logger.info(f"\nCandidate pool size: {result.candidate_pool_size}")
        logger.info(f"Selected products: {len(result.selected_products)}\n")

        for i, product in enumerate(result.selected_products):
            logger.info(f"--- Product #{i+1} ---")
            logger.info(f"  Rank: {product.rank}")
            logger.info(f"  Name: {product.candidate.name}")
            logger.info(f"  Brand: {product.candidate.brand}")
            logger.info(f"  Price: {product.candidate.price:,}원")
            logger.info(f"  Slot: {product.slot}")
            logger.info(f"  Manufacturer: {product.candidate.manufacturer}")
            logger.info(f"  Total Score: {product.scores.total_score:.3f}")
            logger.info(f"  Reasons:")
            for reason in product.selection_reasons:
                logger.info(f"    - {reason}")
            logger.info("")

        logger.info("--- Validation ---")
        for validation in result.validation:
            status = "✓" if validation.passed else "✗"
            logger.info(f"  {status} {validation.check_name}: {validation.detail}")

        # Save to JSON
        output_path = Path("data/processed/a0_selected_전기면도기.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"\n✓ Results saved to: {output_path}")

        # Check for price-tier collapse (the original bug)
        slots = [p.slot for p in result.selected_products]
        unique_slots = set(slots)

        logger.info("\n" + "=" * 80)
        logger.info("PRICE-TIER ANALYSIS")
        logger.info("=" * 80)

        if len(unique_slots) == 3:
            logger.info("✓ SUCCESS: All 3 slots filled (stability, balance, value)")
            logger.info("✓ No price-tier collapse detected!")
        else:
            logger.warning(f"⚠ WARNING: Only {len(unique_slots)} unique slots: {unique_slots}")
            logger.warning("⚠ Price-tier collapse may have occurred")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
