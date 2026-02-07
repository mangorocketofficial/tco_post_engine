"""CLI entry point for the price tracker module.

Usage:
    python -m src.part_a.price_tracker.main --keyword "로봇청소기"
    python -m src.part_a.price_tracker.main --product-code 12345678
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from ..common.config import Config
from ..database.connection import init_db
from .danawa_scraper import DanawaScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Danawa Price Tracker")
    parser.add_argument(
        "--keyword",
        type=str,
        help="Search keyword (e.g., '로봇청소기')",
    )
    parser.add_argument(
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

    if not args.keyword and not args.product_code:
        parser.error("Either --keyword or --product-code is required")

    config = Config()

    if args.save_db:
        init_db(config)

    with DanawaScraper(config) as scraper:
        all_records = []

        if args.keyword:
            logger.info("Searching Danawa for: %s", args.keyword)
            products = scraper.search_products(args.keyword, args.max_results)

            for product in products:
                logger.info(
                    "  [%s] %s — %s원",
                    product["product_code"],
                    product["name"],
                    f"{product['price']:,}",
                )
                records = scraper.get_product_prices(product["product_code"])
                all_records.extend(records)

        elif args.product_code:
            logger.info("Fetching prices for product: %s", args.product_code)
            records = scraper.get_product_prices(args.product_code)
            all_records.extend(records)

            logger.info("Fetching price history...")
            history = scraper.get_price_history(args.product_code)
            all_records.extend(history)

        logger.info("Total records collected: %d", len(all_records))

        if args.save_db and all_records:
            inserted = scraper.save_prices_to_db(all_records)
            logger.info("Saved %d new records to database", inserted)

        if args.output:
            output_data = [r.to_dict() for r in all_records]
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            logger.info("Output written to %s", args.output)


if __name__ == "__main__":
    main()
