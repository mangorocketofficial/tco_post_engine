"""Final product selector — merges A-0 and A-0.1 results into Top 3.

Merge logic (3-Case):
  Default:    V1 not in {A1, A2}           → [A1, A2, V1]
  Overlap-1:  V1 in {A1,A2}, V2 not        → [A1, A2, V2]
  Overlap-2:  V1 and V2 both in {A1,A2}    → [A1, A3, A2]
"""

from __future__ import annotations

import logging
import re
from datetime import date

from .models import (
    FinalProduct,
    FinalSelectionResult,
    ProductMention,
    RecommendationResult,
    SelectedProduct,
    SelectionResult,
)
from .recommendation_pipeline import RecommendationPipeline

logger = logging.getLogger(__name__)

# Reuse static helpers from RecommendationPipeline
_extract_model_code = RecommendationPipeline._extract_model_code
_normalize_name = RecommendationPipeline._normalize_name


def _extract_model_tokens(name: str) -> list[str]:
    """Extract ALL potential model code tokens (4+ chars, letters+digits) from a name.

    Unlike _extract_model_code (which returns only the first 5+ char token),
    this returns all 4+ char tokens — enabling prefix matching for cases
    where Naver Shopping truncates model codes (e.g., "RP13" vs "RP13C1022S9").
    """
    if not name:
        return []
    tokens = re.findall(r"[A-Za-z0-9](?:[A-Za-z0-9\-]{2,}[A-Za-z0-9])", name)
    result: list[str] = []
    for token in tokens:
        clean = token.replace("-", "").upper()
        has_letter = any(c.isalpha() for c in clean)
        has_digit = any(c.isdigit() for c in clean)
        if has_letter and has_digit and len(clean) >= 4:
            result.append(clean)
    return result


# ------------------------------------------------------------------
# Product matching
# ------------------------------------------------------------------


def match_product(
    selected: SelectedProduct,
    mention: ProductMention,
) -> tuple[bool, str]:
    """Check if an A-0 SelectedProduct matches an A-0.1 ProductMention.

    Strategy:
      1. Extract model code from both product names → exact match.
      2. Extract all model tokens (4+ chars) → prefix match.
         Handles truncated codes from Naver Shopping (e.g., "RP13" vs "RP13C1022S9").
      3. Fallback: substring match on normalized names.

    Returns:
        (is_match, match_method) — method is
        "model_code" | "model_code_prefix" | "substring" | "none"
    """
    a0_name = selected.candidate.name
    a0_code = _extract_model_code(a0_name)
    v_code = _extract_model_code(mention.product_name)

    # 1) Exact model code match
    if a0_code and v_code and a0_code == v_code:
        return True, "model_code"

    # Also check against mention.normalized_name (which is the model code
    # when one was found during A-0.1 processing)
    if a0_code and mention.normalized_name.upper() == a0_code:
        return True, "model_code"

    # 2) Prefix model code match — handles truncated codes from Naver Shopping
    a0_tokens = _extract_model_tokens(a0_name)
    v_tokens = _extract_model_tokens(mention.product_name)

    # Also include mention.normalized_name if it looks like a model code
    if mention.normalized_name:
        v_norm_upper = mention.normalized_name.upper().replace("-", "")
        if v_norm_upper and v_norm_upper not in v_tokens:
            has_letter = any(c.isalpha() for c in v_norm_upper)
            has_digit = any(c.isdigit() for c in v_norm_upper)
            if has_letter and has_digit and len(v_norm_upper) >= 4:
                v_tokens.append(v_norm_upper)

    for a_tok in a0_tokens:
        for v_tok in v_tokens:
            shorter, longer = (a_tok, v_tok) if len(a_tok) <= len(v_tok) else (v_tok, a_tok)
            if len(shorter) >= 4 and longer.startswith(shorter):
                return True, "model_code_prefix"

    # 3) Substring fallback on normalized names
    a0_norm = _normalize_name(a0_name)
    v_norm = _normalize_name(mention.product_name)

    if a0_norm and v_norm and len(v_norm) >= 5:
        if v_norm in a0_norm or a0_norm in v_norm:
            return True, "substring"

    return False, "none"


