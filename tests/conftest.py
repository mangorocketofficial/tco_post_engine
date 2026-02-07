"""Shared test fixtures for TCO Post Engine."""

import os
import sys
from pathlib import Path

import pytest

# Ensure src is importable
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the test fixtures directory."""
    return PROJECT_ROOT / "tests" / "fixtures"


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
        "resale_value_24mo": 650_000,
        "expected_repair_cost": 180_000,
        "real_cost_3yr": 1_020_000,  # 1_490_000 + 180_000 - 650_000
        "as_turnaround_days": 7.5,
        "monthly_maintenance_minutes": 25,
    }
