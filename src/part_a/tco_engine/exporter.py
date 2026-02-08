"""TCO data exporter — generates JSON matching api-contract.json schema.

Output is consumed by Part B (Content Engine) for blog generation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from ..common.config import Config
from .calculator import TCOCalculator

logger = logging.getLogger(__name__)

# Project root for default export path
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class TCOExporter:
    """Export TCO data to JSON files matching the Part A → Part B contract.

    Usage:
        exporter = TCOExporter()
        exporter.export_category("로봇청소기")
    """

    def __init__(
        self,
        config: Config | None = None,
        a2_data_path: str | Path | None = None,
        a3_data_path: str | Path | None = None,
    ) -> None:
        self.config = config or Config()
        self._calculator = TCOCalculator(
            self.config, a2_data_path=a2_data_path, a3_data_path=a3_data_path
        )
        self._export_dir = _PROJECT_ROOT / "data" / "exports"

    def export_category(
        self,
        category: str,
        output_path: str | Path | None = None,
    ) -> dict:
        """Export TCO data for all products in a category.

        Args:
            category: Product category (e.g., "로봇청소기").
            output_path: Optional output file path. Defaults to
                         data/exports/tco_{category}_{date}.json

        Returns:
            The complete export dict matching TCOCategoryExport schema.
        """
        # Calculate TCO for all products
        all_tcos = self._calculator.calculate_all()

        # Build export matching api-contract.json schema
        export = {
            "category": category,
            "generated_at": datetime.now().isoformat(),
            "products": [],
        }

        for tco in all_tcos:
            # Filter by category if product has category set
            prod_category = tco.get("category", "")
            if prod_category and prod_category != category:
                continue

            product_export = {
                "product_id": str(tco.get("product_id", "")),
                "name": tco.get("product_name", ""),
                "brand": tco.get("brand", ""),
                "release_date": tco.get("release_date", ""),
                "tco": tco["tco"],
                "price_history": tco.get("price_history", []),
                "resale_curve": tco.get("resale_curve", {}),
                "repair_stats": tco.get("repair_stats", {}),
                "maintenance_tasks": tco.get("maintenance_tasks", []),
            }
            export["products"].append(product_export)

            # Save TCO summary to DB for caching
            try:
                self._calculator.save_tco_summary(
                    int(tco["product_id"]), tco
                )
            except (ValueError, TypeError):
                pass

        # Write to file
        if output_path is None:
            self._export_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime("%Y%m%d")
            safe_category = category.replace(" ", "_")
            output_path = self._export_dir / f"tco_{safe_category}_{date_str}.json"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2, default=str)

        logger.info(
            "Exported TCO data for %s (%d products) → %s",
            category, len(export["products"]), output_path,
        )
        return export

    def export_single_product(
        self,
        product_id: int,
        output_path: str | Path | None = None,
    ) -> dict:
        """Export TCO data for a single product.

        Args:
            product_id: Database product ID.
            output_path: Optional output file path.

        Returns:
            Single product TCO dict.
        """
        tco = self._calculator.calculate_for_product(product_id)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(tco, f, ensure_ascii=False, indent=2, default=str)
            logger.info("Exported TCO for product %d → %s", product_id, output_path)

        return tco
