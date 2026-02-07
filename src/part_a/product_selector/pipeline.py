"""End-to-end product selection pipeline.

Orchestrates: data collection → aggregation → enrichment → scoring →
slot assignment → validation → output.

Usage:
    pipeline = ProductSelectionPipeline(category_config)
    result = pipeline.run()
    print(result.to_json())
"""

from __future__ import annotations

import json
import logging
from datetime import date

from ..common.config import Config
from ..database.connection import get_connection
from .candidate_aggregator import CandidateAggregator
from .category_config import CategoryConfig
from .models import CandidateProduct, SelectionResult
from .price_classifier import PriceClassifier
from .resale_quick_checker import ResaleQuickChecker
from .sales_ranking_scraper import (
    CoupangRankingScraper,
    DanawaRankingScraper,
    NaverShoppingRankingScraper,
)
from .scorer import ProductScorer
from .search_interest_scraper import NaverDataLabScraper
from .sentiment_scraper import SentimentScraper
from .slot_selector import SlotSelector
from .validator import SelectionValidator

logger = logging.getLogger(__name__)


class ProductSelectionPipeline:
    """End-to-end product selection pipeline.

    Steps:
    1. Collect sales rankings from 3 platforms
    2. Aggregate into candidate pool (presence >= 2)
    3. Collect search interest for candidates
    4. Collect community sentiment for candidates
    5. Classify price tiers
    6. Quick resale check
    7. Score all candidates
    8. Assign to 3 slots
    9. Validate and fix if needed
    10. Build SelectionResult

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
        """Execute the full pipeline.

        Returns:
            SelectionResult with selected products and validation.
        """
        keyword = self.category_config.search_terms[0] if self.category_config.search_terms else ""
        logger.info("=== Product Selection Pipeline: %s ===", keyword)

        # Step 1: Collect sales rankings
        logger.info("Step 1: Collecting sales rankings...")
        naver, danawa, coupang = self._collect_sales_rankings(keyword)

        # Step 2: Aggregate into candidate pool
        logger.info("Step 2: Aggregating candidates...")
        active_sources = sum(1 for src in (naver, danawa, coupang) if src)
        min_presence = min(2, active_sources)  # need ≥2 platforms, but relax if only 1 source
        aggregator = CandidateAggregator()
        candidates = aggregator.aggregate(
            naver, danawa, coupang,
            category=keyword,
            min_presence=min_presence,
        )
        logger.info("Candidate pool: %d products", len(candidates))

        if len(candidates) < 3:
            raise ValueError(
                f"Only {len(candidates)} candidates found (need >= 3). "
                "Try broader search terms or lower min_presence."
            )

        # Steps 3-6: Enrichment (each step is optional — failures don't stop the pipeline)
        for step_num, step_name, step_fn in [
            (3, "search interest", self._collect_search_interest),
            (4, "community sentiment", self._collect_sentiment),
            (5, "price tiers", self._classify_prices),
            (6, "resale quick-check", self._check_resale),
        ]:
            logger.info("Step %d: Collecting %s...", step_num, step_name)
            try:
                step_fn(candidates)
            except Exception:
                logger.warning(
                    "Step %d (%s) failed, continuing without it",
                    step_num, step_name, exc_info=True,
                )

        # Step 7: Score candidates
        logger.info("Step 7: Scoring candidates...")
        scorer = ProductScorer()
        scores = scorer.score_candidates(candidates)

        # Step 8: Assign to 3 slots
        logger.info("Step 8: Assigning to slots...")
        selector = SlotSelector()
        assignments = selector.select(candidates, scores)

        # Step 9: Validate and fix
        logger.info("Step 9: Validating selection...")
        validator = SelectionValidator(self.category_config)
        assignments, validations = validator.validate_and_fix(
            assignments, candidates, scores
        )

        # Step 10: Build result
        result = SelectionResult(
            category=keyword,
            selection_date=date.today(),
            data_sources={
                "sales_rankings": ["naver_shopping", "danawa", "coupang"],
                "search_volume": "naver_datalab",
                "community_sentiment": ["ppomppu", "clien", "naver_cafe"],
                "price_data": "danawa",
                "resale_check": "danggeun",
            },
            candidate_pool_size=len(candidates),
            selected_products=assignments,
            validation=validations,
        )

        logger.info("=== Pipeline complete ===")
        return result

    def _collect_sales_rankings(self, keyword: str) -> tuple[list, list, list]:
        """Collect from Naver, Danawa, Coupang.

        Each scraper failure is caught gracefully — the pipeline
        continues with whichever sources succeed.
        """
        # Naver Shopping (API)
        try:
            with NaverShoppingRankingScraper(self.config) as scraper:
                naver = scraper.get_best_products(keyword)
        except Exception:
            logger.warning("Naver Shopping scraper failed, continuing without it", exc_info=True)
            naver = []

        # Danawa
        danawa_code = self.category_config.danawa_category_code
        if danawa_code:
            try:
                with DanawaRankingScraper(self.config) as scraper:
                    danawa = scraper.get_popular_products(danawa_code)
            except Exception:
                logger.warning("Danawa scraper failed, continuing without it", exc_info=True)
                danawa = []
        else:
            danawa = []
            logger.warning("No Danawa category code configured, skipping")

        # Coupang
        try:
            with CoupangRankingScraper(self.config) as scraper:
                coupang = scraper.get_best_sellers(keyword)
        except Exception:
            logger.warning("Coupang scraper failed, continuing without it", exc_info=True)
            coupang = []

        total = len(naver) + len(danawa) + len(coupang)
        if total == 0:
            raise RuntimeError(
                "All sales ranking scrapers failed. "
                "Check API keys (NAVER_DATALAB_CLIENT_ID/SECRET) and network."
            )

        return naver, danawa, coupang

    def _collect_search_interest(
        self, candidates: list[CandidateProduct]
    ) -> None:
        """Populate search_interest on each candidate (in-place)."""
        names = [c.name for c in candidates]
        with NaverDataLabScraper(self.config) as scraper:
            interests = scraper.get_search_interest(names)

        interest_map = {si.product_name: si for si in interests}
        for c in candidates:
            c.search_interest = interest_map.get(c.name)

    def _collect_sentiment(
        self, candidates: list[CandidateProduct]
    ) -> None:
        """Populate sentiment on each candidate (in-place)."""
        names = [c.name for c in candidates]
        with SentimentScraper(self.config) as scraper:
            sentiments = scraper.get_sentiment_batch(
                names,
                negative_keywords=self.category_config.negative_keywords,
                positive_keywords=self.category_config.positive_keywords,
            )

        sentiment_map = {s.product_name: s for s in sentiments}
        for c in candidates:
            c.sentiment = sentiment_map.get(c.name)

    def _classify_prices(
        self, candidates: list[CandidateProduct]
    ) -> None:
        """Populate price_position on each candidate (in-place)."""
        classifier = PriceClassifier()
        positions = classifier.classify_candidates(candidates)

        position_map = {p.product_name: p for p in positions}
        for c in candidates:
            c.price_position = position_map.get(c.name)

    def _check_resale(
        self, candidates: list[CandidateProduct]
    ) -> None:
        """Populate resale_check on each candidate (in-place)."""
        with ResaleQuickChecker(self.config) as checker:
            checks = checker.check_resale_batch(candidates)

        check_map = {r.product_name: r for r in checks}
        for c in candidates:
            c.resale_check = check_map.get(c.name)

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
