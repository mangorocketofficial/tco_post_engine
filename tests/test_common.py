"""Tests for shared common modules — models, database, config."""

import sqlite3
import tempfile
from datetime import date, datetime
from pathlib import Path

import pytest

from src.common.models import (
    FailureTypeStat,
    MaintenanceTask,
    PriceRecord,
    PriceSource,
    Product,
    ProductTCOExport,
    RepairReport,
    RepairStats,
    ResaleCurve,
    ResaleTransaction,
    Sentiment,
    TCOCategoryExport,
    TCOSummary,
)
from src.common.database import get_connection, init_db


class TestProduct:
    def test_create_product(self, sample_product_data: dict):
        product = Product(**sample_product_data)
        assert product.product_id == "test-roborock-s8-pro"
        assert product.brand == "로보락"
        assert product.category == "로봇청소기"

    def test_product_date_parsing(self):
        product = Product(
            product_id="test",
            name="테스트",
            brand="테스트",
            category="테스트",
            release_date="2024-03-15",
        )
        assert product.release_date == date(2024, 3, 15)


class TestPriceRecord:
    def test_create_price_record(self):
        record = PriceRecord(
            product_id="test",
            date="2026-01-15",
            price=1_490_000,
            source=PriceSource.DANAWA,
            is_sale=False,
        )
        assert record.price == 1_490_000
        assert record.source == PriceSource.DANAWA

    def test_price_must_be_non_negative(self):
        with pytest.raises(Exception):
            PriceRecord(
                product_id="test",
                date="2026-01-15",
                price=-100,
                source=PriceSource.DANAWA,
            )


class TestTCOSummary:
    def test_create_tco_summary(self, sample_tco_data: dict):
        tco = TCOSummary(**sample_tco_data)
        assert tco.real_cost_3yr == 1_020_000
        assert tco.as_turnaround_days == 7.5

    def test_tco_formula(self, sample_tco_data: dict):
        tco = TCOSummary(**sample_tco_data)
        expected = tco.purchase_price_avg + tco.expected_repair_cost - tco.resale_value_2yr
        assert tco.real_cost_3yr == expected


class TestMaintenanceTask:
    def test_total_monthly_minutes(self):
        task = MaintenanceTask(
            product_id="test",
            task="먼지통 비우기",
            frequency_per_month=8,
            minutes_per_task=2,
        )
        assert task.total_monthly_minutes == 16.0


class TestTCOCategoryExport:
    def test_full_export_structure(self, sample_product_data: dict, sample_tco_data: dict):
        export = TCOCategoryExport(
            category="로봇청소기",
            generated_at=datetime.now(),
            products=[
                ProductTCOExport(
                    product_id=sample_product_data["product_id"],
                    name=sample_product_data["name"],
                    brand=sample_product_data["brand"],
                    release_date=sample_product_data["release_date"],
                    tco=TCOSummary(**sample_tco_data),
                )
            ],
        )
        assert export.category == "로봇청소기"
        assert len(export.products) == 1
        assert export.products[0].tco.real_cost_3yr == 1_020_000

    def test_export_serialization(self, sample_product_data: dict, sample_tco_data: dict):
        export = TCOCategoryExport(
            category="로봇청소기",
            generated_at=datetime(2026, 2, 7, 12, 0, 0),
            products=[
                ProductTCOExport(
                    product_id=sample_product_data["product_id"],
                    name=sample_product_data["name"],
                    brand=sample_product_data["brand"],
                    release_date=sample_product_data["release_date"],
                    tco=TCOSummary(**sample_tco_data),
                )
            ],
        )
        json_str = export.model_dump_json(indent=2)
        assert "로봇청소기" in json_str
        assert "1020000" in json_str


class TestDatabase:
    def test_init_db_creates_tables(self, tmp_path: Path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        conn = get_connection(db_path)
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row["name"] for row in cursor.fetchall()]
            assert "products" in tables
            assert "prices" in tables
            assert "resale_transactions" in tables
            assert "repair_reports" in tables
            assert "maintenance_tasks" in tables
            assert "tco_summaries" in tables
        finally:
            conn.close()

    def test_insert_and_query_product(self, tmp_path: Path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        conn = get_connection(db_path)
        try:
            conn.execute(
                "INSERT INTO products (product_id, name, brand, category, release_date) "
                "VALUES (?, ?, ?, ?, ?)",
                ("test-1", "로보락 S8", "로보락", "로봇청소기", "2024-03-15"),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM products WHERE product_id = ?", ("test-1",)
            ).fetchone()
            assert row["name"] == "로보락 S8"
            assert row["category"] == "로봇청소기"
        finally:
            conn.close()

    def test_insert_price_record(self, tmp_path: Path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        conn = get_connection(db_path)
        try:
            conn.execute(
                "INSERT INTO products (product_id, name, brand, category, release_date) "
                "VALUES (?, ?, ?, ?, ?)",
                ("test-1", "로보락 S8", "로보락", "로봇청소기", "2024-03-15"),
            )
            conn.execute(
                "INSERT INTO prices (product_id, date, price, source, is_sale) "
                "VALUES (?, ?, ?, ?, ?)",
                ("test-1", "2026-01-15", 1490000, "danawa", 0),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM prices WHERE product_id = ?", ("test-1",)
            ).fetchone()
            assert row["price"] == 1490000
            assert row["source"] == "danawa"
        finally:
            conn.close()
