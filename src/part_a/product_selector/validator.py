"""Validation checks for the 3-product selection.

Validates brand diversity, price spread, data sufficiency, recency,
and availability. Includes auto-fix for brand diversity failures.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from .category_config import CategoryConfig
from .models import CandidateProduct, ProductScores, SlotAssignment, ValidationResult

logger = logging.getLogger(__name__)


class SelectionValidator:
    """Validates the 3-product selection against business rules.

    Checks:
    1. Brand diversity — 3 different brands
    2. Price spread — max price >= 1.3x min price
    3. Data sufficiency — each product >= min_community_posts
    4. Recency — released within max_product_age_months
    5. Availability — all in stock

    Usage:
        validator = SelectionValidator(category_config)
        results = validator.validate(assignments)
    """

    def __init__(self, category_config: CategoryConfig) -> None:
        self.category_config = category_config

    def validate(
        self, assignments: list[SlotAssignment]
    ) -> list[ValidationResult]:
        """Run all validation checks.

        Args:
            assignments: List of 3 SlotAssignment.

        Returns:
            List of ValidationResult (one per check).
        """
        return [
            self._check_brand_diversity(assignments),
            self._check_price_spread(assignments),
            self._check_data_sufficiency(assignments),
            self._check_recency(assignments),
            self._check_availability(assignments),
        ]

    def validate_and_fix(
        self,
        assignments: list[SlotAssignment],
        candidates: list[CandidateProduct],
        scores: dict[str, ProductScores],
    ) -> tuple[list[SlotAssignment], list[ValidationResult]]:
        """Validate and attempt to fix failures.

        Currently auto-fixes:
        - Brand diversity: swaps duplicate-brand product for next-best

        Args:
            assignments: Current 3 SlotAssignment.
            candidates: Full candidate pool for swapping.
            scores: All product scores.

        Returns:
            Tuple of (possibly-modified assignments, validation results).
        """
        results = self.validate(assignments)

        # Check if brand diversity failed
        brand_result = results[0]
        if not brand_result.passed:
            fixed = self._fix_brand_diversity(assignments, candidates, scores)
            if fixed:
                assignments = fixed
                results = self.validate(assignments)
                logger.info("Auto-fixed brand diversity issue")

        return assignments, results

    def _check_brand_diversity(
        self, assignments: list[SlotAssignment]
    ) -> ValidationResult:
        """All 3 products should be from different brands."""
        brands = [a.candidate.brand for a in assignments]
        unique_brands = set(brands)

        if len(unique_brands) == len(brands):
            return ValidationResult(
                check_name="brand_diversity",
                passed=True,
                detail=f"{len(unique_brands)} unique brands: {', '.join(unique_brands)}",
            )
        else:
            duplicates = [b for b in brands if brands.count(b) > 1]
            return ValidationResult(
                check_name="brand_diversity",
                passed=False,
                detail=f"Duplicate brand(s): {', '.join(set(duplicates))}",
            )

    def _check_price_spread(
        self, assignments: list[SlotAssignment]
    ) -> ValidationResult:
        """Max price should be >= 1.3x min price."""
        prices = []
        for a in assignments:
            if a.candidate.price_position:
                prices.append(a.candidate.price_position.current_price)
            else:
                # Fallback: use best price from rankings
                ranking_prices = [r.price for r in a.candidate.rankings if r.price > 0]
                if ranking_prices:
                    prices.append(min(ranking_prices))

        if len(prices) < 2:
            return ValidationResult(
                check_name="price_spread",
                passed=True,
                detail="Insufficient price data to check",
            )

        min_price = min(prices)
        max_price = max(prices)

        if min_price <= 0:
            return ValidationResult(
                check_name="price_spread",
                passed=True,
                detail="Min price is zero, skipping check",
            )

        ratio = max_price / min_price
        passed = ratio >= 1.3

        return ValidationResult(
            check_name="price_spread",
            passed=passed,
            detail=f"{ratio:.2f}x ratio ({min_price:,}원 to {max_price:,}원)",
        )

    def _check_data_sufficiency(
        self, assignments: list[SlotAssignment]
    ) -> ValidationResult:
        """Each product needs >= min_community_posts."""
        threshold = self.category_config.min_community_posts
        insufficient: list[str] = []

        for a in assignments:
            total = 0
            if a.candidate.sentiment:
                total = a.candidate.sentiment.total_posts
            if total < threshold:
                insufficient.append(f"{a.candidate.name} ({total} posts)")

        if not insufficient:
            return ValidationResult(
                check_name="data_sufficiency",
                passed=True,
                detail=f"All products have >= {threshold} community posts",
            )
        else:
            return ValidationResult(
                check_name="data_sufficiency",
                passed=False,
                detail=f"Below {threshold} posts: {'; '.join(insufficient)}",
            )

    def _check_recency(
        self, assignments: list[SlotAssignment]
    ) -> ValidationResult:
        """All products released within max_product_age_months."""
        max_months = self.category_config.max_product_age_months
        cutoff = date.today() - timedelta(days=max_months * 30)
        old_products: list[str] = []

        for a in assignments:
            if a.candidate.release_date and a.candidate.release_date < cutoff:
                old_products.append(a.candidate.name)

        # Products without release_date pass by default
        if not old_products:
            return ValidationResult(
                check_name="recency",
                passed=True,
                detail=f"All products within {max_months} months",
            )
        else:
            return ValidationResult(
                check_name="recency",
                passed=False,
                detail=f"Older than {max_months} months: {', '.join(old_products)}",
            )

    def _check_availability(
        self, assignments: list[SlotAssignment]
    ) -> ValidationResult:
        """All products must be in stock."""
        unavailable = [
            a.candidate.name for a in assignments if not a.candidate.in_stock
        ]

        if not unavailable:
            return ValidationResult(
                check_name="availability",
                passed=True,
                detail="All products in stock",
            )
        else:
            return ValidationResult(
                check_name="availability",
                passed=False,
                detail=f"Out of stock: {', '.join(unavailable)}",
            )

    def _fix_brand_diversity(
        self,
        assignments: list[SlotAssignment],
        candidates: list[CandidateProduct],
        scores: dict[str, ProductScores],
    ) -> list[SlotAssignment] | None:
        """Swap the lower-scored duplicate-brand product for next-best different brand.

        Returns new assignments list, or None if no fix is possible.
        """
        brands = [a.candidate.brand for a in assignments]
        selected_names = {a.candidate.name for a in assignments}

        # Find duplicate brands
        seen: dict[str, int] = {}
        duplicate_indices: list[int] = []
        for i, brand in enumerate(brands):
            if brand in seen:
                # Keep the first occurrence, mark the duplicate for swap
                duplicate_indices.append(i)
            else:
                seen[brand] = i

        if not duplicate_indices:
            return None

        # For each duplicate, find the best replacement from a different brand
        new_assignments = list(assignments)
        used_brands = set(brands)

        for idx in duplicate_indices:
            current = assignments[idx]
            current_slot = current.slot

            # Find candidates not already selected and from a different brand
            alternatives = [
                c for c in candidates
                if c.name not in selected_names
                and c.brand not in used_brands
            ]

            if not alternatives:
                # Try allowing brands not in current selection (relaxed)
                alternatives = [
                    c for c in candidates
                    if c.name not in selected_names
                    and c.brand != current.candidate.brand
                ]

            if not alternatives:
                return None  # Can't fix

            # Pick the best alternative by weighted total
            best = max(
                alternatives,
                key=lambda c: scores[c.name].weighted_total if c.name in scores else 0,
            )

            new_assignments[idx] = SlotAssignment(
                slot=current_slot,
                candidate=best,
                scores=scores.get(best.name, current.scores),
                selection_reasons=[
                    f"Swapped from {current.candidate.name} for brand diversity"
                ],
            )
            selected_names.add(best.name)
            used_brands.add(best.brand)

            logger.info(
                "Brand diversity fix: [%s] %s → %s",
                current_slot,
                current.candidate.name,
                best.name,
            )

        return new_assignments
