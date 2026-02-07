"""SQLite database connection and schema management."""

from __future__ import annotations

import sqlite3
import logging
from pathlib import Path

from ..common.config import Config

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    release_date TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_products_name_brand
    ON products(name, brand);

CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    price INTEGER NOT NULL,
    source TEXT NOT NULL,
    is_sale INTEGER DEFAULT 0,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_prices_product_date
    ON prices(product_id, date);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prices_unique
    ON prices(product_id, date, source);

CREATE TABLE IF NOT EXISTS resale_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    sale_price INTEGER NOT NULL,
    months_since_release REAL,
    condition TEXT DEFAULT 'used',
    listing_date TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_resale_product
    ON resale_transactions(product_id);

CREATE TABLE IF NOT EXISTS repair_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    failure_type TEXT NOT NULL,
    repair_cost INTEGER NOT NULL,
    as_days INTEGER,
    sentiment TEXT DEFAULT 'neutral',
    source_url TEXT,
    date TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS maintenance_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    task TEXT NOT NULL,
    frequency_per_month REAL NOT NULL,
    minutes_per_task REAL NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS product_selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    selection_date TEXT NOT NULL,
    candidate_pool_size INTEGER,
    result_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_selections_category_date
    ON product_selections(category, selection_date);
"""


def get_connection(config: Config | None = None) -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled.

    Args:
        config: Optional Config. Uses defaults if not provided.

    Returns:
        sqlite3.Connection with Row factory.
    """
    config = config or Config()
    db_path = config.database_abs_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(config: Config | None = None) -> None:
    """Initialize database schema (idempotent).

    Args:
        config: Optional Config. Uses defaults if not provided.
    """
    conn = get_connection(config)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        logger.info("Database schema initialized at %s", config or Config())
    finally:
        conn.close()
