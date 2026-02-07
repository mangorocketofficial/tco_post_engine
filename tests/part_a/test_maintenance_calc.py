"""Tests for the maintenance calculator module."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.part_a.maintenance_calc.models import MaintenanceRecord, MaintenanceSummary
from src.part_a.maintenance_calc.calculator import MaintenanceCalculator


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def test_config_path(tmp_path) -> Path:
    """Create a test YAML config file."""
    config = {
        "category": "로봇청소기",
        "products": [
            {
                "product_id": "test-product-a",
                "name": "테스트 제품 A",
                "brand": "브랜드A",
                "release_date": "2024-01-01",
            },
            {
                "product_id": "test-product-b",
                "name": "테스트 제품 B",
                "brand": "브랜드B",
                "release_date": "2024-06-01",
            },
        ],
        "maintenance_tasks": [
            {"task": "먼지통 비우기", "frequency_per_month": 8, "minutes_per_task": 2},
            {"task": "필터 세척", "frequency_per_month": 2, "minutes_per_task": 5},
            {"task": "브러시 청소", "frequency_per_month": 4, "minutes_per_task": 5},
        ],
    }
    path = tmp_path / "test_products.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    return path


class TestMaintenanceRecord:
    """Test MaintenanceRecord model."""

    def test_create_record(self):
        record = MaintenanceRecord(
            product_name="테스트",
            task="먼지통 비우기",
            frequency_per_month=8,
            minutes_per_task=2,
        )
        assert record.task == "먼지통 비우기"
        assert record.frequency_per_month == 8
        assert record.minutes_per_task == 2

    def test_total_monthly_minutes(self):
        record = MaintenanceRecord("테스트", "필터 세척", 2, 5)
        assert record.total_monthly_minutes == 10.0

    def test_to_dict(self):
        record = MaintenanceRecord("테스트", "브러시 청소", 4, 5)
        d = record.to_dict()
        assert d["task"] == "브러시 청소"
        assert d["total_monthly_minutes"] == 20.0


class TestMaintenanceSummary:
    """Test MaintenanceSummary model."""

    def test_empty_summary(self):
        summary = MaintenanceSummary(product_name="테스트")
        assert summary.total_monthly_minutes == 0
        assert summary.total_3yr_hours == 0

    def test_summary_calculation(self):
        tasks = [
            MaintenanceRecord("테스트", "먼지통 비우기", 8, 2),    # 16 min
            MaintenanceRecord("테스트", "필터 세척", 2, 5),        # 10 min
            MaintenanceRecord("테스트", "브러시 청소", 4, 5),      # 20 min
        ]
        summary = MaintenanceSummary(product_name="테스트", tasks=tasks)

        assert summary.total_monthly_minutes == 46.0
        # 3yr = 46 * 36 / 60 = 27.6 hours
        assert summary.total_3yr_hours == pytest.approx(27.6, abs=0.1)

    def test_to_dict(self):
        tasks = [
            MaintenanceRecord("테스트", "먼지통 비우기", 8, 2),
        ]
        summary = MaintenanceSummary(product_name="테스트", tasks=tasks)
        d = summary.to_dict()
        assert d["product_name"] == "테스트"
        assert d["total_monthly_minutes"] == 16.0
        assert len(d["tasks"]) == 1


class TestMaintenanceCalculator:
    """Test MaintenanceCalculator with YAML config."""

    def test_load_config(self, test_config_path):
        calc = MaintenanceCalculator(config_path=test_config_path)
        tasks = calc.get_default_tasks()
        assert len(tasks) == 3
        assert tasks[0]["task"] == "먼지통 비우기"

    def test_get_product_list(self, test_config_path):
        calc = MaintenanceCalculator(config_path=test_config_path)
        products = calc.get_product_list()
        assert len(products) == 2
        assert products[0]["name"] == "테스트 제품 A"

    def test_calculate_default(self, test_config_path):
        calc = MaintenanceCalculator(config_path=test_config_path)
        summary = calc.calculate_for_product("테스트 제품 A")

        assert summary.product_name == "테스트 제품 A"
        assert len(summary.tasks) == 3
        # 8*2 + 2*5 + 4*5 = 16 + 10 + 20 = 46 min/month
        assert summary.total_monthly_minutes == 46.0

    def test_calculate_with_overrides(self, test_config_path):
        """Test task overrides (e.g., auto-clean station reduces time)."""
        calc = MaintenanceCalculator(config_path=test_config_path)
        overrides = {
            "먼지통 비우기": {"frequency_per_month": 0, "minutes_per_task": 0},  # Auto-clean
            "필터 세척": {"minutes_per_task": 3},  # Easier filter
        }
        summary = calc.calculate_for_product("테스트 제품 A", overrides)

        assert len(summary.tasks) == 3
        # 0*0 + 2*3 + 4*5 = 0 + 6 + 20 = 26 min/month
        assert summary.total_monthly_minutes == 26.0

    def test_calculate_with_skip(self, test_config_path):
        """Test skipping a task entirely."""
        calc = MaintenanceCalculator(config_path=test_config_path)
        overrides = {
            "브러시 청소": {"skip": True},
        }
        summary = calc.calculate_for_product("테스트 제품 A", overrides)

        assert len(summary.tasks) == 2  # One task skipped
        task_names = [t.task for t in summary.tasks]
        assert "브러시 청소" not in task_names

    def test_calculate_all_products(self, test_config_path):
        calc = MaintenanceCalculator(config_path=test_config_path)
        summaries = calc.calculate_all_products()

        assert len(summaries) == 2
        assert summaries[0].product_name == "테스트 제품 A"
        assert summaries[1].product_name == "테스트 제품 B"
        # Both have same default tasks
        assert summaries[0].total_monthly_minutes == summaries[1].total_monthly_minutes

    def test_calculate_all_with_per_product_overrides(self, test_config_path):
        calc = MaintenanceCalculator(config_path=test_config_path)
        overrides = {
            "테스트 제품 A": {
                "먼지통 비우기": {"frequency_per_month": 0, "minutes_per_task": 0},
            },
        }
        summaries = calc.calculate_all_products(overrides)

        # Product A has overrides, Product B uses defaults
        assert summaries[0].total_monthly_minutes < summaries[1].total_monthly_minutes

    def test_uses_real_config(self):
        """Test loading the actual project config file."""
        calc = MaintenanceCalculator()
        tasks = calc.get_default_tasks()
        assert len(tasks) >= 3  # At least 3 maintenance tasks defined
        assert any(t["task"] == "먼지통 비우기" for t in tasks)


class TestSaveToDb:
    """Test database persistence."""

    def test_save_maintenance_tasks(self, temp_db, test_config_path):
        calc = MaintenanceCalculator(config=temp_db, config_path=test_config_path)
        summary = calc.calculate_for_product("테스트 제품 A")

        inserted = calc.save_to_db(summary)
        assert inserted == 3

        from src.part_a.database.connection import get_connection

        conn = get_connection(temp_db)
        try:
            rows = conn.execute(
                "SELECT COUNT(*) as cnt FROM maintenance_tasks"
            ).fetchone()
            assert rows["cnt"] == 3

            row = conn.execute(
                "SELECT * FROM maintenance_tasks ORDER BY id LIMIT 1"
            ).fetchone()
            assert row["task"] == "먼지통 비우기"
            assert row["frequency_per_month"] == 8
        finally:
            conn.close()

    def test_save_overwrites_existing(self, temp_db, test_config_path):
        """Test that saving again replaces existing tasks."""
        calc = MaintenanceCalculator(config=temp_db, config_path=test_config_path)
        summary = calc.calculate_for_product("테스트 제품 A")

        calc.save_to_db(summary)
        calc.save_to_db(summary)  # Save again

        from src.part_a.database.connection import get_connection

        conn = get_connection(temp_db)
        try:
            rows = conn.execute(
                "SELECT COUNT(*) as cnt FROM maintenance_tasks"
            ).fetchone()
            assert rows["cnt"] == 3  # Not 6 — replaced
        finally:
            conn.close()
