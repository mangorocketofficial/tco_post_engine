"""TCO (Total Cost of Ownership) calculator.

Pulls price, resale, repair, and maintenance data from the database
and calculates the 3-year TCO for each product.

Supports hybrid pipeline: DB data (A1) + Claude WebSearch JSON overrides (A2/A3).

Formula: Real Cost (3yr) = Q1 (Purchase Price) + Q3 (Repair Cost) − Q2 (Resale Value)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date
from pathlib import Path
from statistics import mean, median

from ..common.config import Config
from ..database.connection import get_connection

logger = logging.getLogger(__name__)


class TCOCalculator:
    """Calculate TCO metrics for products from database data.

    Supports optional A2 (resale) and A3 (repair) JSON overrides from
    Claude WebSearch. When provided, these override the DB-sourced data.

    Usage:
        calc = TCOCalculator()
        tco = calc.calculate_for_product(product_id=1)
        print(f"3-year real cost: {tco['real_cost_3yr']:,}원")

        # With A2/A3 overrides:
        calc = TCOCalculator(a2_data_path="data/processed/a2_resale.json",
                             a3_data_path="data/processed/a3_repair.json")
    """

    def __init__(
        self,
        config: Config | None = None,
        a2_data_path: str | Path | None = None,
        a3_data_path: str | Path | None = None,
    ) -> None:
        self.config = config or Config()
        self._a2_overrides: dict[str, dict] = {}
        self._a3_overrides: dict[str, dict] = {}

        if a2_data_path:
            self._a2_overrides = self._load_override_json(a2_data_path, "A2 resale")
        if a3_data_path:
            self._a3_overrides = self._load_override_json(a3_data_path, "A3 repair")

    @staticmethod
    def _load_override_json(path: str | Path, label: str) -> dict[str, dict]:
        """Load A2/A3 JSON and index by product_name for fast lookup."""
        path = Path(path)
        if not path.exists():
            logger.warning("%s file not found: %s", label, path)
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        indexed = {}
        for product in data.get("products", []):
            name = product.get("product_name", "")
            if name:
                indexed[name] = product
        logger.info("Loaded %s override: %d products from %s", label, len(indexed), path)
        return indexed

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
            resale_data = self._resolve_resale_data(conn, product_id, product["name"])
            repair_data = self._resolve_repair_data(conn, product_id, product["name"])
            maintenance_data = self._get_maintenance_data(conn, product_id)

            # Q1: Purchase Price
            purchase_avg = price_data.get("avg_price", 0)
            purchase_min = price_data.get("min_price", 0)

            # Q2: Resale Values (1yr / 2yr / 3yr+)
            resale_1yr = resale_data.get("resale_value_1yr", 0)
            resale_2yr = resale_data.get("resale_value_2yr", 0)
            resale_3yr_plus = resale_data.get("resale_value_3yr_plus", 0)

            # Q3: Expected Repair Cost (probability-weighted)
            expected_repair = repair_data.get("expected_repair_cost", 0)

            # TCO Formula (uses 2yr resale — most common resale timeframe)
            real_cost_3yr = purchase_avg + expected_repair - resale_2yr

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
                    "resale_value_1yr": resale_1yr,
                    "resale_value_2yr": resale_2yr,
                    "resale_value_3yr_plus": resale_3yr_plus,
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
                "TCO for %s: purchase=%s, resale(2yr)=%s, repair=%s → real_cost=%s",
                product["name"],
                f"{purchase_avg:,}",
                f"{resale_2yr:,}",
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
                    resale_value_1yr INTEGER,
                    resale_value_2yr INTEGER,
                    resale_value_3yr_plus INTEGER,
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
                 resale_value_1yr, resale_value_2yr, resale_value_3yr_plus,
                 expected_repair_cost, real_cost_3yr,
                 as_turnaround_days, monthly_maintenance_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product_id,
                tco_data["purchase_price_avg"],
                tco_data["purchase_price_min"],
                tco_data["resale_value_1yr"],
                tco_data["resale_value_2yr"],
                tco_data["resale_value_3yr_plus"],
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

    def _resolve_resale_data(
        self, conn: sqlite3.Connection, product_id: int, product_name: str
    ) -> dict:
        """Get resale data from A2 override if available, else from DB."""
        a2 = self._find_override(self._a2_overrides, product_name)
        if a2:
            resale_prices = a2.get("resale_prices", {})
            resale_1yr = resale_prices.get("1yr", {}).get("price", 0)
            resale_2yr = resale_prices.get("2yr", {}).get("price", 0)
            resale_3yr_plus = resale_prices.get("3yr_plus", {}).get("price", 0)

            curve = a2.get("retention_curve", {})

            logger.info(
                "A2 override for %s: 1yr=%s, 2yr=%s, 3yr+=%s",
                product_name, f"{resale_1yr:,}", f"{resale_2yr:,}", f"{resale_3yr_plus:,}",
            )
            return {
                "resale_value_1yr": resale_1yr,
                "resale_value_2yr": resale_2yr,
                "resale_value_3yr_plus": resale_3yr_plus,
                "curve": {
                    "1yr": resale_1yr if resale_1yr else None,
                    "2yr": resale_2yr if resale_2yr else None,
                    "3yr_plus": resale_3yr_plus if resale_3yr_plus else None,
                },
            }
        return self._get_resale_data(conn, product_id)

    def _resolve_repair_data(
        self, conn: sqlite3.Connection, product_id: int, product_name: str
    ) -> dict:
        """Get repair data from A3 override if available, else from DB."""
        a3 = self._find_override(self._a3_overrides, product_name)
        if a3:
            failure_types = []
            for ft in a3.get("failure_types", []):
                failure_types.append({
                    "type": ft.get("type", ""),
                    "count": 1,
                    "avg_cost": ft.get("avg_cost", 0),
                    "probability": ft.get("probability", 0),
                })

            expected_repair = a3.get("expected_repair_cost", 0)
            avg_as_days = a3.get("avg_as_days", 0.0)

            logger.info(
                "A3 override for %s: repair=%s, AS=%.1f days",
                product_name, f"{expected_repair:,}", avg_as_days,
            )
            return {
                "expected_repair_cost": expected_repair,
                "avg_as_days": avg_as_days,
                "stats": {
                    "total_reports": len(failure_types),
                    "failure_types": failure_types,
                },
            }
        return self._get_repair_data(conn, product_id)

    @staticmethod
    def _find_override(overrides: dict[str, dict], product_name: str) -> dict | None:
        """Find override entry by exact match or substring match."""
        if not overrides:
            return None
        # Exact match
        if product_name in overrides:
            return overrides[product_name]
        # Substring match (product_name contains override key or vice versa)
        for key, value in overrides.items():
            if key in product_name or product_name in key:
                return value
        return None

    # Conditions excluded from resale calculation (broken/parts-only)
    EXCLUDED_CONDITIONS = {"worn"}

    @staticmethod
    def _get_resale_data(conn: sqlite3.Connection, product_id: int) -> dict:
        """Get resale statistics from the resale_transactions table.

        Groups by yearly buckets (1yr/2yr/3yr+), uses median prices,
        and excludes worn/broken items for representative pricing.
        """
        rows = conn.execute(
            """SELECT sale_price, months_since_release, condition, listing_date
               FROM resale_transactions WHERE product_id = ?""",
            (product_id,),
        ).fetchall()

        if not rows:
            return {
                "resale_value_1yr": 0,
                "resale_value_2yr": 0,
                "resale_value_3yr_plus": 0,
                "curve": {},
            }

        # Group by yearly buckets, excluding worn/broken items
        buckets: dict[str, list[int]] = {"1yr": [], "2yr": [], "3yr_plus": []}
        for row in rows:
            months = row["months_since_release"]
            if months is None:
                continue
            if row["condition"] in TCOCalculator.EXCLUDED_CONDITIONS:
                continue
            price = row["sale_price"]
            if months <= 18:
                buckets["1yr"].append(price)
            elif months <= 30:
                buckets["2yr"].append(price)
            else:
                buckets["3yr_plus"].append(price)

        def _median_or_zero(prices: list[int]) -> int:
            return int(median(prices)) if prices else 0

        resale_1yr = _median_or_zero(buckets["1yr"])
        resale_2yr = _median_or_zero(buckets["2yr"])
        resale_3yr_plus = _median_or_zero(buckets["3yr_plus"])

        # If no 2yr data, estimate from available data
        if resale_2yr == 0:
            usable = [row["sale_price"] for row in rows
                      if row["condition"] not in TCOCalculator.EXCLUDED_CONDITIONS]
            if usable:
                resale_2yr = int(median(usable) * 0.45)  # Conservative estimate

        curve = {}
        for key, prices in buckets.items():
            curve[key] = int(median(prices)) if prices else None

        return {
            "resale_value_1yr": resale_1yr,
            "resale_value_2yr": resale_2yr,
            "resale_value_3yr_plus": resale_3yr_plus,
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
