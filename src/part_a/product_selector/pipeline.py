"""Product selection pipeline.

Simplified 4-step pipeline:
1. Naver Shopping API → candidate product list
2. Naver Search Ad API → keyword metrics per product
3. Score & rank → TOP 3 by affiliate value
4. Validate (brand diversity)

Usage:
    pipeline = ProductSelectionPipeline(category_config)
    result = pipeline.run()
    print(result.to_json())
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import date

from ..common.config import Config
from ..database.connection import get_connection
from .category_config import CategoryConfig
from .models import (
    CandidateProduct,
    KeywordMetrics,
    ProductScores,
    RecommendationResult,
    SelectedProduct,
    SelectionResult,
    ValidationResult,
    extract_manufacturer,
)
from .naver_ad_client import NaverAdClient
from .price_classifier import PriceClassifier
from .sales_ranking_scraper import NaverShoppingRankingScraper
from .scorer import ProductScorer
from .slot_selector import TopSelector

logger = logging.getLogger(__name__)


class ProductSelectionPipeline:
    """Product selection pipeline.

    Steps:
    1. Discover candidates via Naver Shopping API
    2. Fetch keyword metrics via Naver Search Ad API
    3. Score and select TOP 3
    4. Validate

    Usage:
        pipeline = ProductSelectionPipeline(category_config)
        result = pipeline.run()
    """

    def __init__(
        self,
        category_config: CategoryConfig,
        config: Config | None = None,
        recommendation_result: RecommendationResult | None = None,
    ) -> None:
        self.category_config = category_config
        self.config = config or Config()
        self.recommendation_result = recommendation_result

    def run(self, force_tier: str = "") -> SelectionResult:
        """Execute the pipeline.

        Args:
            force_tier: Override tier selection ("premium"|"mid"|"budget").
                        Empty string = auto-select winning tier (default).

        Returns:
            SelectionResult with selected products and validation.
        """
        keyword = (
            self.category_config.search_terms[0]
            if self.category_config.search_terms
            else ""
        )
        logger.info("=== Product Selection Pipeline: %s ===", keyword)

        # Step 1: Discover candidates from Naver Shopping
        logger.info("Step 1: Discovering candidates from Naver Shopping...")
        candidates = self._discover_candidates(keyword)
        logger.info("Found %d candidates", len(candidates))

        if len(candidates) < 3:
            raise ValueError(
                f"Only {len(candidates)} candidates found (need >= 3). "
                "Check Naver API keys or try broader search terms."
            )

        # Step 2: Fetch keyword metrics
        logger.info("Step 2: Fetching keyword metrics from Naver Search Ad...")
        self._fetch_keyword_metrics(candidates)

        # Step 2.5: Score candidates
        logger.info("Step 2.5: Scoring candidates...")
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        # Step 2.7: Apply blog recommendation score bonus
        if self.recommendation_result and self.recommendation_result.top_products:
            logger.info("Step 2.7: Applying blog recommendation bonus...")
            from .final_selector import match_product

            for candidate in candidates:
                for mention in self.recommendation_result.top_products:
                    # Create minimal SelectedProduct wrapper for match_product
                    temp_selected = SelectedProduct(
                        rank=0,
                        candidate=candidate,
                        scores=ProductScores(product_name=candidate.name),
                    )
                    is_match, _ = match_product(temp_selected, mention)
                    if is_match:
                        old_score = scores[candidate.name].total_score
                        # Bonus: +0.05 per mention, capped at +0.25
                        bonus = min(0.05 * mention.mention_count, 0.25)
                        # Apply bonus by scaling score components proportionally
                        scale = (old_score + bonus) / max(old_score, 0.01)

                        s = scores[candidate.name]
                        scores[candidate.name] = ProductScores(
                            product_name=s.product_name,
                            clicks_score=s.clicks_score * scale,
                            cpc_score=s.cpc_score * scale,
                            search_volume_score=s.search_volume_score * scale,
                            competition_score=s.competition_score * scale,
                        )
                        logger.info(
                            "Blog bonus applied: %s (+%.3f → %.3f)",
                            candidate.name,
                            old_score,
                            scores[candidate.name].total_score,
                        )
                        break

        # Step 3: Classify candidates into price tiers
        logger.info("Step 3: Classifying products into price tiers...")
        classifier = PriceClassifier()
        price_positions = classifier.classify_candidates(candidates)
        tier_map = {pos.product_name: pos.price_tier for pos in price_positions}
        logger.info(
            "Tier distribution: %s",
            {
                tier: sum(1 for t in tier_map.values() if t == tier)
                for tier in ["premium", "mid", "budget"]
            },
        )

        # Step 4: Select TOP 3 from winning tier
        logger.info("Step 4: Selecting TOP 3 from winning tier...")
        selector = TopSelector()
        picks, winning_tier, tier_scores, tier_counts = selector.select(
            candidates, scores, tier_map, force_tier=force_tier
        )
        logger.info(
            "Winning tier: %s (score %.3f)",
            winning_tier,
            tier_scores.get(winning_tier, 0.0),
        )

        # Step 4.5: Build runner-ups (rank 4-6) for fallback pool
        picked_names = {p.candidate.name for p in picks}
        runner_ups: list[SelectedProduct] = []
        adj_order = {
            "premium": ["mid", "budget"],
            "mid": ["premium", "budget"],
            "budget": ["mid", "premium"],
        }
        search_tiers = [winning_tier] + adj_order.get(winning_tier, [])
        for tier in search_tiers:
            tier_candidates = sorted(
                [c for c in candidates if tier_map.get(c.name) == tier],
                key=lambda c: scores.get(
                    c.name, ProductScores(product_name=c.name)
                ).total_score,
                reverse=True,
            )
            for c in tier_candidates:
                if c.name in picked_names:
                    continue
                s = scores.get(c.name, ProductScores(product_name=c.name))
                if s.total_score < 0.1:
                    continue
                runner_ups.append(SelectedProduct(
                    rank=len(picks) + len(runner_ups) + 1,
                    candidate=c,
                    scores=s,
                    selection_reasons=[f"Runner-up from tier '{tier}'"],
                    slot="",
                ))
                if len(runner_ups) >= 3:
                    break
            if len(runner_ups) >= 3:
                break

        # Re-sort and re-rank runner-ups by score
        runner_ups.sort(key=lambda x: x.scores.total_score, reverse=True)
        for i, ru in enumerate(runner_ups):
            ru.rank = len(picks) + i + 1

        logger.info("Runner-ups: %d candidates", len(runner_ups))
        for ru in runner_ups:
            logger.info(
                "  #%d: %s (%s) — score=%.3f",
                ru.rank, ru.candidate.name, ru.candidate.brand,
                ru.scores.total_score,
            )

        # Step 5: Validate
        logger.info("Step 5: Validating...")
        validations = self._validate(picks, tier_map, winning_tier, tier_counts)

        result = SelectionResult(
            category=keyword,
            selection_date=date.today(),
            data_sources={
                "candidates": "naver_shopping_api",
                "scoring": "naver_searchad_api",
            },
            candidate_pool_size=len(candidates),
            selected_products=picks,
            runner_ups=runner_ups,
            validation=validations,
            selected_tier=winning_tier,
            tier_scores=tier_scores,
            tier_product_counts=tier_counts,
        )

        logger.info("=== Pipeline complete ===")
        return result

    def _discover_candidates(self, keyword: str) -> list[CandidateProduct]:
        """Get candidate products from Naver Shopping API."""
        try:
            with NaverShoppingRankingScraper(self.config) as scraper:
                entries = scraper.get_best_products(keyword)
        except Exception:
            logger.error("Naver Shopping API failed", exc_info=True)
            raise RuntimeError(
                "Failed to fetch candidates from Naver Shopping. "
                "Check API keys (NAVER_CLIENT_ID / NAVER_CLIENT_SECRET)."
            )

        if not entries:
            raise RuntimeError(
                f"No products found for '{keyword}' on Naver Shopping."
            )

        candidates: list[CandidateProduct] = []
        for entry in entries:
            candidates.append(CandidateProduct(
                name=entry.product_name,
                brand=entry.brand,
                category=keyword,
                product_code=entry.product_code,
                rankings=[entry],
                price=entry.price,
                naver_rank=entry.rank,
            ))

        return candidates

    def _fetch_keyword_metrics(
        self, candidates: list[CandidateProduct]
    ) -> None:
        """Populate keyword_metrics on each candidate (in-place).

        Builds brand-level keywords (manufacturer + product line) and
        shares metrics across candidates with the same keyword.
        """
        client = NaverAdClient(self.config)

        # Group candidates by brand-level keyword
        keyword_groups: dict[str, list[CandidateProduct]] = {}
        for c in candidates:
            kw = _build_product_keyword(c.name, c.brand)
            if kw:
                keyword_groups.setdefault(kw, []).append(c)

        unique_keywords = list(keyword_groups.keys())
        if not unique_keywords:
            return

        logger.info(
            "Querying %d unique keywords: %s",
            len(unique_keywords), unique_keywords,
        )

        try:
            metrics_list = client.get_keyword_metrics(unique_keywords)
        except Exception:
            logger.warning(
                "Naver Search Ad API failed, continuing with empty metrics",
                exc_info=True,
            )
            return

        # Map keyword → metrics
        metrics_map = {m.product_name: m for m in metrics_list}

        # Assign shared metrics to all candidates with the same keyword
        for kw, cands in keyword_groups.items():
            m = metrics_map.get(kw)
            if m and m.monthly_clicks > 0:
                for c in cands:
                    c.keyword_metrics = dataclasses.replace(
                        m, product_name=c.name
                    )

    @staticmethod
    def _validate(
        picks: list,
        tier_map: dict[str, str],
        winning_tier: str = "",
        tier_counts: dict[str, int] | None = None,
    ) -> list[ValidationResult]:
        """Basic validation on selected products."""
        validations: list[ValidationResult] = []

        # Brand variety — informational only (no hard constraint)
        brands = [p.candidate.manufacturer for p in picks]
        n_unique = len(set(brands))
        validations.append(ValidationResult(
            check_name="brand_variety",
            passed=True,  # always passes — informational only
            detail=f"Selected brands: {', '.join(brands)} ({n_unique} unique)",
        ))

        # Score floor check — all selected products should have score >= 0.1
        all_above_floor = all(
            p.scores.total_score >= 0.1 for p in picks
        )
        validations.append(ValidationResult(
            check_name="keyword_data",
            passed=all_above_floor,
            detail=(
                f"{'All' if all_above_floor else 'Not all'} "
                f"{len(picks)} products have total_score >= 0.1"
            ),
        ))

        # Tier depth check — winning tier should have at least 3 candidates
        if winning_tier and tier_counts:
            n = tier_counts.get(winning_tier, 0)
            validations.append(ValidationResult(
                check_name="tier_depth",
                passed=n >= 3,
                detail=f"Winning tier '{winning_tier}' has {n} candidates (minimum 3)",
            ))

        return validations

    def save_to_db(self, result: SelectionResult) -> None:
        """Save selection result to product_selections table."""
        conn = get_connection(self.config)
        try:
            conn.execute(
                """
                INSERT INTO product_selections
                (category, selection_date, candidate_pool_size, result_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    result.category,
                    result.selection_date.isoformat(),
                    result.candidate_pool_size,
                    result.to_json(),
                ),
            )
            conn.commit()
            logger.info("Saved selection result to database")
        finally:
            conn.close()


