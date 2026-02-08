"""Tests for the TCO engine module."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.part_a.database.connection import get_connection
from src.part_a.tco_engine.calculator import TCOCalculator
from src.part_a.tco_engine.exporter import TCOExporter


@pytest.fixture
def populated_db(temp_db):
    """Create a temp database populated with test data for TCO calculation."""
    conn = get_connection(temp_db)
    try:
        # Insert products
        conn.execute(
            "INSERT INTO products (name, brand, category, release_date) VALUES (?, ?, ?, ?)",
            ("로보락 S8 Pro Ultra", "로보락", "로봇청소기", "2024-03-15"),
        )
        conn.execute(
            "INSERT INTO products (name, brand, category, release_date) VALUES (?, ?, ?, ?)",
            ("삼성 비스포크 제트봇 AI", "삼성", "로봇청소기", "2024-01-10"),
        )

        # Insert prices for product 1 (로보락)
        for day, price, is_sale in [
            ("2026-01-01", 1490000, 0),
            ("2026-01-15", 1450000, 0),
            ("2026-02-01", 1390000, 1),
            ("2026-02-07", 1490000, 0),
        ]:
            conn.execute(
                "INSERT INTO prices (product_id, date, price, source, is_sale) VALUES (?, ?, ?, ?, ?)",
                (1, day, price, "danawa", is_sale),
            )

        # Insert prices for product 2 (삼성)
        for day, price in [
            ("2026-01-01", 1290000),
            ("2026-02-01", 1250000),
        ]:
            conn.execute(
                "INSERT INTO prices (product_id, date, price, source, is_sale) VALUES (?, ?, ?, ?, ?)",
                (2, day, price, "danawa", 0),
            )

        # Insert resale transactions for product 1
        for price, months, condition in [
            (1200000, 6.0, "like_new"),
            (1100000, 8.0, "used"),
            (900000, 12.0, "used"),
            (750000, 18.0, "used"),
            (650000, 24.0, "used"),
            (600000, 25.0, "worn"),
        ]:
            conn.execute(
                """INSERT INTO resale_transactions
                   (product_id, platform, sale_price, months_since_release, condition)
                   VALUES (?, ?, ?, ?, ?)""",
                (1, "danggeun", price, months, condition),
            )

        # Insert repair reports for product 1
        for ftype, cost, days, sentiment in [
            ("sensor", 150000, 7, "positive"),
            ("sensor", 180000, 5, "neutral"),
            ("motor", 300000, 14, "negative"),
            ("battery", 120000, 3, "neutral"),
        ]:
            conn.execute(
                """INSERT INTO repair_reports
                   (product_id, failure_type, repair_cost, as_days, sentiment, date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (1, ftype, cost, days, sentiment, "2026-01-15"),
            )

        # Insert maintenance tasks for product 1
        for task, freq, mins in [
            ("먼지통 비우기", 8, 2),
            ("필터 세척", 2, 5),
            ("브러시 청소", 4, 5),
        ]:
            conn.execute(
                """INSERT INTO maintenance_tasks
                   (product_id, task, frequency_per_month, minutes_per_task)
                   VALUES (?, ?, ?, ?)""",
                (1, task, freq, mins),
            )

        conn.commit()
    finally:
        conn.close()

    return temp_db


