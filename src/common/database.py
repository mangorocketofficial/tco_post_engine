"""SQLite database utilities for TCO Post Engine.

Provides connection management and table initialization.
All modules use this for data persistence.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import settings

# SQL for creating the core tables
_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    release_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    date TEXT NOT NULL,
    price INTEGER NOT NULL,
    source TEXT NOT NULL,
    is_sale INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS resale_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    sale_price INTEGER NOT NULL,
    listing_date TEXT NOT NULL,
    months_since_release INTEGER NOT NULL,
    condition TEXT NOT NULL DEFAULT 'good',
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS repair_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    failure_type TEXT NOT NULL,
    repair_cost INTEGER NOT NULL,
    as_days INTEGER NOT NULL,
    sentiment TEXT NOT NULL DEFAULT 'neutral',
    source TEXT NOT NULL,
    source_url TEXT DEFAULT '',
    date TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS maintenance_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    task TEXT NOT NULL,
    frequency_per_month REAL NOT NULL,
    minutes_per_task REAL NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS tco_summaries (
    product_id TEXT PRIMARY KEY,
    purchase_price_avg INTEGER NOT NULL,
    purchase_price_min INTEGER NOT NULL,
    resale_value_1yr INTEGER NOT NULL DEFAULT 0,
    resale_value_2yr INTEGER NOT NULL DEFAULT 0,
    resale_value_3yr_plus INTEGER NOT NULL DEFAULT 0,
    expected_repair_cost INTEGER NOT NULL,
    real_cost_3yr INTEGER NOT NULL,
    as_turnaround_days REAL NOT NULL,
    monthly_maintenance_minutes REAL NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE INDEX IF NOT EXISTS idx_prices_product_date ON prices(product_id, date);
CREATE INDEX IF NOT EXISTS idx_resale_product ON resale_transactions(product_id);
CREATE INDEX IF NOT EXISTS idx_repair_product ON repair_reports(product_id);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    path = db_path or settings.database.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    """Create all tables if they don't exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript(_CREATE_TABLES_SQL)
        conn.commit()
    finally:
        conn.close()
