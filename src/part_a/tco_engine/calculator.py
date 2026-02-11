"""TCO (Total Cost of Ownership) calculator.

JSON mode only. Reads A0/A2 JSON files directly. No DB needed.

Formula:
    Real Cost (Nyr) = purchase_price + (annual_consumable_cost × tco_years)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TCOCalculator:
    """Calculate TCO metrics for products.

    Usage (JSON mode):
        results = TCOCalculator.calculate_from_files(
            a0_path="data/processed/a0_selected_xxx.json",
            a2_path="data/processed/a2_consumable_xxx.json",
        )
    """

    @staticmethod
    def calculate_from_files(
        a0_path: str | Path,
        a2_path: str | Path,
        tco_years: int = 3,
    ) -> list[dict]:
        """Calculate TCO for all products using JSON files only.

        No database dependency. Reads A0 for product list + prices,
        A2 for consumable data.

        Args:
            a0_path: Path to A0 selected products JSON.
            a2_path: Path to A2 consumable data JSON.
            tco_years: TCO calculation period in years (default 3, pet=2).

        Returns:
            List of TCO result dicts, one per product.
        """
        a0_data = _load_json(a0_path, "A0")
        a2_data = _load_json(a2_path, "A2")

        # Index A2 by product_name for lookup
        a2_index = _index_by_product_name(a2_data.get("products", []))

        # Get product list from A0 — support both field names
        a0_products = (
            a0_data.get("selected_products")
            or a0_data.get("final_products")
            or a0_data.get("a0_summary", {}).get("top_3", [])
        )

        if not a0_products:
            logger.error("No products found in A0 data: %s", a0_path)
            return []

        logger.info("Loaded A0: %d products from %s", len(a0_products), a0_path)
        logger.info("Loaded A2: %d products from %s", len(a2_index), a2_path)

        results = []
        for product in a0_products:
            name = product.get("name", "")
            brand = product.get("brand", "")
            price = (
                product.get("purchase_price")
                or product.get("price")
                or product.get("lprice")
                or 0
            )

            if price <= 0:
                logger.warning("Skipping %s: purchase_price is 0", name)
                continue

            # Resolve A2 consumable data
            a2_product = _find_by_name(a2_index, name)
            consumable_data = _extract_consumables(a2_product) if a2_product else _empty_consumables()

            # === TCO Formula ===
            purchase_price = price
            annual_consumable_cost = consumable_data["annual_consumable_cost"]
            consumable_cost_total = annual_consumable_cost * tco_years

            real_cost_total = purchase_price + consumable_cost_total

            # Resolve product_id — prefer explicit, fallback to rank
            product_id = product.get("product_id") or str(product.get("rank", ""))
            # Resolve total_score — support multiple field paths
            total_score = (
                product.get("total_score")
                or product.get("a0_scores", product.get("scores", {})).get("total_score", 0)
                or 0
            )

            tco_result = {
                "product_id": product_id,
                "name": name,
                "brand": brand,
                "release_date": product.get("release_date"),
                "source_a0_rank": product.get("rank", 0),
                "a0_total_score": total_score,
                "tco": {
                    "purchase_price": purchase_price,
                    "annual_consumable_cost": annual_consumable_cost,
                    "tco_years": tco_years,
                    "consumable_cost_total": consumable_cost_total,
                    "real_cost_total": real_cost_total,
                    "consumable_breakdown": consumable_data.get("consumable_breakdown", []),
                },
                "notes": consumable_data.get("notes", ""),
            }

            results.append(tco_result)

            logger.info(
                "TCO for %s: purchase=%s, consumable_%dyr=%s -> real_cost=%s",
                name,
                f"{purchase_price:,}",
                tco_years,
                f"{consumable_cost_total:,}",
                f"{real_cost_total:,}",
            )

        return results


# ================================================================
# Helper functions for JSON mode
# ================================================================

def _load_json(path: str | Path, label: str) -> dict:
    """Load and return JSON data from file."""
    path = Path(path)
    if not path.exists():
        logger.error("%s file not found: %s", label, path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _index_by_product_name(products: list[dict]) -> dict[str, dict]:
    """Index a list of product dicts by product_name."""
    indexed = {}
    for p in products:
        name = p.get("product_name", "") or p.get("name", "")
        if name:
            indexed[name] = p
    return indexed


def _find_by_name(index: dict[str, dict], target_name: str) -> dict | None:
    """Find product by exact match or substring match."""
    if target_name in index:
        return index[target_name]
    for key, value in index.items():
        if key in target_name or target_name in key:
            return value
    return None


def _extract_consumables(a2_product: dict) -> dict:
    """Extract consumable data from A2 JSON product entry."""
    consumables = a2_product.get("consumables", [])
    breakdown = []
    total_annual = 0

    for item in consumables:
        annual_cost = item.get("annual_cost", 0)
        total_annual += annual_cost
        breakdown.append({
            "name": item.get("name", ""),
            "unit_price": item.get("unit_price", 0),
            "replacement_cycle_months": item.get("replacement_cycle_months", 12),
            "changes_per_year": item.get("changes_per_year", 1),
            "annual_cost": annual_cost,
            "compatible_available": item.get("compatible_available", False),
            "compatible_price": item.get("compatible_price"),
        })

    # Use pre-calculated total if provided, otherwise sum from items
    annual_consumable_cost = a2_product.get("annual_consumable_cost", total_annual)

    return {
        "annual_consumable_cost": annual_consumable_cost,
        "consumable_breakdown": breakdown,
        "notes": a2_product.get("notes", ""),
    }


def _empty_consumables() -> dict:
    """Return zero-cost consumable data when A2 data is missing."""
    return {
        "annual_consumable_cost": 0,
        "consumable_breakdown": [],
        "notes": "",
    }
