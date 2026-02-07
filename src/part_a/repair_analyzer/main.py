"""CLI entry point for the repair analyzer module.

Usage:
    python -m src.part_a.repair_analyzer.main --product "로보락 S8 Pro Ultra"
    python -m src.part_a.repair_analyzer.main --product "로보락 S8 Pro Ultra" --mock
"""

from __future__ import annotations

import argparse
import json
import logging

from ..common.config import Config
from ..database.connection import init_db, get_connection
from .community_scraper import CommunityScraper
from .gpt_extractor import GPTExtractor, MockGPTExtractor
from .models import calculate_repair_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_REPAIR_KEYWORDS = ["수리", "AS", "고장", "서비스센터", "교체", "부품"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair & AS Analyzer")
    parser.add_argument(
        "--product",
        type=str,
        required=True,
        help="Product name (e.g., '로보락 S8 Pro Ultra')",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        nargs="+",
        default=DEFAULT_REPAIR_KEYWORDS,
        help="Repair search keywords",
    )
    parser.add_argument(
        "--max-per-source",
        type=int,
        default=20,
        help="Max posts per source (default: 20)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock GPT extractor (no API key needed)",
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

    # Scrape community posts
    with CommunityScraper(config) as scraper:
        logger.info("Searching communities for: %s", args.product)
        posts = scraper.search_all(
            args.product, args.keywords, args.max_per_source
        )
        logger.info("Collected %d community posts", len(posts))

    # Extract repair data
    if args.mock:
        extractor = MockGPTExtractor()
    else:
        extractor = GPTExtractor()

    records = extractor.extract_batch(posts, args.product)
    logger.info("Extracted %d repair records", len(records))

    for record in records:
        logger.info(
            "  [%s] %s — %s원, AS %s일 (%s)",
            record.failure_type,
            record.product_name[:30],
            f"{record.repair_cost:,}" if record.repair_cost else "N/A",
            record.as_days or "N/A",
            record.sentiment,
        )

    # Calculate stats
    stats = calculate_repair_stats(records)
    logger.info(
        "Expected repair cost: %s원 (from %d reports)",
        f"{stats.expected_repair_cost:,}",
        stats.total_reports,
    )
    logger.info("Avg AS turnaround: %.1f days", stats.avg_as_days)

    # Save to database
    if args.save_db and records:
        inserted = save_records_to_db(records, config)
        logger.info("Saved %d records to database", inserted)

    # Output JSON
    output_data = {
        "product": args.product,
        "total_posts_scraped": len(posts),
        "total_records_extracted": len(records),
        "stats": stats.to_dict(),
        "records": [r.to_dict() for r in records],
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info("Output written to %s", args.output)


def save_records_to_db(records: list, config: Config) -> int:
    """Save repair records to the database."""
    conn = get_connection(config)
    inserted = 0
    try:
        for record in records:
            product_id = _ensure_product(conn, record.product_name)
            conn.execute(
                """INSERT INTO repair_reports
                   (product_id, failure_type, repair_cost, as_days,
                    sentiment, source_url, date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    product_id,
                    record.failure_type,
                    record.repair_cost,
                    record.as_days,
                    record.sentiment,
                    record.source_url,
                    record.date.isoformat() if record.date else None,
                ),
            )
            inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted


def _ensure_product(conn, product_name: str) -> int:
    """Get or create a product row, return its ID."""
    row = conn.execute(
        "SELECT id FROM products WHERE name = ?", (product_name,)
    ).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO products (name, brand, category) VALUES (?, ?, ?)",
        (product_name, "", ""),
    )
    return cursor.lastrowid


if __name__ == "__main__":
    main()
