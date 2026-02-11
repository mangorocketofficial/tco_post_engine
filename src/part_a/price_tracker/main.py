"""CLI entry point for the price tracker module.

Usage:
    # Primary mode — reads A0 JSON and scrapes per-product prices:
    python -m src.part_a.price_tracker.main \
        --a0-data data/processed/a0_selected_전기면도기.json \
        --save-db --output data/processed/a1_prices_전기면도기.json

    # Debug / manual modes (unchanged):
    python -m src.part_a.price_tracker.main --keyword "로봇청소기"
    python -m src.part_a.price_tracker.main --product-code 12345678
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..common.config import Config
from ..database.connection import init_db
from .danawa_scraper import (
    DanawaScraper,
    compute_name_similarity,
    filter_prices_a0_reference,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Minimum similarity ratio to accept a Danawa search result as a match.
# Set at 0.3 because Naver Shopping names are verbose (marketing text, retailer
# names, color variants) while Danawa names are concise — matching the core
# identifiers (brand + model number) typically yields 0.3-0.4 overlap.
NAME_MATCH_THRESHOLD = 0.3


def _run_a0_mode(
    scraper: DanawaScraper,
    a0_path: str,
    *,
    save_db: bool,
    output_path: str | None,
) -> None:
    """Primary pipeline mode: read A0 JSON, scrape per-product prices."""
    a0_data = json.loads(Path(a0_path).read_text(encoding="utf-8"))
    category = a0_data.get("category", "unknown")
    final_products = (
        a0_data.get("selected_products")
        or a0_data.get("final_products")
        or []
    )

    if not final_products:
        logger.error("No products found in A0 data: %s", a0_path)
        sys.exit(1)

    logger.info(
        "A0 data loaded: category=%s, %d products", category, len(final_products)
    )

    product_results: list[dict] = []

    for a0_product in final_products:
        a0_name: str = a0_product["name"]
        a0_price: int = a0_product.get("price", 0) or 0

        logger.info("--- Processing: %s (A0 price: %s원) ---", a0_name, f"{a0_price:,}")

        # Step 1: Search Danawa for this product
        search_results = scraper.search_products(a0_name, max_results=5)

        if not search_results:
            logger.warning("No Danawa search results for '%s' — skipping", a0_name)
            product_results.append(_empty_product_result(a0_name))
            continue

        # Step 2: Score search results by name similarity
        best_match = None
        best_score = 0.0
        for sr in search_results:
            score = compute_name_similarity(a0_name, sr["name"])
            logger.debug(
                "  Match score %.2f: %s", score, sr["name"]
            )
            if score > best_score:
                best_score = score
                best_match = sr

        if best_score < NAME_MATCH_THRESHOLD:
            logger.warning(
                "No Danawa result meets %.0f%% threshold for '%s' (best: %.2f '%s') — skipping",
                NAME_MATCH_THRESHOLD * 100,
                a0_name,
                best_score,
                best_match["name"] if best_match else "N/A",
            )
            product_results.append(_empty_product_result(a0_name))
            continue

        assert best_match is not None
        danawa_code = best_match["product_code"]
        danawa_name = best_match["name"]
        logger.info(
            "  Best match: [%s] %s (score: %.2f)", danawa_code, danawa_name, best_score
        )

        # Step 3: Scrape prices (Layer 1 + Layer 2 applied inside get_product_prices)
        records = scraper.get_product_prices(danawa_code)
        records_after_l2 = len(records)

        # Step 4: Layer 3 — A0 reference price cross-check
        before_l3 = len(records)
        records = filter_prices_a0_reference(records, a0_price)
        removed_l3 = before_l3 - len(records)

        if removed_l3:
            logger.info(
                "  Layer 3 removed %d records (A0 ref price: %s원)",
                removed_l3, f"{a0_price:,}",
            )

        # Step 5: Save to DB
        if save_db and records:
            inserted = scraper.save_prices_to_db(records)
            logger.info("  Saved %d records to DB", inserted)

        # Step 6: Compute summary
        prices = [r.price for r in records]
        avg_price = int(sum(prices) / len(prices)) if prices else 0
        min_price = min(prices) if prices else 0

        filter_log = (
            f"Layer 1: floor<{DanawaScraper.MIN_PRICE_FLOOR} applied at parse, "
            f"Layer 2: IQR→{records_after_l2} records, "
            f"Layer 3: A0 ref removed {removed_l3}"
        )

        product_results.append({
            "product_name": a0_name,
            "danawa_product_code": danawa_code,
            "danawa_product_name": danawa_name,
            "match_score": round(best_score, 3),
            "purchase_price_avg": avg_price,
            "purchase_price_min": min_price,
            "price_records": [r.to_dict() for r in records],
            "records_before_filter": records_after_l2 + removed_l3,
            "records_after_filter": len(records),
            "filter_log": filter_log,
        })

        logger.info(
            "  Result: avg=%s원, min=%s원, %d records",
            f"{avg_price:,}", f"{min_price:,}", len(records),
        )

    # Build structured output
    output_data = {
        "category": category,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "products": product_results,
    }

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Output written to %s", output_path)

    # Summary
    logger.info("=== A1 Summary: %d/%d products matched ===",
                sum(1 for p in product_results if p.get("danawa_product_code")),
                len(final_products))


def _empty_product_result(a0_name: str) -> dict:
    """Placeholder for a product that could not be matched on Danawa."""
    return {
        "product_name": a0_name,
        "danawa_product_code": None,
        "danawa_product_name": None,
        "match_score": 0.0,
        "purchase_price_avg": 0,
        "purchase_price_min": 0,
        "price_records": [],
        "records_before_filter": 0,
        "records_after_filter": 0,
        "filter_log": "No Danawa match found",
    }


def _run_keyword_mode(
    scraper: DanawaScraper,
    keyword: str,
    max_results: int,
    *,
    save_db: bool,
    output_path: str | None,
) -> None:
    """Legacy keyword-search mode for manual / debug use."""
    logger.info("Searching Danawa for: %s", keyword)
    products = scraper.search_products(keyword, max_results)

    all_records = []
    for product in products:
        logger.info(
            "  [%s] %s — %s원",
            product["product_code"],
            product["name"],
            f"{product['price']:,}",
        )
        records = scraper.get_product_prices(product["product_code"])
        all_records.extend(records)

    logger.info("Total records collected: %d", len(all_records))

    if save_db and all_records:
        inserted = scraper.save_prices_to_db(all_records)
        logger.info("Saved %d new records to database", inserted)

    if output_path:
        output_data = [r.to_dict() for r in all_records]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info("Output written to %s", output_path)


def _run_product_code_mode(
    scraper: DanawaScraper,
    product_code: str,
    *,
    save_db: bool,
    output_path: str | None,
) -> None:
    """Single product-code mode for manual / debug use."""
    logger.info("Fetching prices for product: %s", product_code)
    all_records = scraper.get_product_prices(product_code)

    logger.info("Fetching price history...")
    history = scraper.get_price_history(product_code)
    all_records.extend(history)

    logger.info("Total records collected: %d", len(all_records))

    if save_db and all_records:
        inserted = scraper.save_prices_to_db(all_records)
        logger.info("Saved %d new records to database", inserted)

    if output_path:
        output_data = [r.to_dict() for r in all_records]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info("Output written to %s", output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Danawa Price Tracker")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--a0-data",
        type=str,
        help="Path to A0 JSON (primary pipeline mode)",
    )
    group.add_argument(
        "--keyword",
        type=str,
        help="Search keyword — debug/manual mode (e.g., '로봇청소기')",
    )
    group.add_argument(
        "--product-code",
        type=str,
        help="Danawa product code to fetch prices for",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Max search results (default: 5)",
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

    config = Config()

    if args.save_db:
        init_db(config)

    with DanawaScraper(config) as scraper:
        if args.a0_data:
            _run_a0_mode(
                scraper,
                args.a0_data,
                save_db=args.save_db,
                output_path=args.output,
            )
        elif args.keyword:
            _run_keyword_mode(
                scraper,
                args.keyword,
                args.max_results,
                save_db=args.save_db,
                output_path=args.output,
            )
        elif args.product_code:
            _run_product_code_mode(
                scraper,
                args.product_code,
                save_db=args.save_db,
                output_path=args.output,
            )


if __name__ == "__main__":
    main()
