"""Cross-platform candidate aggregation for product selection.

Merges sales rankings from Naver Shopping, Danawa, and Coupang into
a deduplicated candidate pool. Products appearing on fewer than 2
platforms are excluded.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

from .models import CandidateProduct, SalesRankingEntry

logger = logging.getLogger(__name__)


class CandidateAggregator:
    """Aggregates sales rankings from 3 platforms into a unified candidate pool.

    Uses fuzzy product name matching to handle naming variations across
    platforms (e.g., "로보락 S8 Pro Ultra" vs "Roborock S8 Pro Ultra").

    Usage:
        aggregator = CandidateAggregator()
        candidates = aggregator.aggregate(naver, danawa, coupang, category="로봇청소기")
    """

    MATCH_THRESHOLD = 0.65

    def aggregate(
        self,
        naver_rankings: list[SalesRankingEntry],
        danawa_rankings: list[SalesRankingEntry],
        coupang_rankings: list[SalesRankingEntry],
        category: str = "",
        min_presence: int = 2,
    ) -> list[CandidateProduct]:
        """Merge rankings into deduplicated CandidateProduct list.

        Args:
            naver_rankings: Rankings from Naver Shopping.
            danawa_rankings: Rankings from Danawa.
            coupang_rankings: Rankings from Coupang.
            category: Product category name.
            min_presence: Minimum number of platforms a product must appear on.

        Returns:
            List of CandidateProduct with presence_score >= min_presence,
            sorted by avg_rank ascending.
        """
        all_rankings = naver_rankings + danawa_rankings + coupang_rankings

        # Group rankings by matched product name
        groups: dict[str, list[SalesRankingEntry]] = {}
        for entry in all_rankings:
            canonical = self._find_or_create_group(groups, entry.product_name)
            groups[canonical].append(entry)

        # Build CandidateProduct for each group
        candidates: list[CandidateProduct] = []
        for canonical_name, entries in groups.items():
            platforms = {e.platform for e in entries}
            presence_score = len(platforms)

            if presence_score < min_presence:
                continue

            # Average rank across platforms (lower is better)
            ranks = [e.rank for e in entries]
            avg_rank = sum(ranks) / len(ranks)

            # Best brand guess (most common non-empty)
            brands = [e.brand for e in entries if e.brand]
            brand = max(set(brands), key=brands.count) if brands else ""

            # Best product code (prefer danawa)
            product_code = ""
            for e in entries:
                if e.product_code:
                    if e.platform == "danawa" or not product_code:
                        product_code = e.product_code

            candidate = CandidateProduct(
                name=canonical_name,
                brand=brand,
                category=category,
                product_code=product_code,
                rankings=entries,
                presence_score=presence_score,
                avg_rank=avg_rank,
            )
            candidates.append(candidate)

        # Sort by avg_rank ascending (best rank first)
        candidates.sort(key=lambda c: c.avg_rank)

        logger.info(
            "Aggregated %d rankings → %d candidates (presence >= %d)",
            len(all_rankings),
            len(candidates),
            min_presence,
        )
        return candidates

    def _find_or_create_group(
        self,
        groups: dict[str, list[SalesRankingEntry]],
        product_name: str,
    ) -> str:
        """Find an existing group matching product_name, or create a new one.

        Returns the canonical group name.
        """
        normalized = self._normalize_product_name(product_name)

        for canonical in groups:
            canonical_normalized = self._normalize_product_name(canonical)
            if self._match_products(normalized, canonical_normalized):
                return canonical

        # No match found — create new group
        groups[product_name] = []
        return product_name

    @staticmethod
    def _normalize_product_name(name: str) -> str:
        """Normalize product name for cross-platform matching.

        Strips whitespace, lowercases, removes common category suffixes.
        """
        name = name.strip().lower()
        # Remove common suffixes that platforms append
        suffixes = [
            "로봇청소기", "물걸레로봇", "로봇물걸레", "청소기",
            "공기청정기", "건조기", "식기세척기",
        ]
        for suffix in suffixes:
            name = name.replace(suffix, "")
        # Normalize whitespace
        name = re.sub(r"\s+", " ", name).strip()
        return name

    @staticmethod
    def _match_products(name_a: str, name_b: str) -> bool:
        """Fuzzy match two normalized product names.

        Uses SequenceMatcher ratio with a threshold.
        Also handles exact substring matching for short vs long names.
        """
        if not name_a or not name_b:
            return False

        # Exact match
        if name_a == name_b:
            return True

        # Substring match (one contains the other)
        if name_a in name_b or name_b in name_a:
            return True

        # Fuzzy match
        ratio = SequenceMatcher(None, name_a, name_b).ratio()
        return ratio >= CandidateAggregator.MATCH_THRESHOLD