def find_overlaps(
    a0_products: list[SelectedProduct],
    a0_1_products: list[ProductMention],
) -> dict[int, tuple[int, str]]:
    """Find which A-0.1 products overlap with A-0 products.

    Returns:
        Dict mapping a0_1 index → (a0 index, match_method).
        Only the first matching A-0 product is recorded for each A-0.1 product.
    """
    overlaps: dict[int, tuple[int, str]] = {}

    for vi, mention in enumerate(a0_1_products):
        for ai, selected in enumerate(a0_products):
            is_match, method = match_product(selected, mention)
            if is_match:
                overlaps[vi] = (ai, method)
                break  # First match is sufficient

    return overlaps


# ------------------------------------------------------------------
# FinalSelector
# ------------------------------------------------------------------


class FinalSelector:
    """Merges A-0 and A-0.1 results into a final Top 3."""

    def merge(
        self,
        a0_result: SelectionResult,
        a0_1_result: RecommendationResult,
    ) -> FinalSelectionResult:
        """Apply the 3-case merge logic.

        Args:
            a0_result: A-0 pipeline output (Top 3 by keyword metrics).
            a0_1_result: A-0.1 pipeline output (Top 2 by blog mentions).

        Returns:
            FinalSelectionResult with the merged Top 3.
        """
        a0_products = a0_result.selected_products  # [A1, A2, A3]
        v_products = a0_1_result.top_products       # [V1, V2] or fewer

        if len(a0_products) < 3:
            logger.warning("A-0 returned fewer than 3 products (%d)", len(a0_products))

        # Edge case: no recommendation results → pure A-0
        if not v_products:
            logger.info("No A-0.1 results — using pure A-0 Top 3")
            return self._build_result(
                a0_result, a0_1_result,
                picks=list(a0_products[:3]),
                gaseonbi_mention=None,
                merge_case="default",
                match_details=[{"note": "No A-0.1 results available"}],
            )

        # Find overlaps between V products and A-0 Top 2 (index 0, 1)
        a0_top2 = a0_products[:2]
        overlaps = find_overlaps(a0_top2, v_products)

        v1_overlaps = 0 in overlaps  # V1 overlaps with A1 or A2?
        v2_overlaps = 1 in overlaps if len(v_products) > 1 else False

        match_details: list[dict] = []
        for vi, (ai, method) in overlaps.items():
            match_details.append({
                "a0_1_rank": vi + 1,
                "a0_1_product": v_products[vi].product_name,
                "a0_rank": a0_products[ai].rank,
                "a0_product": a0_products[ai].candidate.name,
                "match_method": method,
            })

        # Apply merge logic
        if not v1_overlaps:
            # Default: [A1, A2, V1]
            logger.info("Merge case: Default — V1 not in {A1, A2}")
            return self._build_result(
                a0_result, a0_1_result,
                picks=[a0_products[0], a0_products[1]],
                gaseonbi_mention=v_products[0],
                merge_case="default",
                match_details=match_details,
            )

        if not v2_overlaps and len(v_products) > 1:
            # Overlap-1: [A1, A2, V2]
            logger.info("Merge case: Overlap-1 — V1 overlaps, using V2")
            # Annotate the overlapping A-0 product
            overlap_ai = overlaps[0][0]
            match_details.append({
                "note": f"A-0 #{a0_products[overlap_ai].rank} also matches blog recommendation #1",
            })
            return self._build_result(
                a0_result, a0_1_result,
                picks=[a0_products[0], a0_products[1]],
                gaseonbi_mention=v_products[1],
                merge_case="overlap_1",
                match_details=match_details,
            )

        # Overlap-2: [A1, A3, A2(=gaseonbi)]
        # Both V1 and V2 overlap with A1/A2 → A2 becomes gaseonbi slot, A3 promoted
        logger.info("Merge case: Overlap-2 — both V products in {A1, A2}")

        # Determine which V product is NOT A1 (to place in gaseonbi slot)
        gaseonbi_a0_idx = 1  # Default: A2 is the gaseonbi product

        if len(a0_products) >= 3:
            picks = [a0_products[0], a0_products[2]]  # A1, A3
        else:
            picks = [a0_products[0]]

        # Find which V matches A2 (to get the mention data for annotation)
        gaseonbi_v = None
        for vi, (ai, _) in overlaps.items():
            if ai == gaseonbi_a0_idx:
                gaseonbi_v = v_products[vi]
                break
        if gaseonbi_v is None and v_products:
            gaseonbi_v = v_products[0]

        match_details.append({
            "note": "Both blog recommendations match A-0 Top 2. A3 promoted, A2 → gaseonbi slot.",
        })

        return self._build_result(
            a0_result, a0_1_result,
            picks=picks,
            gaseonbi_mention=gaseonbi_v,
            gaseonbi_selected=a0_products[gaseonbi_a0_idx],
            merge_case="overlap_2",
            match_details=match_details,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_result(
        self,
        a0_result: SelectionResult,
        a0_1_result: RecommendationResult,
        *,
        picks: list[SelectedProduct],
        gaseonbi_mention: ProductMention | None,
        gaseonbi_selected: SelectedProduct | None = None,
        merge_case: str,
        match_details: list[dict],
    ) -> FinalSelectionResult:
        """Build the FinalSelectionResult from picks + gaseonbi product."""
        final_products: list[FinalProduct] = []

        # Add A-0 picks
        for i, sp in enumerate(picks):
            source = "a0"
            reasons = list(sp.selection_reasons)

            # Check if this A-0 product also appears in blog recommendations
            if a0_1_result.top_products:
                for mention in a0_1_result.top_products:
                    is_match, method = match_product(sp, mention)
                    if is_match:
                        source = "both"
                        reasons.append(
                            f"Also blog recommendation (mentioned {mention.mention_count} times)"
                        )
                        break

            final_products.append(FinalProduct(
                rank=i + 1,
                name=sp.candidate.name,
                brand=sp.candidate.brand,
                price=sp.candidate.price,
                source=source,
                selection_reasons=reasons,
                slot=sp.slot,  # Preserve slot from A0
                a0_rank=sp.rank,
                a0_scores=sp.scores,
            ))

        # Add gaseonbi product (3rd slot)
        if gaseonbi_mention is not None:
            if gaseonbi_selected is not None:
                # Overlap-2: the gaseonbi product is from A-0 (A2 demoted to slot 3)
                reasons = [
                    f"Blog recommendation (mentioned {gaseonbi_mention.mention_count} times)",
                    f"A-0 rank #{gaseonbi_selected.rank} (score {gaseonbi_selected.scores.total_score:.3f})",
                ]
                final_products.append(FinalProduct(
                    rank=len(final_products) + 1,
                    name=gaseonbi_selected.candidate.name,
                    brand=gaseonbi_selected.candidate.brand,
                    price=gaseonbi_selected.candidate.price,
                    source="both",
                    selection_reasons=reasons,
                    slot=gaseonbi_selected.slot,  # Preserve slot from A0
                    a0_rank=gaseonbi_selected.rank,
                    a0_scores=gaseonbi_selected.scores,
                    recommendation_mention_count=gaseonbi_mention.mention_count,
                    recommendation_normalized_name=gaseonbi_mention.normalized_name,
                    match_method="model_code",
                ))
            else:
                # Default / Overlap-1: pure A-0.1 product in slot 3
                # Heuristic: assign value slot by default for blog recommendations
                # (assumption: blog recommendations tend toward budget/value)
                assigned_slot = "value"
                reasons = [
                    f"Blog recommendation #1 (mentioned {gaseonbi_mention.mention_count} times)",
                    f"Assigned to {assigned_slot} slot (blog recommendation)",
                ]
                final_products.append(FinalProduct(
                    rank=len(final_products) + 1,
                    name=gaseonbi_mention.product_name,
                    brand="",
                    price=0,
                    source="a0.1",
                    selection_reasons=reasons,
                    slot=assigned_slot,
                    recommendation_mention_count=gaseonbi_mention.mention_count,
                    recommendation_normalized_name=gaseonbi_mention.normalized_name,
                ))

        return FinalSelectionResult(
            category=a0_result.category,
            selection_date=date.today(),
            merge_case=merge_case,
            a0_result=a0_result,
            a0_1_result=a0_1_result,
            final_products=final_products,
            match_details=match_details,
        )
