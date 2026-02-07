"""TCO (Total Cost of Ownership) calculator.

Pulls price, resale, repair, and maintenance data from the database
and calculates the 3-year TCO for each product.

Formula: Real Cost (3yr) = Q1 (Purchase Price) + Q3 (Repair Cost) − Q2 (Resale Value)
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date
from statistics import mean

from ..common.config import Config
from ..database.connection import get_connection

logger = logging.getLogger(__name__)


class TCOCalculator:
    """Calculate TCO metrics for products from database data.

    Usage:
        calc = TCOCalculator()
        tco = calc.calculate_for_product(product_id=1)
        print(f"3-year real cost: {tco['real_cost_3yr']:,}원")
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()

    def calculate_for_product(self, product_id: int) -> dict:
        """Calculate all TCO metrics for a single product.

        Args:
            product_id: Database product ID.

        Returns:
            Dict with TCO metrics matching api-contract.json schema.
        """
        conn = get_connection(self.config)
        try:
            product = self._get_product(conn, product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")

            price_data = self._get_price_data(conn, product_id)
            resale_data = self._get_resale_data(conn, product_id)
            repair_data = self._get_repair_data(conn, product_id)
            maintenance_data = self._get_maintenance_data(conn, product_id)

            # Q1: Purchase Price
            purchase_avg = price_data.get("avg_price", 0)
            purchase_min = price_data.get("min_price", 0)

            # Q2: Resale Value at 24 months
            resale_24mo = resale_data.get("resale_value_24mo", 0)

            # Q3: Expected Repair Cost (probability-weighted)
            expected_repair = repair_data.get("expected_repair_cost", 0)

            # TCO Formula
            real_cost_3yr = purchase_avg + expected_repair - resale_24mo

            # S1: AS Turnaround Days
            as_days = repair_data.get("avg_as_days", 0.0)

            # S2: Monthly Maintenance Minutes
            maintenance_minutes = maintenance_data.get("total_monthly_minutes", 0.0)

            tco = {
                "product_id": product_id,
                "product_name": product["name"],
                "brand": product["brand"],
                "category": product["category"],
                "release_date": product.get("release_date"),
                "tco": {
                    "purchase_price_avg": purchase_avg,
                    "purchase_price_min": purchase_min,
                    "resale_value_24mo": resale_24mo,
                    "expected_repair_cost": expected_repair,
                    "real_cost_3yr": real_cost_3yr,
                    "as_turnaround_days": round(as_days, 1),
                    "monthly_maintenance_minutes": round(maintenance_minutes, 1),
                },
                "price_history": price_data.get("history", []),
                "resale_curve": resale_data.get("curve", {}),
                "repair_stats": repair_data.get("stats", {}),
                "maintenance_tasks": maintenance_data.get("tasks", []),
            }

            logger.info(
                "TCO for %s: purchase=%s, resale=%s, repair=%s → real_cost=%s",
                product["name"],
                f"{purchase_avg:,}",
                f"{resale_24mo:,}",
                f"{expected_repair:,}",
                f"{real_cost_3yr:,}",
            )
            return tco
        finally:
            conn.close()

    def calculate_all(self) -> list[dict]:
        """Calculate TCO for all products in the database.

        Returns:
            List of TCO dicts for each product.
        """
        conn = get_connection(self.config)
        try:
            rows = conn.execute("SELECT id FROM products ORDER BY id").fetchall()
            product_ids = [row["id"] for row in rows]
        finally:
            conn.close()

        results: list[dict] = []
        for pid in product_ids:
            try:
                tco = self.calculate_for_product(pid)
                results.append(tco)
            except Exception:
                logger.warning("Failed to calculate TCO for product %d", pid, exc_info=True)

        return results

    def save_tco_summary(self, product_id: int, tco: dict) -> None:
        """Save TCO summary to a tco_summaries table (if needed for caching)."""
        conn = get_connection(self.config)
        try:
            # Create tco_summaries table if it doesn't exist
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tco_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL UNIQUE,
                    purchase_price_avg INTEGER,
                    purchase_price_min INTEGER,
                    resale_value_24mo INTEGER,
                    expected_repair_cost INTEGER,
                    real_cost_3yr INTEGER,
                    as_turnaround_days REAL,
                    monthly_maintenance_minutes REAL,
                    calculated_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            """)

            tco_data = tco["tco"]
            conn.execute("""
                INSERT OR REPLACE INTO tco_summaries
                (product_id, purchase_price_avg, purchase_price_min,
                 resale_value_24mo, expected_repair_cost, real_cost_3yr,
                 as_turnaround_days, monthly_maintenance_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product_id,
                tco_data["purchase_price_avg"],
                tco_data["purchase_price_min"],
                tco_data["resale_value_24mo"],
                tco_data["expected_repair_cost"],
                tco_data["real_cost_3yr"],
                tco_data["as_turnaround_days"],
                tco_data["monthly_maintenance_minutes"],
            ))
            conn.commit()
            logger.info("Saved TCO summary for product %d", product_id)
        finally:
            conn.close()

    @staticmethod
    def _get_product(conn: sqlite3.Connection, product_id: int) -> dict | None:
        """Get product info."""
        row = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if not row:
            return None
        return dict(row)

    @staticmethod
    def _get_price_data(conn: sqlite3.Connection, product_id: int) -> dict:
        """Get price statistics from the prices table."""
        rows = conn.execute(
            "SELECT price, date, source, is_sale FROM prices WHERE product_id = ? ORDER BY date",
            (product_id,),
        ).fetchall()

        if not rows:
            return {"avg_price": 0, "min_price": 0, "history": []}

        prices = [row["price"] for row in rows]
        history = [
            {
                "date": row["date"],
                "price": row["price"],
                "source": row["source"],
                "is_sale": bool(row["is_sale"]),
            }
            for row in rows
        ]

        return {
            "avg_price": int(mean(prices)),
            "min_price": min(prices),
            "history": history,
        }

    @staticmethod
    def _get_resale_data(conn: sqlite3.Connection, product_id: int) -> dict:
        """Get resale statistics from the resale_transactions table."""
        rows = conn.execute(
            """SELECT sale_price, months_since_release, condition, listing_date
               FROM resale_transactions WHERE product_id = ?""",
            (product_id,),
        ).fetchall()

        if not rows:
            return {"resale_value_24mo": 0, "curve": {}}

        # Group by age buckets for retention curve
        buckets: dict[str, list[int]] = {"6mo": [], "12mo": [], "18mo": [], "24mo": []}
        for row in rows:
            months = row["months_since_release"]
            if months is None:
                continue
            price = row["sale_price"]
            if months <= 9:
                buckets["6mo"].append(price)
            elif months <= 15:
                buckets["12mo"].append(price)
            elif months <= 21:
                buckets["18mo"].append(price)
            elif months <= 30:
                buckets["24mo"].append(price)

        # Resale value at 24mo
        resale_24mo = int(mean(buckets["24mo"])) if buckets["24mo"] else 0

        # If no 24mo data, try to extrapolate from available data
        if resale_24mo == 0:
            all_prices = [row["sale_price"] for row in rows]
            if all_prices:
                resale_24mo = int(mean(all_prices) * 0.45)  # Conservative estimate

        curve = {}
        for key, prices in buckets.items():
            curve[key] = round(mean(prices), 0) if prices else None

        return {
            "resale_value_24mo": resale_24mo,
            "curve": curve,
        }

    @staticmethod
    def _get_repair_data(conn: sqlite3.Connection, product_id: int) -> dict:
        """Get repair statistics from the repair_reports table."""
        rows = conn.execute(
            """SELECT failure_type, repair_cost, as_days, sentiment
               FROM repair_reports WHERE product_id = ?""",
            (product_id,),
        ).fetchall()

        if not rows:
            return {"expected_repair_cost": 0, "avg_as_days": 0.0, "stats": {"total_reports": 0, "failure_types": []}}

        total = len(rows)

        # Group by failure type
        type_groups: dict[str, list[dict]] = {}
        for row in rows:
            ft = row["failure_type"]
            type_groups.setdefault(ft, []).append(dict(row))

        failure_types = []
        expected_cost = 0

        for ftype, group in type_groups.items():
            count = len(group)
            costs = [r["repair_cost"] for r in group if r["repair_cost"] > 0]
            avg_cost = int(mean(costs)) if costs else 0
            probability = count / total

            failure_types.append({
                "type": ftype,
                "count": count,
                "avg_cost": avg_cost,
                "probability": round(probability, 3),
            })
            expected_cost += int(avg_cost * probability)

        # Average AS days
        as_days_list = [row["as_days"] for row in rows if row["as_days"] is not None and row["as_days"] > 0]
        avg_as = mean(as_days_list) if as_days_list else 0.0

        return {
            "expected_repair_cost": expected_cost,
            "avg_as_days": avg_as,
            "stats": {
                "total_reports": total,
                "failure_types": failure_types,
            },
        }

    @staticmethod
    def _get_maintenance_data(conn: sqlite3.Connection, product_id: int) -> dict:
        """Get maintenance data from the maintenance_tasks table."""
        rows = conn.execute(
            """SELECT task, frequency_per_month, minutes_per_task
               FROM maintenance_tasks WHERE product_id = ?""",
            (product_id,),
        ).fetchall()

        if not rows:
            return {"total_monthly_minutes": 0.0, "tasks": []}

        tasks = []
        total_minutes = 0.0

        for row in rows:
            freq = row["frequency_per_month"]
            mins = row["minutes_per_task"]
            monthly = freq * mins
            total_minutes += monthly
            tasks.append({
                "task": row["task"],
                "frequency_per_month": freq,
                "minutes_per_task": mins,
            })

        return {
            "total_monthly_minutes": total_minutes,
            "tasks": tasks,
        }
