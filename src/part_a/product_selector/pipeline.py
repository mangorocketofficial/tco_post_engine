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
    SelectionResult,
    ValidationResult,
    extract_manufacturer,
)
from .naver_ad_client import NaverAdClient
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
    ) -> None:
        self.category_config = category_config
        self.config = config or Config()

    def run(self) -> SelectionResult:
        """Execute the pipeline.

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

        # Step 3: Score and select TOP 3
        logger.info("Step 3: Scoring and selecting TOP 3...")
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        selector = TopSelector()
        picks = selector.select(candidates, scores)

        # Step 4: Validate
        logger.info("Step 4: Validating...")
        validations = self._validate(picks)

        result = SelectionResult(
            category=keyword,
            selection_date=date.today(),
            data_sources={
                "candidates": "naver_shopping_api",
                "scoring": "naver_searchad_api",
            },
            candidate_pool_size=len(candidates),
            selected_products=picks,
            validation=validations,
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
    def _validate(picks: list) -> list[ValidationResult]:
        """Basic validation on selected products."""
        validations: list[ValidationResult] = []

        # Brand diversity check — use manufacturer, not product line
        manufacturers = [p.candidate.manufacturer for p in picks]
        unique_mfrs = set(manufacturers)
        validations.append(ValidationResult(
            check_name="brand_diversity",
            passed=len(unique_mfrs) == len(manufacturers),
            detail=f"{len(unique_mfrs)} unique manufacturers: {', '.join(unique_mfrs)}",
        ))

        # Keyword data check
        has_metrics = sum(
            1 for p in picks if p.candidate.keyword_metrics
            and p.candidate.keyword_metrics.monthly_clicks > 0
        )
        validations.append(ValidationResult(
            check_name="keyword_data",
            passed=has_metrics >= 1,
            detail=f"{has_metrics}/{len(picks)} products have keyword metrics",
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
