"""CLI entry point for the resale tracker module.

Usage:
    python -m src.part_a.resale_tracker.main --keyword "로보락 Q Revo S"
    python -m src.part_a.resale_tracker.main --keyword "로보락 Q Revo S" --original-price 1500000
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from ..common.config import Config
from ..database.connection import init_db
from .danggeun_scraper import DanggeunScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Danggeun Resale Tracker")
    parser.add_argument(
        "--keyword",
        type=str,
        required=True,
        help="Product search keyword (e.g., '로보락 Q Revo S')",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=30,
        help="Max listings to collect (default: 30)",
    )
    parser.add_argument(
        "--original-price",
        type=int,
        help="Original retail price (KRW) for retention curve calculation",
    )
    parser.add_argument(
        "--release-date",
        type=str,
        help="Product release date (YYYY-MM-DD) for age calculation",
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

    release_date = None
    if args.release_date:
        release_date = date.fromisoformat(args.release_date)

    with DanggeunScraper(config) as scraper:
        logger.info("Searching Danggeun Market for: %s", args.keyword)
        records = scraper.search_sold_items(args.keyword, args.max_results)

        for record in records:
            logger.info(
                "  [%s] %s — %s원 (%s)",
                record.condition,
                record.product_name[:40],
                f"{record.sale_price:,}",
                record.listing_date or "unknown date",
            )

        if args.save_db and records:
            inserted = scraper.save_records_to_db(records)
            logger.info("Saved %d records to database", inserted)

        output_data: dict = {
            "keyword": args.keyword,
            "total_sold_listings": len(records),
            "records": [r.to_dict() for r in records],
        }

        if args.original_price and records:
            curve = scraper.calculate_retention_curve(
                records,
                original_price=args.original_price,
                release_date=release_date,
            )
            output_data["retention_curve"] = curve.to_dict()
            logger.info("Retention curve: %s", curve.to_dict()["resale_curve"])

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            logger.info("Output written to %s", args.output)


if __name__ == "__main__":
    main()
