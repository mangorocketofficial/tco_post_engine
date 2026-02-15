#!/usr/bin/env python3
"""Insert A0 products into database for TCO calculation."""

import json
from pathlib import Path
from src.part_a.database.connection import get_connection
from src.part_a.common.config import Config

def insert_a0_products(a0_json_path: str, category: str) -> int:
    """Insert A0 products into the database."""
    config = Config()
    conn = get_connection(config)

    try:
        with open(a0_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        inserted = 0
        products = data.get("final_products", data.get("selected_products", []))

        for product in products:
            name = product.get("name", "")
            brand = product.get("brand", "")

            if not name or not brand:
                continue

            # Insert product (will be ignored if already exists due to unique index)
            try:
                conn.execute("""
                    INSERT INTO products (name, brand, category)
                    VALUES (?, ?, ?)
                """, (name, brand, category))
                inserted += 1
                print(f"[+] Inserted: {name}")
            except Exception as e:
                print(f"[!] Skipped {name}: {e}")

        conn.commit()
        print(f"\n[OK] Inserted {inserted} products into database")
        return inserted

    finally:
        conn.close()

if __name__ == "__main__":
    insert_a0_products(
        a0_json_path="data/processed/a0_selected_air_fryer.json",
        category="에어프라이어"
    )
