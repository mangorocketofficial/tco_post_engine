"""Tests for the database layer."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from src.part_a.database.connection import init_db, get_connection
from src.part_a.database.models import Product, Price


class TestDatabaseInit:
    """Test database schema initialization."""

    def test_init_creates_tables(self, temp_db):
        conn = get_connection(temp_db)
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row["name"] for row in cursor.fetchall()]
            assert "products" in tables
            assert "prices" in tables
            assert "product_selections" in tables
        finally:
            conn.close()

    def test_init_is_idempotent(self, temp_db):
        # Calling init_db again should not raise
        init_db(temp_db)
        init_db(temp_db)

    def test_foreign_keys_enabled(self, db_conn):
        row = db_conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1

    def test_wal_mode(self, db_conn):
        row = db_conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"


class TestProductCRUD:
    """Test product table operations."""

    def test_insert_product(self, db_conn):
        db_conn.execute(
            "INSERT INTO products (name, brand, category) VALUES (?, ?, ?)",
            ("로보락 Q Revo S", "로보락", "로봇청소기"),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT * FROM products WHERE name = ?", ("로보락 Q Revo S",)).fetchone()
        assert row is not None
        assert row["brand"] == "로보락"
        assert row["category"] == "로봇청소기"

    def test_unique_name_brand(self, db_conn):
        db_conn.execute(
            "INSERT INTO products (name, brand, category) VALUES (?, ?, ?)",
            ("테스트 제품", "브랜드A", "카테고리"),
        )
        db_conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO products (name, brand, category) VALUES (?, ?, ?)",
                ("테스트 제품", "브랜드A", "카테고리"),
            )

    def test_same_product_different_category(self, db_conn):
        """Products with same name+brand but different category should not collide."""
        db_conn.execute(
            "INSERT INTO products (name, brand, category) VALUES (?, ?, ?)",
            ("테스트제품", "테스트브랜드", "로봇청소기"),
        )
        db_conn.execute(
            "INSERT INTO products (name, brand, category) VALUES (?, ?, ?)",
            ("테스트제품", "테스트브랜드", "펫 급수기"),
        )
        db_conn.commit()
        rows = db_conn.execute("SELECT * FROM products WHERE name='테스트제품'").fetchall()
        assert len(rows) == 2


class TestPriceCRUD:
    """Test price table operations."""

    def test_insert_price(self, db_conn):
        db_conn.execute(
            "INSERT INTO products (name, brand, category) VALUES (?, ?, ?)",
            ("테스트 제품", "브랜드", "카테고리"),
        )
        product_id = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        db_conn.execute(
            "INSERT INTO prices (product_id, date, price, source, is_sale) VALUES (?, ?, ?, ?, ?)",
            (product_id, "2026-02-07", 1490000, "danawa", 0),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT * FROM prices WHERE product_id = ?", (product_id,)
        ).fetchone()
        assert row["price"] == 1490000
        assert row["source"] == "danawa"

    def test_unique_price_per_product_date_source(self, db_conn):
        db_conn.execute(
            "INSERT INTO products (name, brand, category) VALUES (?, ?, ?)",
            ("제품A", "브랜드A", "카테고리A"),
        )
        product_id = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        db_conn.execute(
            "INSERT INTO prices (product_id, date, price, source) VALUES (?, ?, ?, ?)",
            (product_id, "2026-02-07", 100000, "danawa"),
        )
        db_conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO prices (product_id, date, price, source) VALUES (?, ?, ?, ?)",
                (product_id, "2026-02-07", 110000, "danawa"),
            )


class TestModels:
    """Test data model serialization."""

    def test_product_to_dict(self):
        p = Product(name="Test", brand="Brand", category="Cat", id=1)
        d = p.to_dict()
        assert d["name"] == "Test"
        assert d["id"] == 1

    def test_price_to_dict(self):
        p = Price(product_id=1, date=date(2026, 2, 7), price=1000000, source="danawa")
        d = p.to_dict()
        assert d["date"] == "2026-02-07"
        assert d["price"] == 1000000


