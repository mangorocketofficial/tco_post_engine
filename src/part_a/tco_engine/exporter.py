"""TCO data exporter — generates JSON for Part B consumption.

Pure JSON mode. Merges A0 + A2 + A5 data without DB dependency.

Output schema includes:
- Tier metadata from A0
- TCO calculations from calculator (consumable-based)
- Review insights from A5
- Credibility metadata
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from .calculator import TCOCalculator

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class TCOExporter:
    """Export TCO data to JSON files for Part B."""

    @staticmethod
    def export_from_files(
        category: str,
        a0_path: str | Path,
        a2_path: str | Path,
        a5_path: str | Path | None = None,
        output_path: str | Path | None = None,
        tco_years: int = 3,
        domain: str = "tech",
    ) -> dict:
        """Export TCO data by merging A0+A2+A5 JSON files.

        This is the primary export method for the pipeline.
        No database dependency.

        Args:
            category: Product category name.
            a0_path: A0 selected products JSON.
            a2_path: A2 consumable data JSON.
            a5_path: A5 review insights JSON (optional).
            output_path: Output file path.
            tco_years: TCO calculation period in years (default 3, pet=2, baby=1~3).
            domain: Blog domain — "tech", "pet", or "baby".

        Returns:
            Complete export dict for Part B consumption.
        """
        # Step 1: Calculate TCO from A0+A2
        tco_results = TCOCalculator.calculate_from_files(a0_path, a2_path, tco_years=tco_years)

        # Step 2: Load A0 for tier metadata
        a0_data = _load_json(a0_path)

        # Step 3: Load A5 for review insights (optional)
        a5_data = _load_json(a5_path) if a5_path else {}

        # Step 4: Build review index
        a5_index = {}
        for p in a5_data.get("products", []):
            name = p.get("product_name", "")
            if name:
                a5_index[name] = p

        # Step 5: Build export
        export = {
            "category": category,
            "domain": domain,
            "tco_years": tco_years,
            "generated_at": datetime.now().isoformat(),
            "selected_tier": a0_data.get("selected_tier", ""),
            "tier_scores": a0_data.get("tier_scores", {}),
            "tier_product_counts": a0_data.get("tier_product_counts", {}),
            "credibility": _build_credibility(a0_data, a5_data),
            "products": [],
        }

        # Step 6: Enrich each product with A5 data
        for tco in tco_results:
            product_name = tco["name"]
            a5_product = _find_by_name(a5_index, product_name)

            product_export = {
                "product_id": tco["product_id"],
                "name": tco["name"],
                "brand": tco["brand"],
                "release_date": tco.get("release_date"),
                "source_a0_rank": tco.get("source_a0_rank", 0),
                "a0_total_score": tco.get("a0_total_score", 0),
                "tco": tco["tco"],
                "notes": tco.get("notes", ""),
            }

            # Add A5 review data if available
            if a5_product:
                product_export["review_insights"] = {
                    "reviews_collected": a5_product.get("reviews_collected", 0),
                    "purchase_motivations": a5_product.get("purchase_motivations", []),
                    "sentiment_keywords": a5_product.get("sentiment_keywords", {}),
                    "hidden_differentiator": a5_product.get("hidden_differentiator", ""),
                    "environment_splits": a5_product.get("environment_splits", []),
                }
                # AS reputation from A5 (qualitative, not quantified)
                product_export["as_reputation"] = a5_product.get("as_reputation", "")
                product_export["as_reputation_summary"] = a5_product.get("as_reputation_summary", "")

            export["products"].append(product_export)

        # Step 7: Add category-level insights from A5
        if a5_data.get("category_insights"):
            export["category_insights"] = a5_data["category_insights"]

        # Step 8: Build summary
        export["summary"] = _build_summary(export["products"])

        # Step 9: TCO verification
        verification = _verify_tco(export["products"], tco_years=tco_years)
        if verification["errors"]:
            logger.error("TCO verification FAILED: %s", verification["errors"])
            export["_verification"] = verification
        else:
            logger.info("TCO verification passed for all %d products", len(export["products"]))

        # Step 10: Write to file
        if output_path is None:
            export_dir = _PROJECT_ROOT / "data" / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            safe_category = category.replace(" ", "_")
            output_path = export_dir / f"tco_{safe_category}.json"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2, default=str)

        logger.info(
            "Exported TCO data for %s (%d products) -> %s",
            category, len(export["products"]), output_path,
        )
        return export


# ================================================================
# Helper functions
# ================================================================

def _load_json(path: str | Path | None) -> dict:
    if path is None:
        return {}
    path = Path(path)
    if not path.exists():
        logger.warning("File not found: %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_by_name(index: dict[str, dict], target: str) -> dict | None:
    if target in index:
        return index[target]
    for key, value in index.items():
        if key in target or target in key:
            return value
    return None


def _build_credibility(a0_data: dict, a5_data: dict) -> dict:
    """Build credibility metadata from A0 and A5."""
    products = (
        a0_data.get("selected_products")
        or a0_data.get("final_products")
        or a0_data.get("a0_summary", {}).get("top_3", [])
    )
    product_count = len(products) if products else 0
    pool_size = a0_data.get("candidate_pool_size") or a0_data.get("a0_summary", {}).get("candidate_pool_size", 0)

    review_count = a5_data.get("total_reviews_analyzed", 0)
    review_sources = a5_data.get("review_sources", [])

    return {
        "product_count": product_count,
        "candidate_pool_size": pool_size,
        "total_reviews_analyzed": review_count,
        "review_sources": review_sources,
        "data_pipeline": "A0(product selection) -> A2(consumables) -> A5(reviews) -> A4(TCO)",
    }


def _build_summary(products: list[dict]) -> dict:
    """Build cost summary from product list."""
    if not products:
        return {}

    costs = [(p["name"], p["tco"]["real_cost_total"]) for p in products]
    costs.sort(key=lambda x: x[1])

    cheapest = costs[0]
    most_expensive = costs[-1]
    diff = most_expensive[1] - cheapest[1]
    diff_pct = round((diff / cheapest[1]) * 100) if cheapest[1] > 0 else 0

    return {
        "cheapest": {"name": cheapest[0], "real_cost_total": cheapest[1]},
        "most_expensive": {"name": most_expensive[0], "real_cost_total": most_expensive[1]},
        "cost_difference": diff,
        "cost_difference_pct": diff_pct,
        "total_cost_range": {
            "lowest": cheapest[1],
            "highest": most_expensive[1],
        },
    }


def _verify_tco(products: list[dict], tco_years: int = 3) -> dict:
    """Verify TCO calculations for all products.

    Checks:
    1. consumable_cost_total == annual_consumable_cost * tco_years
    2. real_cost_total == purchase_price + consumable_cost_total
    """
    errors = []
    for p in products:
        tco = p.get("tco", {})
        name = p.get("name", "unknown")

        annual = tco.get("annual_consumable_cost", 0)
        consumable_total = tco.get("consumable_cost_total", 0)
        purchase = tco.get("purchase_price", 0)
        real_cost = tco.get("real_cost_total", 0)

        # Check 1: consumable_cost_total == annual * tco_years
        expected_total = annual * tco_years
        if consumable_total != expected_total:
            errors.append(
                f"{name}: consumable_cost_total={consumable_total} != "
                f"annual_consumable_cost*{tco_years}={expected_total}"
            )

        # Check 2: real_cost_total == purchase + consumable_cost_total
        expected_real = purchase + consumable_total
        if real_cost != expected_real:
            errors.append(
                f"{name}: real_cost_total={real_cost} != "
                f"purchase({purchase}) + consumable_total({consumable_total}) = {expected_real}"
            )

    return {
        "verified": len(errors) == 0,
        "product_count": len(products),
        "errors": errors,
    }
