"""Price tier classification for product selection.

Classifies candidate products into Premium / Mid / Budget tiers
based on their price position within the candidate pool.

v3 changes:
- Added MAX_TIER_PRICE_RATIO (default 3.0) to prevent extreme spreads within a tier
- When max/min ratio within a tier exceeds this threshold, products above
  the largest price gap are promoted to the next tier
- Added tier_spread_check validation
"""

from __future__ import annotations

import logging
import math

from .models import CandidateProduct, PricePosition

logger = logging.getLogger(__name__)

# Maximum allowed price ratio (max/min) within a single tier.
# If exceeded, the tier is split at the largest price gap.
# Example: 864,000 / 146,000 = 5.9x > 3.0x → split
MAX_TIER_PRICE_RATIO = 3.0


class PriceClassifier:
    """Classifies products into price tiers.

    Tier boundaries (by percentile in the candidate pool):
    - Premium: top 30% by price
    - Mid: middle 40% by price
    - Budget: bottom 30% by price

    Post-processing: validates that no tier has an internal price ratio
    exceeding MAX_TIER_PRICE_RATIO. If violated, splits at the largest gap.

    Usage:
        classifier = PriceClassifier()
        positions = classifier.classify_candidates(candidates)
    """

    def classify_candidates(
        self, candidates: list[CandidateProduct]
    ) -> list[PricePosition]:
        """Classify all candidates into price tiers."""
        # Extract best price per candidate
        prices = self._get_best_prices(candidates)

        if not prices:
            return []

        # Assign tiers (percentile-based)
        tiers = self._assign_tiers(prices)

        # Post-process: enforce max ratio within each tier
        tiers = self._enforce_max_ratio(prices, tiers)

        # Normalize prices to 0.0-1.0
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
            # Try rankings first
            candidate_prices = [r.price for r in c.rankings if r.price > 0]
            if candidate_prices:
                prices[c.name] = min(candidate_prices)
            # Fallback to candidate.price if no rankings
            elif c.price > 0:
                prices[c.name] = c.price
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
            tiers: dict[str, str] = {}
            if n == 1:
                tiers[sorted_items[0][0]] = "mid"
            else:
                tiers[sorted_items[0][0]] = "budget"
                tiers[sorted_items[1][0]] = "premium"
            return tiers

        budget_count = max(1, math.ceil(n * 0.3))
        premium_count = max(1, math.ceil(n * 0.3))
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
    def _enforce_max_ratio(
        prices: dict[str, int], tiers: dict[str, str]
    ) -> dict[str, str]:
        """Enforce MAX_TIER_PRICE_RATIO within each tier.

        If a tier's max/min price ratio exceeds the threshold,
        find the largest price gap within that tier and promote
        products above the gap to the next higher tier.

        Promotion chain: budget -> mid -> premium
        Products already in premium cannot be promoted further.
        """
        tier_order = ["budget", "mid", "premium"]
        updated_tiers = dict(tiers)

        for tier_idx, tier_name in enumerate(tier_order):
            # Get products in this tier, sorted by price
            tier_products = sorted(
                [(name, prices[name]) for name, t in updated_tiers.items() if t == tier_name],
                key=lambda x: x[1],
            )

            if len(tier_products) < 2:
                continue

            min_price = tier_products[0][1]
            max_price = tier_products[-1][1]

            if min_price <= 0:
                continue

            ratio = max_price / min_price

            if ratio <= MAX_TIER_PRICE_RATIO:
                continue

            # Ratio exceeded — find the largest price gap
            logger.warning(
                "Tier '%s' price ratio %.1fx exceeds %.1fx limit "
                "(min=%s, max=%s). Splitting at largest gap.",
                tier_name,
                ratio,
                MAX_TIER_PRICE_RATIO,
                f"{min_price:,}",
                f"{max_price:,}",
            )

            largest_gap = 0
            gap_index = 0
            for i in range(len(tier_products) - 1):
                gap = tier_products[i + 1][1] - tier_products[i][1]
                if gap > largest_gap:
                    largest_gap = gap
                    gap_index = i + 1

            # Promote products above the gap to the next tier
            if tier_idx < len(tier_order) - 1:
                next_tier = tier_order[tier_idx + 1]
                promoted = []
                for name, price in tier_products[gap_index:]:
                    updated_tiers[name] = next_tier
                    promoted.append(f"{name}({price:,})")

                logger.info(
                    "Promoted %d products from '%s' to '%s': %s",
                    len(promoted),
                    tier_name,
                    next_tier,
                    ", ".join(promoted),
                )
            else:
                logger.warning(
                    "Cannot promote from 'premium' tier. "
                    "Consider reviewing candidate pool price distribution."
                )

        # Iterative: after promoting, the receiving tier might also exceed.
        # Run up to 3 additional passes (budget->mid, mid->premium cascade).
        for _pass in range(3):
            any_change = False
            for tier_idx2, tier_name2 in enumerate(tier_order[:-1]):  # skip premium
                tier_products2 = sorted(
                    [(name, prices[name]) for name, t in updated_tiers.items() if t == tier_name2],
                    key=lambda x: x[1],
                )
                if len(tier_products2) < 2:
                    continue
                min_p2 = tier_products2[0][1]
                max_p2 = tier_products2[-1][1]
                if min_p2 <= 0 or max_p2 / min_p2 <= MAX_TIER_PRICE_RATIO:
                    continue

                largest_gap2 = 0
                gap_idx2 = 0
                for i in range(len(tier_products2) - 1):
                    gap2 = tier_products2[i + 1][1] - tier_products2[i][1]
                    if gap2 > largest_gap2:
                        largest_gap2 = gap2
                        gap_idx2 = i + 1

                next_tier2 = tier_order[tier_idx2 + 1]
                for name, _ in tier_products2[gap_idx2:]:
                    updated_tiers[name] = next_tier2
                any_change = True

            if not any_change:
                break

        return updated_tiers

    @staticmethod
    def validate_selected_products_spread(
        selected_prices: list[int],
        max_ratio: float = MAX_TIER_PRICE_RATIO,
    ) -> tuple[bool, str]:
        """Validate that selected TOP 3 products have reasonable price spread.

        Call this AFTER TOP 3 selection to catch cases where the winning
        tier itself was too broad (e.g., premium tier with 4x spread).

        Args:
            selected_prices: List of prices for selected products.
            max_ratio: Maximum allowed ratio (default: MAX_TIER_PRICE_RATIO).

        Returns:
            (passed, message) tuple.
        """
        if len(selected_prices) < 2:
            return True, "Only 1 product, no spread check needed"

        valid_prices = [p for p in selected_prices if p > 0]
        if len(valid_prices) < 2:
            return True, "Insufficient prices for spread check"

        min_p = min(valid_prices)
        max_p = max(valid_prices)
        ratio = max_p / min_p

        if ratio <= max_ratio:
            return True, f"Price spread {ratio:.1f}x within {max_ratio}x limit"

        return False, (
            f"Price spread {ratio:.1f}x exceeds {max_ratio}x limit "
            f"(min={min_p:,}, max={max_p:,}). "
            f"Consider replacing the outlier product with the next candidate."
        )

    @staticmethod
    def _normalize_prices(prices: dict[str, int]) -> dict[str, float]:
        """Normalize prices to 0.0-1.0 range (min=0.0, max=1.0)."""
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

    @staticmethod
    def validate_tier_spread(prices: dict[str, int], tiers: dict[str, str]) -> list[str]:
        """Validate that no tier has excessive price spread.

        Returns list of warning messages. Empty list = all tiers OK.
        """
        warnings = []
        for tier_name in ["budget", "mid", "premium"]:
            tier_prices = [
                prices[name] for name, t in tiers.items()
                if t == tier_name and prices.get(name, 0) > 0
            ]
            if len(tier_prices) < 2:
                continue

            min_p = min(tier_prices)
            max_p = max(tier_prices)
            if min_p > 0:
                ratio = max_p / min_p
                if ratio > MAX_TIER_PRICE_RATIO:
                    warnings.append(
                        f"Tier '{tier_name}': {max_p:,}/{min_p:,} = {ratio:.1f}x "
                        f"(exceeds {MAX_TIER_PRICE_RATIO}x limit)"
                    )
        return warnings