"""CLI entry point for the multi-platform resale tracker.

Usage:
    python -m src.part_a.resale_tracker.main --keyword "로보락 Q Revo S"
    python -m src.part_a.resale_tracker.main --keyword "삼성 김치플러스" --platform all
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
from .bunjang_scraper import BunjangScraper
from .danggeun_scraper import DanggeunScraper
from .models import ResaleRecord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Registry of available scrapers
SCRAPERS = {
    "danggeun": DanggeunScraper,
    "bunjang": BunjangScraper,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Platform Resale Tracker")
    parser.add_argument(
        "--keyword",
        type=str,
        required=True,
        help="Product search keyword (e.g., '로보락 Q Revo S')",
    )
    parser.add_argument(
        "--platform",
        type=str,
        nargs="+",
        default=["all"],
        choices=["danggeun", "bunjang", "all"],
        help="Platforms to search (default: all)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=30,
        help="Max listings per platform (default: 30)",
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

    # Determine which platforms to search
    platforms = list(SCRAPERS.keys()) if "all" in args.platform else args.platform

    all_records: list[ResaleRecord] = []

    for platform_name in platforms:
        scraper_cls = SCRAPERS[platform_name]
        with scraper_cls(config) as scraper:
            logger.info("Searching %s for: %s", platform_name, args.keyword)
            records = scraper.search_sold_items(args.keyword, args.max_results)
            all_records.extend(records)

            if args.save_db and records:
                inserted = scraper.save_records_to_db(records)
                logger.info("Saved %d records from %s", inserted, platform_name)

    # Log results
    for record in all_records:
        logger.info(
            "  [%s][%s] %s — %s원 (%s)",
            record.platform,
            record.condition,
            record.product_name[:40],
            f"{record.sale_price:,}",
            record.listing_date or "unknown date",
        )

    output_data: dict = {
        "keyword": args.keyword,
        "platforms": platforms,
        "total_sold_listings": len(all_records),
        "records_by_platform": {
            p: sum(1 for r in all_records if r.platform == p)
            for p in platforms
        },
        "records": [r.to_dict() for r in all_records],
    }

    if args.original_price and all_records:
        # Use any scraper instance for the shared calculation
        scraper_cls = SCRAPERS[platforms[0]]
        with scraper_cls(config) as scraper:
            curve = scraper.calculate_retention_curve(
                all_records,
                original_price=args.original_price,
                release_date=release_date,
            )
            output_data["retention_curve"] = curve.to_dict()
            logger.info(
                "Retention curve: %s | Median prices: %s",
                curve.to_dict()["resale_curve"],
                curve.to_dict()["median_prices"],
            )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info("Output written to %s", args.output)


if __name__ == "__main__":
    main()
