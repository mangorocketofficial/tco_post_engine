"""Product scoring — normalizes raw data into 0.0–1.0 scores.

Scores candidates across 5 dimensions with weights:
- Sales Presence: 20%
- Search Interest: 25%
- Sentiment: 25%
- Price Position: 15%
- Resale Retention: 15%
"""

from __future__ import annotations

import logging

from .models import CandidateProduct, ProductScores

logger = logging.getLogger(__name__)


class ProductScorer:
    """Normalizes raw candidate data into scores for slot selection.

    All scores are relative to the candidate pool (best = 1.0, worst = 0.0).

    Usage:
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
        # scores["로보락 Q Revo S"].weighted_total -> 0.82
    """

    def score_candidates(
        self, candidates: list[CandidateProduct]
    ) -> dict[str, ProductScores]:
        """Score all candidates across 5 dimensions.

        Args:
            candidates: List of CandidateProduct with all data populated.

        Returns:
            Dict mapping product name to ProductScores.
        """
        if not candidates:
            return {}

        sales = self._normalize_sales_presence(candidates)
        search = self._normalize_search_interest(candidates)
        sentiment = self._normalize_sentiment(candidates)
        price_pos = self._normalize_price_position(candidates)
        resale = self._normalize_resale_retention(candidates)

        scores: dict[str, ProductScores] = {}
        for c in candidates:
            name = c.name
            ps = ProductScores(
                product_name=name,
                sales_presence=sales.get(name, 0.0),
                search_interest=search.get(name, 0.0),
                sentiment=sentiment.get(name, 0.5),
                price_position=price_pos.get(name, 0.5),
                resale_retention=resale.get(name, 0.0),
                price_normalized=c.price_position.price_normalized if c.price_position else 0.5,
            )
            scores[name] = ps
            logger.debug(
                "Score %s: sales=%.2f search=%.2f sent=%.2f price=%.2f resale=%.2f total=%.2f",
                name, ps.sales_presence, ps.search_interest,
                ps.sentiment, ps.price_position, ps.resale_retention,
                ps.weighted_total,
            )

        return scores

    @staticmethod
    def _normalize_sales_presence(
        candidates: list[CandidateProduct],
    ) -> dict[str, float]:
        """Normalize presence_score: score / max_presence_score."""
        max_presence = max((c.presence_score for c in candidates), default=1)
        if max_presence == 0:
            max_presence = 1
        return {
            c.name: c.presence_score / max_presence
            for c in candidates
        }

    @staticmethod
    def _normalize_search_interest(
        candidates: list[CandidateProduct],
    ) -> dict[str, float]:
        """Normalize search volume: volume_30d / max_volume."""
        volumes = {
            c.name: c.search_interest.volume_30d if c.search_interest else 0.0
            for c in candidates
        }
        max_vol = max(volumes.values(), default=1.0)
        if max_vol <= 0:
            max_vol = 1.0
        return {name: vol / max_vol for name, vol in volumes.items()}

    @staticmethod
    def _normalize_sentiment(
        candidates: list[CandidateProduct],
    ) -> dict[str, float]:
        """Normalize sentiment: (satisfaction_rate - complaint_rate + 1) / 2.

        Maps [-1, 1] range to [0, 1].
        """
        result: dict[str, float] = {}
        for c in candidates:
            if c.sentiment and c.sentiment.total_posts > 0:
                raw = c.sentiment.satisfaction_rate - c.sentiment.complaint_rate
                result[c.name] = (raw + 1.0) / 2.0
            else:
                result[c.name] = 0.5  # Neutral default
        return result

    @staticmethod
    def _normalize_price_position(
        candidates: list[CandidateProduct],
    ) -> dict[str, float]:
        """Normalize price tier: premium=1.0, mid=0.5, budget=0.0.

        Note: Higher is NOT inherently better — slot-specific formulas
        handle the tier semantics differently.
        """
        tier_map = {"premium": 1.0, "mid": 0.5, "budget": 0.0}
        return {
            c.name: tier_map.get(
                c.price_position.price_tier if c.price_position else "mid",
                0.5,
            )
            for c in candidates
        }

    @staticmethod
    def _normalize_resale_retention(
        candidates: list[CandidateProduct],
    ) -> dict[str, float]:
        """Normalize resale_ratio: ratio / max_ratio."""
        ratios = {
            c.name: c.resale_check.resale_ratio if c.resale_check else 0.0
            for c in candidates
        }
        max_ratio = max(ratios.values(), default=1.0)
        if max_ratio <= 0:
            max_ratio = 1.0
        return {name: ratio / max_ratio for name, ratio in ratios.items()}
