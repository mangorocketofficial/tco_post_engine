"""3-slot product selection algorithm.

Assigns candidates to Stability / Balance / Value slots based on
weighted scores, implementing the consumer decision architecture.
"""

from __future__ import annotations

import logging

from .models import CandidateProduct, ProductScores, SlotAssignment

logger = logging.getLogger(__name__)


class SlotSelector:
    """Assigns 3 products to Stability/Balance/Value slots.

    Selection algorithm:
    - Stability: Premium/Mid tier, max(sentiment*0.6 + resale*0.4)
    - Balance: Exclude stability, max(search*0.5 + sales*0.3 + sentiment*0.2)
    - Value: Mid/Budget tier, exclude previous, max(sales*0.4 + (1-price_norm)*0.4 + sentiment*0.2)

    Usage:
        selector = SlotSelector()
        assignments = selector.select(candidates, scores)
    """

    def select(
        self,
        candidates: list[CandidateProduct],
        scores: dict[str, ProductScores],
    ) -> list[SlotAssignment]:
        """Run the 3-slot selection algorithm.

        Args:
            candidates: List of scored CandidateProduct.
            scores: Dict mapping product name to ProductScores.

        Returns:
            List of 3 SlotAssignment objects [stability, balance, value].

        Raises:
            ValueError: If fewer than 3 eligible candidates.
        """
        if len(candidates) < 3:
            raise ValueError(
                f"Need at least 3 candidates for selection, got {len(candidates)}"
            )

        exclude: set[str] = set()

        # 1. Stability slot
        stability = self._select_stability(candidates, scores)
        exclude.add(stability.candidate.name)

        # 2. Balance slot
        balance = self._select_balance(candidates, scores, exclude)
        exclude.add(balance.candidate.name)

        # 3. Value slot
        value = self._select_value(candidates, scores, exclude)

        assignments = [stability, balance, value]

        for a in assignments:
            logger.info(
                "Slot [%s]: %s (%s) — score=%.3f",
                a.slot.upper(),
                a.candidate.name,
                a.candidate.brand,
                a.scores.weighted_total,
            )

        return assignments

    def _select_stability(
        self,
        candidates: list[CandidateProduct],
        scores: dict[str, ProductScores],
    ) -> SlotAssignment:
        """Select the stability pick.

        Filter: Premium or Mid tier only.
        Rank by: sentiment * 0.6 + resale_retention * 0.4
        """
        pool = [
            c for c in candidates
            if c.price_position and c.price_position.price_tier in ("premium", "mid")
        ]
        # Fallback: if no premium/mid, use all
        if not pool:
            pool = list(candidates)

        def stability_score(c: CandidateProduct) -> float:
            s = scores.get(c.name)
            if not s:
                return 0.0
            return s.sentiment * 0.6 + s.resale_retention * 0.4

        pick = max(pool, key=stability_score)
        s = scores[pick.name]

        reasons = self._generate_reasons("stability", pick, s)

        return SlotAssignment(
            slot="stability",
            candidate=pick,
            scores=s,
            selection_reasons=reasons,
        )

    def _select_balance(
        self,
        candidates: list[CandidateProduct],
        scores: dict[str, ProductScores],
        exclude: set[str],
    ) -> SlotAssignment:
        """Select the balance pick.

        Exclude: stability pick.
        Rank by: search_interest * 0.5 + sales_presence * 0.3 + sentiment * 0.2
        """
        pool = [c for c in candidates if c.name not in exclude]

        def balance_score(c: CandidateProduct) -> float:
            s = scores.get(c.name)
            if not s:
                return 0.0
            return s.search_interest * 0.5 + s.sales_presence * 0.3 + s.sentiment * 0.2

        pick = max(pool, key=balance_score)
        s = scores[pick.name]

        reasons = self._generate_reasons("balance", pick, s)

        return SlotAssignment(
            slot="balance",
            candidate=pick,
            scores=s,
            selection_reasons=reasons,
        )

    def _select_value(
        self,
        candidates: list[CandidateProduct],
        scores: dict[str, ProductScores],
        exclude: set[str],
    ) -> SlotAssignment:
        """Select the value pick.

        Filter: Mid or Budget tier only. Exclude: stability + balance picks.
        Rank by: sales_presence * 0.4 + (1 - price_normalized) * 0.4 + sentiment * 0.2
        """
        pool = [
            c for c in candidates
            if c.name not in exclude
            and (
                not c.price_position
                or c.price_position.price_tier in ("mid", "budget")
            )
        ]
        # Fallback: if no mid/budget, use all remaining
        if not pool:
            pool = [c for c in candidates if c.name not in exclude]

        def value_score(c: CandidateProduct) -> float:
            s = scores.get(c.name)
            if not s:
                return 0.0
            return (
                s.sales_presence * 0.4
                + (1.0 - s.price_normalized) * 0.4
                + s.sentiment * 0.2
            )

        pick = max(pool, key=value_score)
        s = scores[pick.name]

        reasons = self._generate_reasons("value", pick, s)

        return SlotAssignment(
            slot="value",
            candidate=pick,
            scores=s,
            selection_reasons=reasons,
        )

    @staticmethod
    def _generate_reasons(
        slot: str,
        candidate: CandidateProduct,
        scores: ProductScores,
    ) -> list[str]:
        """Generate human-readable selection reasons."""
        reasons: list[str] = []

        if slot == "stability":
            if candidate.sentiment:
                reasons.append(
                    f"Complaint rate: {candidate.sentiment.complaint_rate:.2f}"
                )
            if candidate.resale_check:
                reasons.append(
                    f"Resale ratio: {candidate.resale_check.resale_ratio:.2f}"
                )
            reasons.append(f"Sentiment score: {scores.sentiment:.2f}")

        elif slot == "balance":
            reasons.append(f"Search interest score: {scores.search_interest:.2f}")
            reasons.append(f"Sales presence score: {scores.sales_presence:.2f}")
            if candidate.search_interest:
                reasons.append(
                    f"Trend: {candidate.search_interest.trend_direction}"
                )

        elif slot == "value":
            if candidate.price_position:
                reasons.append(
                    f"Price tier: {candidate.price_position.price_tier} "
                    f"({candidate.price_position.current_price:,}원)"
                )
            reasons.append(f"Sales presence score: {scores.sales_presence:.2f}")
            reasons.append(f"Price advantage: {1.0 - scores.price_normalized:.2f}")

        reasons.append(f"Presence on {candidate.presence_score} platforms")
        return reasons
