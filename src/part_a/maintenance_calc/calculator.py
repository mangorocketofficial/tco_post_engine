"""Maintenance time calculator.

Loads maintenance task templates from YAML config and calculates
per-product monthly time cost. Supports product-specific overrides
(e.g., auto-clean station reduces cleaning time to 0).

Config source: config/products_robot_vacuum.yaml
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from ..common.config import Config
from ..database.connection import get_connection
from .models import MaintenanceRecord, MaintenanceSummary

logger = logging.getLogger(__name__)

# Project root for resolving config paths
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class MaintenanceCalculator:
    """Calculate maintenance time cost from YAML config.

    Usage:
        calc = MaintenanceCalculator()
        summary = calc.calculate_for_product("로보락 S8 Pro Ultra")
        print(f"Monthly: {summary.total_monthly_minutes} min")
        print(f"3-year: {summary.total_3yr_hours} hours")
    """

    def __init__(
        self,
        config: Config | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self.config = config or Config()
        self._config_path = (
            Path(config_path) if config_path
            else _PROJECT_ROOT / "config" / "products_robot_vacuum.yaml"
        )
        self._product_config: dict | None = None

    def _load_config(self) -> dict:
        """Load and cache the product configuration YAML."""
        if self._product_config is None:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._product_config = yaml.safe_load(f)
        return self._product_config

    def get_default_tasks(self) -> list[dict]:
        """Get the default maintenance tasks from config."""
        config = self._load_config()
        return config.get("maintenance_tasks", [])

    def get_product_list(self) -> list[dict]:
        """Get the list of products from config."""
        config = self._load_config()
        return config.get("products", [])

    def calculate_for_product(
        self,
        product_name: str,
        overrides: dict[str, dict] | None = None,
    ) -> MaintenanceSummary:
        """Calculate maintenance summary for a product.

        Args:
            product_name: Name of the product.
            overrides: Optional per-task overrides.
                       Key = task name, Value = dict with any of:
                       - frequency_per_month: override frequency
                       - minutes_per_task: override time
                       - skip: True to exclude this task entirely

        Returns:
            MaintenanceSummary with all tasks and totals.
        """
        default_tasks = self.get_default_tasks()
        overrides = overrides or {}

        records: list[MaintenanceRecord] = []

        for task_def in default_tasks:
            task_name = task_def["task"]

            # Check for overrides
            override = overrides.get(task_name, {})
            if override.get("skip", False):
                logger.debug("Skipping task '%s' for %s", task_name, product_name)
                continue

            freq = override.get("frequency_per_month", task_def["frequency_per_month"])
            minutes = override.get("minutes_per_task", task_def["minutes_per_task"])

            records.append(MaintenanceRecord(
                product_name=product_name,
                task=task_name,
                frequency_per_month=freq,
                minutes_per_task=minutes,
            ))

        summary = MaintenanceSummary(product_name=product_name, tasks=records)

        logger.info(
            "Maintenance for %s: %.1f min/month, %.1f hours/3yr (%d tasks)",
            product_name,
            summary.total_monthly_minutes,
            summary.total_3yr_hours,
            len(records),
        )
        return summary

    def calculate_all_products(
        self,
        product_overrides: dict[str, dict[str, dict]] | None = None,
    ) -> list[MaintenanceSummary]:
        """Calculate maintenance for all configured products.

        Args:
            product_overrides: Nested dict of product_name → task_name → override.

        Returns:
            List of MaintenanceSummary for each product.
        """
        products = self.get_product_list()
        product_overrides = product_overrides or {}

        summaries: list[MaintenanceSummary] = []
        for product in products:
            name = product["name"]
            overrides = product_overrides.get(name, {})
            summary = self.calculate_for_product(name, overrides)
            summaries.append(summary)

        return summaries

    def save_to_db(self, summary: MaintenanceSummary) -> int:
        """Save maintenance tasks to database.

        Args:
            summary: MaintenanceSummary to persist.

        Returns:
            Number of records inserted.
        """
        conn = get_connection(self.config)
        inserted = 0
        try:
            product_id = self._ensure_product(conn, summary.product_name)

            # Remove existing tasks for this product (refresh)
            conn.execute(
                "DELETE FROM maintenance_tasks WHERE product_id = ?",
                (product_id,),
            )

            for task in summary.tasks:
                conn.execute(
                    """INSERT INTO maintenance_tasks
                       (product_id, task, frequency_per_month, minutes_per_task)
                       VALUES (?, ?, ?, ?)""",
                    (
                        product_id,
                        task.task,
                        task.frequency_per_month,
                        task.minutes_per_task,
                    ),
                )
                inserted += 1

            conn.commit()
            logger.info(
                "Saved %d maintenance tasks for %s",
                inserted, summary.product_name,
            )
        finally:
            conn.close()

        return inserted

    @staticmethod
    def _ensure_product(conn, product_name: str) -> int:
        """Get or create a product row, return its ID."""
        row = conn.execute(
            "SELECT id FROM products WHERE name = ?", (product_name,)
        ).fetchone()
        if row:
            return row["id"]
        cursor = conn.execute(
            "INSERT INTO products (name, brand, category) VALUES (?, ?, ?)",
            (product_name, "", ""),
        )
        return cursor.lastrowid