class TestTCOCalculator:
    """Test TCO calculation logic."""

    def test_calculate_single_product(self, populated_db):
        calc = TCOCalculator(populated_db)
        tco = calc.calculate_for_product(1)

        assert tco["product_name"] == "로보락 S8 Pro Ultra"
        assert tco["brand"] == "로보락"

        tco_data = tco["tco"]

        # Q1: Purchase Price — avg of 1490000, 1450000, 1390000, 1490000 = 1455000
        assert tco_data["purchase_price_avg"] == 1455000
        assert tco_data["purchase_price_min"] == 1390000

        # Q2: Resale Values (yearly buckets, median, worn excluded)
        # 1yr (≤18mo): [1200000, 1100000, 900000, 750000] → median = 1000000
        assert tco_data["resale_value_1yr"] == 1000000
        # 2yr (18-30mo): [650000] → median = 650000 (worn 600000 excluded)
        assert tco_data["resale_value_2yr"] == 650000
        # 3yr+ (>30mo): [] → 0
        assert tco_data["resale_value_3yr_plus"] == 0

        # Q3: Expected Repair Cost
        # sensor: avg=165000, prob=0.5 → 82500
        # motor: avg=300000, prob=0.25 → 75000
        # battery: avg=120000, prob=0.25 → 30000
        # total = 187500
        assert tco_data["expected_repair_cost"] == 187500

        # Real Cost = 1455000 + 187500 - 650000 = 992500
        assert tco_data["real_cost_3yr"] == 992500

        # S1: AS Days — avg of (7, 5, 14, 3) = 7.25
        assert tco_data["as_turnaround_days"] == 7.2  # rounded to 1 decimal

        # S2: Maintenance — 8*2 + 2*5 + 4*5 = 46.0
        assert tco_data["monthly_maintenance_minutes"] == 46.0

    def test_calculate_product_minimal_data(self, populated_db):
        """Product 2 has prices but no resale/repair/maintenance data."""
        calc = TCOCalculator(populated_db)
        tco = calc.calculate_for_product(2)

        tco_data = tco["tco"]
        assert tco_data["purchase_price_avg"] == 1270000  # avg(1290000, 1250000)
        assert tco_data["resale_value_1yr"] == 0  # No resale data available
        assert tco_data["resale_value_2yr"] == 0
        assert tco_data["resale_value_3yr_plus"] == 0
        assert tco_data["expected_repair_cost"] == 0
        assert tco_data["monthly_maintenance_minutes"] == 0.0
        # Real cost = purchase + 0 - 0
        assert tco_data["real_cost_3yr"] == 1270000

    def test_calculate_nonexistent_product(self, populated_db):
        calc = TCOCalculator(populated_db)
        with pytest.raises(ValueError):
            calc.calculate_for_product(999)

    def test_calculate_all(self, populated_db):
        calc = TCOCalculator(populated_db)
        results = calc.calculate_all()

        assert len(results) == 2
        assert results[0]["product_name"] == "로보락 S8 Pro Ultra"
        assert results[1]["product_name"] == "삼성 비스포크 제트봇 AI"

    def test_price_history_included(self, populated_db):
        calc = TCOCalculator(populated_db)
        tco = calc.calculate_for_product(1)

        assert len(tco["price_history"]) == 4
        assert tco["price_history"][0]["date"] == "2026-01-01"
        assert tco["price_history"][0]["price"] == 1490000

    def test_resale_curve_included(self, populated_db):
        calc = TCOCalculator(populated_db)
        tco = calc.calculate_for_product(1)

        curve = tco["resale_curve"]
        assert "1yr" in curve
        assert "2yr" in curve

    def test_repair_stats_included(self, populated_db):
        calc = TCOCalculator(populated_db)
        tco = calc.calculate_for_product(1)

        stats = tco["repair_stats"]
        assert stats["total_reports"] == 4
        assert len(stats["failure_types"]) == 3

    def test_maintenance_tasks_included(self, populated_db):
        calc = TCOCalculator(populated_db)
        tco = calc.calculate_for_product(1)

        tasks = tco["maintenance_tasks"]
        assert len(tasks) == 3
        assert tasks[0]["task"] == "먼지통 비우기"

    def test_save_tco_summary(self, populated_db):
        calc = TCOCalculator(populated_db)
        tco = calc.calculate_for_product(1)
        calc.save_tco_summary(1, tco)

        conn = get_connection(populated_db)
        try:
            row = conn.execute(
                "SELECT * FROM tco_summaries WHERE product_id = 1"
            ).fetchone()
            assert row is not None
            assert row["purchase_price_avg"] == 1455000
            assert row["real_cost_3yr"] == 992500
        finally:
            conn.close()