def _build_product_keyword(product_name: str, brand: str) -> str:
    """Build API keyword from manufacturer + product line (brand).

    Uses the brand field from Naver Shopping API (product line name)
    combined with the manufacturer prefix extracted from the product name.

    Returns empty string when the keyword would be too generic
    (e.g., brand == manufacturer → just "삼성" or "LG").

    Examples:
        ("삼성전자 그랑데 WF19T6000KW 화이트", "그랑데") → "삼성그랑데"
        ("LG전자 트롬 오브제 FX25ESR", "트롬") → "LG트롬"
        ("삼성전자 비스포크AI콤보 25/18kg", "비스포크AI콤보") → "삼성비스포크AI콤보"
        ("삼성전자 삼성 WF21DG6650B", "삼성") → "" (too generic)
    """
    manufacturer = extract_manufacturer(product_name)
    if brand:
        # Skip if brand is just the manufacturer name — keyword would be
        # too generic (e.g., "삼성" matches all Samsung searches)
        if brand == manufacturer:
            return ""
        # Avoid duplication: "삼성" + "삼성비스포크" → "삼성비스포크"
        if manufacturer and brand.startswith(manufacturer):
            keyword = brand.replace(" ", "")
        else:
            keyword = f"{manufacturer}{brand}".replace(" ", "")
    elif manufacturer:
        # No brand at all — manufacturer-only keyword is too generic
        return ""
    else:
        keyword = ""
    return keyword
