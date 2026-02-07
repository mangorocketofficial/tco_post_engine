"""Shared test fixtures for Part A tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.part_a.common.config import Config
from src.part_a.database.connection import init_db, get_connection

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def temp_db(tmp_path: Path) -> Config:
    """Provide a Config pointing to a temporary SQLite database."""
    config = Config()
    config.database_path = str(tmp_path / "test.db")
    config.raw_html_cache_dir = str(tmp_path / "raw_html")
    init_db(config)
    return config


@pytest.fixture
def db_conn(temp_db: Config) -> sqlite3.Connection:
    """Provide an open database connection for tests."""
    conn = get_connection(temp_db)
    yield conn
    conn.close()