class TestTCOExporter:
    """Test JSON export matching api-contract.json schema."""

    def test_export_category(self, populated_db, tmp_path):
        exporter = TCOExporter(populated_db)
        output_path = tmp_path / "tco_export.json"

        export = exporter.export_category("로봇청소기", output_path)

        # Verify structure matches api-contract.json
        assert "category" in export
        assert "generated_at" in export
        assert "products" in export
        assert export["category"] == "로봇청소기"
        assert len(export["products"]) == 2

        # Verify product structure
        product = export["products"][0]
        assert "product_id" in product
        assert "name" in product
        assert "brand" in product
        assert "release_date" in product
        assert "tco" in product
        assert "price_history" in product
        assert "resale_curve" in product
        assert "repair_stats" in product
        assert "maintenance_tasks" in product

        # Verify TCO fields
        tco = product["tco"]
        assert "purchase_price_avg" in tco
        assert "purchase_price_min" in tco
        assert "resale_value_1yr" in tco
        assert "resale_value_2yr" in tco
        assert "resale_value_3yr_plus" in tco
        assert "expected_repair_cost" in tco
        assert "real_cost_3yr" in tco
        assert "as_turnaround_days" in tco
        assert "monthly_maintenance_minutes" in tco

        # Verify file was written
        assert output_path.exists()
        with open(output_path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data["category"] == "로봇청소기"
        assert len(saved_data["products"]) == 2

    def test_export_single_product(self, populated_db, tmp_path):
        exporter = TCOExporter(populated_db)
        output_path = tmp_path / "product_tco.json"

        tco = exporter.export_single_product(1, output_path)

        assert tco["product_name"] == "로보락 S8 Pro Ultra"
        assert output_path.exists()

    def test_export_default_path(self, populated_db):
        """Test that export creates file at default path."""
        exporter = TCOExporter(populated_db)
        export = exporter.export_category("로봇청소기")

        assert len(export["products"]) == 2

    def test_export_category_filter(self, populated_db):
        """Test filtering by category."""
        # Add a product with a different category
        conn = get_connection(populated_db)
        try:
            conn.execute(
                "INSERT INTO products (name, brand, category) VALUES (?, ?, ?)",
                ("에어컨 테스트", "LG", "에어컨"),
            )
            conn.commit()
        finally:
            conn.close()

        exporter = TCOExporter(populated_db)
        export = exporter.export_category("로봇청소기")

        # Should only include 로봇청소기 products
        names = [p["name"] for p in export["products"]]
        assert "에어컨 테스트" not in names


class TestTCOFormula:
    """Test the core TCO formula independently."""

    def test_formula_basic(self):
        """Real Cost (3yr) = Q1 + Q3 - Q2"""
        q1 = 1_490_000  # Purchase price
        q2 = 650_000    # Resale value
        q3 = 180_000    # Expected repair cost

        real_cost = q1 + q3 - q2
        assert real_cost == 1_020_000

    def test_formula_no_repairs(self):
        q1 = 1_000_000
        q2 = 500_000
        q3 = 0

        real_cost = q1 + q3 - q2
        assert real_cost == 500_000

    def test_formula_high_retention(self):
        """Product that retains value well has lower TCO."""
        q1 = 1_500_000
        q2 = 1_200_000  # High retention
        q3 = 100_000

        real_cost = q1 + q3 - q2
        assert real_cost == 400_000

    def test_formula_low_retention(self):
        """Product that loses value quickly has higher TCO."""
        q1 = 1_500_000
        q2 = 300_000  # Low retention
        q3 = 200_000

        real_cost = q1 + q3 - q2
        assert real_cost == 1_400_000


class TestEndToEnd:
    """End-to-end test: populate data → calculate TCO → export JSON."""

    def test_full_pipeline(self, temp_db, tmp_path):
        """Simulate the full Part A pipeline."""
        conn = get_connection(temp_db)
        try:
            # Step 1: Add product
            conn.execute(
                "INSERT INTO products (name, brand, category, release_date) VALUES (?, ?, ?, ?)",
                ("테스트 로봇청소기", "테스트브랜드", "로봇청소기", "2024-01-01"),
            )

            # Step 2: Add prices (price-tracker output)
            conn.execute(
                "INSERT INTO prices (product_id, date, price, source, is_sale) VALUES (?, ?, ?, ?, ?)",
                (1, "2026-01-01", 1000000, "danawa", 0),
            )
            conn.execute(
                "INSERT INTO prices (product_id, date, price, source, is_sale) VALUES (?, ?, ?, ?, ?)",
                (1, "2026-02-01", 950000, "danawa", 1),
            )

            # Step 3: Add resale data (resale-tracker output)
            conn.execute(
                """INSERT INTO resale_transactions
                   (product_id, platform, sale_price, months_since_release, condition)
                   VALUES (?, ?, ?, ?, ?)""",
                (1, "danggeun", 500000, 24.0, "used"),
            )

            # Step 4: Add repair data (repair-analyzer output)
            conn.execute(
                """INSERT INTO repair_reports
                   (product_id, failure_type, repair_cost, as_days, sentiment, date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (1, "sensor", 100000, 5, "neutral", "2026-01-15"),
            )

            # Step 5: Add maintenance data (maintenance-calc output)
            conn.execute(
                """INSERT INTO maintenance_tasks
                   (product_id, task, frequency_per_month, minutes_per_task)
                   VALUES (?, ?, ?, ?)""",
                (1, "먼지통 비우기", 8, 2),
            )

            conn.commit()
        finally:
            conn.close()

        # Step 6: Calculate TCO
        calc = TCOCalculator(temp_db)
        tco = calc.calculate_for_product(1)

        assert tco["tco"]["purchase_price_avg"] == 975000  # avg(1000000, 950000)
        assert tco["tco"]["resale_value_1yr"] == 0
        assert tco["tco"]["resale_value_2yr"] == 500000
        assert tco["tco"]["resale_value_3yr_plus"] == 0
        assert tco["tco"]["expected_repair_cost"] == 100000
        assert tco["tco"]["real_cost_3yr"] == 575000  # 975000 + 100000 - 500000
        assert tco["tco"]["as_turnaround_days"] == 5.0
        assert tco["tco"]["monthly_maintenance_minutes"] == 16.0

        # Step 7: Export JSON
        exporter = TCOExporter(temp_db)
        output_path = tmp_path / "pipeline_output.json"
        export = exporter.export_category("로봇청소기", output_path)

        assert len(export["products"]) == 1
        assert export["products"][0]["tco"]["real_cost_3yr"] == 575000

        # Verify JSON file is valid
        with open(output_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["category"] == "로봇청소기"
