"""TOP 3 product selector.

Ranks all candidates by total_score and picks the top 3,
enforcing brand diversity (no duplicate brands).
"""

from __future__ import annotations

import logging

from .models import CandidateProduct, ProductScores, SelectedProduct

logger = logging.getLogger(__name__)


class TopSelector:
    """Selects TOP 3 products by keyword metric score.

    Enforces brand diversity: if a brand already has a pick,
    the next-best product from a different brand is chosen.

    Usage:
        selector = TopSelector()
        picks = selector.select(candidates, scores)
    """

    def select(
        self,
        candidates: list[CandidateProduct],
        scores: dict[str, ProductScores],
        top_n: int = 3,
    ) -> list[SelectedProduct]:
        """Select top N products by score with brand diversity.

        Args:
            candidates: All candidate products.
            scores: Product name → ProductScores mapping.
            top_n: Number of products to select (default 3).

        Returns:
            List of SelectedProduct, ranked 1 to top_n.

        Raises:
            ValueError: If fewer than top_n candidates available.
        """
        if len(candidates) < top_n:
            raise ValueError(
                f"Need at least {top_n} candidates, got {len(candidates)}"
            )

        # Sort by total_score descending
        ranked = sorted(
            candidates,
            key=lambda c: scores.get(c.name, ProductScores(product_name=c.name)).total_score,
            reverse=True,
        )

        picks: list[SelectedProduct] = []
        used_brands: set[str] = set()

        for c in ranked:
            if len(picks) >= top_n:
                break

            # Enforce brand diversity using manufacturer (not product line)
            if c.manufacturer in used_brands:
                continue

            s = scores.get(c.name, ProductScores(product_name=c.name))
            reasons = _generate_reasons(c, s)

            picks.append(SelectedProduct(
                rank=len(picks) + 1,
                candidate=c,
                scores=s,
                selection_reasons=reasons,
            ))
            used_brands.add(c.manufacturer)

        # If brand diversity filtered too many, fill remaining without constraint
        if len(picks) < top_n:
            selected_names = {p.candidate.name for p in picks}
            for c in ranked:
                if len(picks) >= top_n:
                    break
                if c.name in selected_names:
                    continue

                s = scores.get(c.name, ProductScores(product_name=c.name))
                reasons = _generate_reasons(c, s)
                reasons.append("(brand diversity relaxed)")

                picks.append(SelectedProduct(
                    rank=len(picks) + 1,
                    candidate=c,
                    scores=s,
                    selection_reasons=reasons,
                ))
                selected_names.add(c.name)

        for p in picks:
            logger.info(
                "Pick #%d: %s (%s) — score=%.3f",
                p.rank, p.candidate.name, p.candidate.brand, p.scores.total_score,
            )

        return picks


def _generate_reasons(
    candidate: CandidateProduct,
    scores: ProductScores,
) -> list[str]:
    """Generate human-readable selection reasons."""
    reasons: list[str] = []

    if candidate.keyword_metrics:
        km = candidate.keyword_metrics
        if km.monthly_clicks > 0:
            reasons.append(f"Monthly clicks: {km.monthly_clicks:,}")
        if km.avg_cpc > 0:
            reasons.append(f"Avg CPC: {km.avg_cpc:,}원")
        if km.monthly_search_volume > 0:
            reasons.append(f"Monthly searches: {km.monthly_search_volume:,}")
        reasons.append(f"Competition: {km.competition}")

    reasons.append(f"Total score: {scores.total_score:.3f}")
    return reasons
