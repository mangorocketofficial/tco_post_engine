"""Price tier classification for product selection.

Classifies candidate products into Premium / Mid / Budget tiers
based on their price position within the candidate pool.
"""

from __future__ import annotations

import logging
import math

from .models import CandidateProduct, PricePosition

logger = logging.getLogger(__name__)


class PriceClassifier:
    """Classifies products into price tiers.

    Tier boundaries (by percentile in the candidate pool):
    - Premium: top 30% by price
    - Mid: middle 40% by price
    - Budget: bottom 30% by price

    Usage:
        classifier = PriceClassifier()
        positions = classifier.classify_candidates(candidates)
    """

    def classify_candidates(
        self, candidates: list[CandidateProduct]
    ) -> list[PricePosition]:
        """Classify all candidates into price tiers.

        Uses prices from rankings data already collected by sales scrapers.

        Args:
            candidates: CandidateProduct list with rankings containing prices.

        Returns:
            List of PricePosition with tier and normalized price.
        """
        # Extract best price per candidate
        prices = self._get_best_prices(candidates)

        if not prices:
            return []

        # Assign tiers
        tiers = self._assign_tiers(prices)

        # Normalize prices to 0.0–1.0
        normalized = self._normalize_prices(prices)

        results: list[PricePosition] = []
        for candidate in candidates:
            name = candidate.name
            price = prices.get(name, 0)
            if price <= 0:
                continue

            position = PricePosition(
                product_name=name,
                current_price=price,
                avg_price_90d=price,  # Using current as proxy in MVP
                price_tier=tiers.get(name, "mid"),
                price_normalized=normalized.get(name, 0.5),
            )
            results.append(position)

        logger.info(
            "Classified %d products: %s",
            len(results),
            {p.product_name: p.price_tier for p in results},
        )
        return results

    @staticmethod
    def _get_best_prices(candidates: list[CandidateProduct]) -> dict[str, int]:
        """Extract the best (lowest) price for each candidate from rankings."""
        prices: dict[str, int] = {}
        for c in candidates:
            candidate_prices = [r.price for r in c.rankings if r.price > 0]
            if candidate_prices:
                prices[c.name] = min(candidate_prices)
        return prices

    @staticmethod
    def _assign_tiers(prices: dict[str, int]) -> dict[str, str]:
        """Assign tier labels based on percentile position.

        Sorted by price:
        - Bottom 30% -> budget
        - Middle 40% -> mid
        - Top 30% -> premium
        """
        if not prices:
            return {}

        sorted_items = sorted(prices.items(), key=lambda x: x[1])
        n = len(sorted_items)

        if n <= 2:
            # With 1-2 products, assign directly
            tiers: dict[str, str] = {}
            if n == 1:
                tiers[sorted_items[0][0]] = "mid"
            else:
                tiers[sorted_items[0][0]] = "budget"
                tiers[sorted_items[1][0]] = "premium"
            return tiers

        budget_count = max(1, math.ceil(n * 0.3))
        premium_count = max(1, math.ceil(n * 0.3))
        # Mid gets the remainder
        mid_count = n - budget_count - premium_count
        if mid_count < 0:
            mid_count = 0
            budget_count = n // 2
            premium_count = n - budget_count

        tiers = {}
        for i, (name, _) in enumerate(sorted_items):
            if i < budget_count:
                tiers[name] = "budget"
            elif i < budget_count + mid_count:
                tiers[name] = "mid"
            else:
                tiers[name] = "premium"

        return tiers

    @staticmethod
    def _normalize_prices(prices: dict[str, int]) -> dict[str, float]:
        """Normalize prices to 0.0–1.0 range (min=0.0, max=1.0)."""
        if not prices:
            return {}

        values = list(prices.values())
        min_p = min(values)
        max_p = max(values)
        spread = max_p - min_p

        if spread == 0:
            return {name: 0.5 for name in prices}

        return {
            name: (price - min_p) / spread
            for name, price in prices.items()
        }
