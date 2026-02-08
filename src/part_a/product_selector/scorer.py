"""Product scoring based on Naver Search Ad keyword metrics.

Score = clicks×0.4 + cpc×0.3 + search_volume×0.2 + competition×0.1

All scores are min-max normalized within the candidate pool (0.0-1.0).
"""

from __future__ import annotations

import logging

from .models import CandidateProduct, ProductScores

logger = logging.getLogger(__name__)

COMPETITION_MAP = {"high": 1.0, "medium": 0.5, "low": 0.0}


class ProductScorer:
    """Scores candidates using Naver Search Ad keyword metrics.

    Usage:
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)
    """

    def score_candidates(
        self, candidates: list[CandidateProduct]
    ) -> dict[str, ProductScores]:
        """Score all candidates based on keyword metrics.

        Args:
            candidates: List of CandidateProduct with keyword_metrics populated.

        Returns:
            Dict mapping product name to ProductScores.
        """
        if not candidates:
            return {}

        clicks_vals = {
            c.name: c.keyword_metrics.monthly_clicks if c.keyword_metrics else 0
            for c in candidates
        }
        cpc_vals = {
            c.name: c.keyword_metrics.avg_cpc if c.keyword_metrics else 0
            for c in candidates
        }
        search_vals = {
            c.name: c.keyword_metrics.monthly_search_volume if c.keyword_metrics else 0
            for c in candidates
        }
        comp_vals = {
            c.name: COMPETITION_MAP.get(
                c.keyword_metrics.competition if c.keyword_metrics else "low", 0.0
            )
            for c in candidates
        }

        norm_clicks = _min_max_normalize(clicks_vals)
        norm_cpc = _min_max_normalize(cpc_vals)
        norm_search = _min_max_normalize(search_vals)

        scores: dict[str, ProductScores] = {}
        for c in candidates:
            ps = ProductScores(
                product_name=c.name,
                clicks_score=norm_clicks.get(c.name, 0.0),
                cpc_score=norm_cpc.get(c.name, 0.0),
                search_volume_score=norm_search.get(c.name, 0.0),
                competition_score=comp_vals.get(c.name, 0.0),
            )
            scores[c.name] = ps
            logger.debug(
                "Score %s: clicks=%.2f cpc=%.2f search=%.2f comp=%.2f total=%.3f",
                c.name, ps.clicks_score, ps.cpc_score,
                ps.search_volume_score, ps.competition_score,
                ps.total_score,
            )

        return scores


def _min_max_normalize(values: dict[str, int | float]) -> dict[str, float]:
    """Min-max normalize values to 0.0-1.0 range."""
    if not values:
        return {}
    min_val = min(values.values())
    max_val = max(values.values())
    spread = max_val - min_val
    if spread <= 0:
        return {k: 0.5 for k in values}
    return {k: (v - min_val) / spread for k, v in values.items()}
