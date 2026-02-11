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

CREATE INDEX IF NOT EXISTS idx_prices_product_date ON prices(product_id, date);
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
