"""Shared test fixtures for TCO Post Engine."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure src is importable
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.part_a.common.config import Config
from src.part_a.database.connection import init_db, get_connection


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the test fixtures directory."""
    return PROJECT_ROOT / "tests" / "fixtures"


@pytest.fixture
def temp_db(tmp_path):
    """Provide a Config pointing to a temporary SQLite database."""
    db_file = tmp_path / "test_tco.db"
    config = Config(database_path=str(db_file))
    init_db(config)
    return config


@pytest.fixture
def db_conn(temp_db):
    """Provide an initialized SQLite connection from temp_db."""
    conn = get_connection(temp_db)
    yield conn
    conn.close()


@pytest.fixture
def sample_product_data() -> dict:
    """Return sample product data for testing."""
    return {
        "product_id": "test-roborock-s8-pro",
        "name": "로보락 S8 Pro Ultra",
        "brand": "로보락",
        "category": "로봇청소기",
        "release_date": "2024-03-15",
    }


@pytest.fixture
def sample_tco_data() -> dict:
    """Return sample TCO calculation data for testing."""
    return {
        "purchase_price_avg": 1_490_000,
        "purchase_price_min": 1_290_000,
        "resale_value_1yr": 1_010_000,
        "resale_value_2yr": 650_000,
        "resale_value_3yr_plus": 450_000,
        "expected_repair_cost": 180_000,
        "real_cost_3yr": 1_020_000,  # 1_490_000 + 180_000 - 650_000
        "as_turnaround_days": 7.5,
        "monthly_maintenance_minutes": 25,
    }
