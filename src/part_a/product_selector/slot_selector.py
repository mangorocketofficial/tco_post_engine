"""Single-tier product selector.

Selects the winning price tier (highest aggregate score), then picks
the top 3 products from that tier by score. Products with total_score < 0.1
are filtered out to avoid zero-data placeholders.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .models import CandidateProduct, ProductScores, SelectedProduct

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Tier names in preference order (used for tie-breaking / adjacency)
TIER_ORDER = ["premium", "mid", "budget"]

# Minimum score to be eligible for selection
SCORE_FLOOR = 0.1


def score_tiers(
    candidates: list[CandidateProduct],
    scores: dict[str, ProductScores],
    tier_map: dict[str, str],
) -> tuple[dict[str, float], dict[str, int]]:
    """Score each tier by the sum of its top-3 product scores.

    Tiers with fewer than 3 products are penalized proportionally.

    Returns:
        (tier_scores, tier_product_counts)
    """
    # Group candidates by tier
    tier_groups: dict[str, list[float]] = {t: [] for t in TIER_ORDER}

    for c in candidates:
        tier = tier_map.get(c.name)
        if tier in tier_groups:
            s = scores.get(c.name, ProductScores(product_name=c.name))
            tier_groups[tier].append(s.total_score)

    tier_scores: dict[str, float] = {}
    tier_counts: dict[str, int] = {}

    for tier in TIER_ORDER:
        product_scores = sorted(tier_groups[tier], reverse=True)
        tier_counts[tier] = len(product_scores)
        top3 = product_scores[:3]

        if len(top3) == 0:
            tier_scores[tier] = 0.0
        else:
            raw_sum = sum(top3)
            # Penalty for fewer than 3 products
            penalty = len(top3) / 3
            tier_scores[tier] = raw_sum * penalty

    return tier_scores, tier_counts


def select_winning_tier(tier_scores: dict[str, float]) -> str:
    """Select the tier with the highest aggregate score.

    Ties broken by TIER_ORDER priority (premium > mid > budget).
    """
    best_tier = TIER_ORDER[0]
    best_score = tier_scores.get(best_tier, 0.0)

    for tier in TIER_ORDER[1:]:
        score = tier_scores.get(tier, 0.0)
        if score > best_score:
            best_tier = tier
            best_score = score

    return best_tier


class SlotSelector:
    """Single-tier product selector.

    Algorithm:
    1. Score each tier by aggregate of top-3 scores
    2. Select the winning tier
    3. Filter out candidates below score floor (0.1)
    4. Pick top 3 from winning tier by score (no brand constraint)
    5. Fallback: pull from adjacent tier if insufficient eligible candidates
    6. Brand mix: if all 3 are same brand, replace rank 3 with best other-brand
    """

    def select(
        self,
        candidates: list[CandidateProduct],
        scores: dict[str, ProductScores],
        tier_map: dict[str, str],
        top_n: int = 3,
        force_tier: str = "",
    ) -> tuple[list[SelectedProduct], str, dict[str, float], dict[str, int]]:
        """Select products from the winning tier.

        Args:
            candidates: All candidate products
            scores: Product name -> ProductScores mapping
            tier_map: Product name -> tier mapping ("premium"|"mid"|"budget")
            top_n: Number of products to select (default 3)
            force_tier: Override tier selection ("premium"|"mid"|"budget").
                        Empty string = auto-select winning tier (default).

        Returns:
            Tuple of (picks, winning_tier, tier_scores, tier_product_counts)

        Raises:
            ValueError: If fewer than top_n candidates available
        """
        if len(candidates) < top_n:
            raise ValueError(
                f"Need at least {top_n} candidates, got {len(candidates)}"
            )

        # Score tiers and select winner
        tier_scores, tier_counts = score_tiers(candidates, scores, tier_map)

        if force_tier and force_tier in TIER_ORDER:
            winning_tier = force_tier
            logger.info(
                "Tier scores: %s → forced tier: %s",
                {t: round(s, 3) for t, s in tier_scores.items()},
                winning_tier,
            )
        else:
            winning_tier = select_winning_tier(tier_scores)
            logger.info(
                "Tier scores: %s → winning tier: %s",
                {t: round(s, 3) for t, s in tier_scores.items()},
                winning_tier,
            )

        # Group candidates by tier, sorted by score descending
        tier_groups: dict[str, list[CandidateProduct]] = {t: [] for t in TIER_ORDER}
        for c in candidates:
            tier = tier_map.get(c.name)
            if tier in tier_groups:
                tier_groups[tier].append(c)

        for tier in tier_groups:
            tier_groups[tier].sort(
                key=lambda c: scores.get(
                    c.name, ProductScores(product_name=c.name)
                ).total_score,
                reverse=True,
            )

        # Pick top-N from winning tier (score floor applied, no brand constraint)
        picks = self._pick_from_tier(
            tier_groups[winning_tier],
            winning_tier,
            scores,
            tier_scores,
            top_n,
        )

        # Not enough? Pull from adjacent tier (also with score floor)
        if len(picks) < top_n:
            picks = self._pull_from_adjacent(
                picks,
                tier_groups,
                winning_tier,
                scores,
                tier_scores,
                top_n,
            )

        # Brand mix: if all picks share the same manufacturer,
        # replace rank 3 (lowest score) with the best other-brand candidate
        if len(picks) >= top_n:
            picks = self._enforce_brand_mix(
                picks,
                tier_groups,
                winning_tier,
                scores,
                tier_scores,
            )

        # Assign ranks 1..N
        for i, p in enumerate(picks):
            p.rank = i + 1

        for p in picks:
            logger.info(
                "Pick #%d (%s): %s — score=%.3f",
                p.rank,
                p.candidate.manufacturer,
                p.candidate.name,
                p.scores.total_score,
            )

        return picks, winning_tier, tier_scores, tier_counts

    def _pick_from_tier(
        self,
        tier_candidates: list[CandidateProduct],
        tier: str,
        scores: dict[str, ProductScores],
        tier_scores: dict[str, float],
        top_n: int,
    ) -> list[SelectedProduct]:
        """Pick top products from tier by score (no brand constraint).

        Candidates with total_score < SCORE_FLOOR are excluded.
        """
        picks: list[SelectedProduct] = []

        # Filter by score floor
        eligible = [
            c for c in tier_candidates
            if scores.get(c.name, ProductScores(product_name=c.name)).total_score >= SCORE_FLOOR
        ]

        if len(eligible) < top_n:
            logger.warning(
                "Only %d candidates with score >= %.1f in tier '%s'. "
                "Consider expanding candidate pool.",
                len(eligible),
                SCORE_FLOOR,
                tier,
            )

        for c in eligible:
            if len(picks) >= top_n:
                break

            s = scores.get(c.name, ProductScores(product_name=c.name))
            reasons = _generate_reasons(c, s, tier, tier_scores)

            picks.append(SelectedProduct(
                rank=0,
                candidate=c,
                scores=s,
                selection_reasons=reasons,
                slot="",
            ))

        return picks

    def _enforce_brand_mix(
        self,
        picks: list[SelectedProduct],
        tier_groups: dict[str, list[CandidateProduct]],
        winning_tier: str,
        scores: dict[str, ProductScores],
        tier_scores: dict[str, float],
    ) -> list[SelectedProduct]:
        """Replace rank 3 if all picks share the same manufacturer.

        Searches winning tier first, then adjacent tiers for the
        highest-scoring candidate from a different brand.
        """
        manufacturers = {p.candidate.manufacturer for p in picks}
        if len(manufacturers) != 1:
            return picks  # already diverse

        dominant_brand = next(iter(manufacturers))
        picked_names = {p.candidate.name for p in picks}

        # Search order: winning tier first, then adjacent
        adjacent = {
            "premium": ["mid", "budget"],
            "mid": ["premium", "budget"],
            "budget": ["mid", "premium"],
        }
        search_tiers = [winning_tier] + adjacent[winning_tier]

        replacement: SelectedProduct | None = None
        for tier in search_tiers:
            for c in tier_groups[tier]:
                if c.name in picked_names:
                    continue
                if c.manufacturer == dominant_brand:
                    continue
                s = scores.get(c.name, ProductScores(product_name=c.name))
                if s.total_score < SCORE_FLOOR:
                    continue

                reasons = _generate_reasons(c, s, tier, tier_scores)
                reasons.append(
                    f"(brand mix: replaced same-brand rank 3 — "
                    f"all were {dominant_brand})"
                )
                replacement = SelectedProduct(
                    rank=0,
                    candidate=c,
                    scores=s,
                    selection_reasons=reasons,
                    slot="",
                )
                break
            if replacement:
                break

        if replacement:
            dropped = picks[-1]
            logger.info(
                "Brand mix: dropping %s (%s, score=%.3f), "
                "replacing with %s (%s, score=%.3f)",
                dropped.candidate.name,
                dropped.candidate.manufacturer,
                dropped.scores.total_score,
                replacement.candidate.name,
                replacement.candidate.manufacturer,
                replacement.scores.total_score,
            )
            picks = picks[:-1] + [replacement]
        else:
            logger.info(
                "Brand mix: all picks are %s but no eligible "
                "other-brand candidate found",
                dominant_brand,
            )

        return picks

    def _pull_from_adjacent(
        self,
        picks: list[SelectedProduct],
        tier_groups: dict[str, list[CandidateProduct]],
        winning_tier: str,
        scores: dict[str, ProductScores],
        tier_scores: dict[str, float],
        top_n: int,
    ) -> list[SelectedProduct]:
        """Pull from adjacent tiers when winning tier has insufficient candidates."""
        picked_names = {p.candidate.name for p in picks}

        # Adjacent tier order based on winning tier
        adjacent = {
            "premium": ["mid", "budget"],
            "mid": ["premium", "budget"],
            "budget": ["mid", "premium"],
        }

        for adj_tier in adjacent[winning_tier]:
            for c in tier_groups[adj_tier]:
                if len(picks) >= top_n:
                    break
                if c.name in picked_names:
                    continue

                s = scores.get(c.name, ProductScores(product_name=c.name))
                if s.total_score < SCORE_FLOOR:
                    continue

                reasons = _generate_reasons(c, s, adj_tier, tier_scores)
                reasons.append(
                    "(pulled from adjacent tier: insufficient candidates in winning tier)"
                )

                picks.append(SelectedProduct(
                    rank=0,
                    candidate=c,
                    scores=s,
                    selection_reasons=reasons,
                    slot="",
                ))
                picked_names.add(c.name)

            if len(picks) >= top_n:
                break

        return picks


def _generate_reasons(
    candidate: CandidateProduct,
    scores: ProductScores,
    tier: str,
    tier_scores: dict[str, float],
) -> list[str]:
    """Generate human-readable selection reasons."""
    reasons: list[str] = []

    # Winning tier context
    tier_score = tier_scores.get(tier, 0.0)
    reasons.append(f"Winning tier: {tier} (score {tier_score:.3f})")

    # Keyword metrics
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


# Backward compatibility alias
TopSelector = SlotSelector
