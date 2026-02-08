"""Recommendation pipeline orchestrator (A-0.1).

Orchestrates the full flow:
  1. Naver Blog API + Google SerpAPI search
  2. DeepSeek product name extraction
  3. Frequency counting → Top N selection
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter
from datetime import datetime

from .blog_recommendation_scraper import BlogRecommendationScraper
from .models import ProductMention, RecommendationResult
from .product_name_extractor import ProductNameExtractor

logger = logging.getLogger(__name__)


class RecommendationPipeline:
    """Find the most recommended products for a category keyword."""

    def __init__(
        self,
        *,
        serpapi_key: str | None = None,
        naver_client_id: str | None = None,
        naver_client_secret: str | None = None,
        deepseek_key: str | None = None,
    ):
        self._scraper = BlogRecommendationScraper(
            serpapi_key=serpapi_key,
            naver_client_id=naver_client_id,
            naver_client_secret=naver_client_secret,
        )
        self._extractor = ProductNameExtractor(api_key=deepseek_key)

    def run(
        self,
        keyword: str,
        *,
        top_n: int = 2,
        naver_count: int = 50,
        google_count: int = 50,
    ) -> RecommendationResult:
        """Execute the full recommendation pipeline.

        Args:
            keyword: Category keyword (e.g., "드럼세탁기").
            top_n: Number of top products to return.
            naver_count: Number of Naver blog results to fetch.
            google_count: Number of Google blog results to fetch.

        Returns:
            RecommendationResult with ranked product mentions.
        """
        search_query = f"가성비 {keyword}"
        logger.info("=== A-0.1 Recommendation Pipeline: '%s' ===", keyword)

        # Step 1: Collect blog search results
        logger.info("Step 1: Searching blogs (Naver API + Google SerpAPI)...")
        blogs = self._scraper.search_all(
            keyword,
            naver_count=naver_count,
            google_count=google_count,
        )

        if not blogs:
            logger.warning("No blog results found for '%s'", keyword)
            return RecommendationResult(
                keyword=keyword,
                search_query=search_query,
                total_blogs_searched=0,
                total_products_extracted=0,
                top_products=[],
                search_date=datetime.now().isoformat(),
            )

        # Step 2: Extract product names via DeepSeek
        logger.info("Step 2: Extracting product names via DeepSeek...")
        raw_mentions = self._extractor.extract_from_snippets(blogs, keyword)

        if not raw_mentions:
            logger.warning("No product names extracted for '%s'", keyword)
            return RecommendationResult(
                keyword=keyword,
                search_query=search_query,
                total_blogs_searched=len(blogs),
                total_products_extracted=0,
                top_products=[],
                search_date=datetime.now().isoformat(),
            )

        # Step 3: Count and rank
        logger.info("Step 3: Counting mentions and ranking...")
        top_products = self._count_and_rank(raw_mentions, top_n=top_n)

        result = RecommendationResult(
            keyword=keyword,
            search_query=search_query,
            total_blogs_searched=len(blogs),
            total_products_extracted=len(raw_mentions),
            top_products=top_products,
            search_date=datetime.now().isoformat(),
        )

        # Log summary
        logger.info("=== Results for '%s' ===", keyword)
        logger.info("Blogs searched: %d", result.total_blogs_searched)
        logger.info("Product names extracted: %d", result.total_products_extracted)
        for i, p in enumerate(result.top_products, 1):
            logger.info("  Top %d: %s (mentioned %d times)", i, p.product_name, p.mention_count)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _count_and_rank(
        self,
        raw_mentions: list[dict],
        *,
        top_n: int,
    ) -> list[ProductMention]:
        """Count product mentions using model-code-based grouping.

        Strategy:
          1. Extract model codes (e.g., WF19T6000KW) from product names.
          2. Group entries sharing the same model code.
          3. Entries without a model code fall back to normalized-name grouping.
          4. Merge into a unified ranking sorted by mention count.
        """
        # Phase 1: Separate entries with/without model codes
        model_groups: dict[str, list[dict]] = {}   # model_code → [mention, ...]
        no_model_entries: list[dict] = []

        for mention in raw_mentions:
            name = mention["product_name"]
            code = self._extract_model_code(name)
            if code:
                model_groups.setdefault(code, []).append(mention)
            else:
                no_model_entries.append(mention)

        # Phase 2: Build unified groups
        # Each group: key → (count, original_names Counter, source_links set)
        groups: dict[str, tuple[int, Counter[str], set[str]]] = {}

        # Model-code groups
        for code, mentions in model_groups.items():
            original_counter: Counter[str] = Counter()
            sources: set[str] = set()
            for m in mentions:
                original_counter[m["product_name"]] += 1
                sources.update(m.get("source_links", []))
            groups[code] = (len(mentions), original_counter, sources)

        # No-model fallback (normalized name grouping)
        for mention in no_model_entries:
            norm = self._normalize_name(mention["product_name"])
            if not norm:
                continue
            if norm not in groups:
                groups[norm] = (0, Counter(), set())
            count, orig_counter, src_set = groups[norm]
            orig_counter[mention["product_name"]] += 1
            src_set.update(mention.get("source_links", []))
            groups[norm] = (count + 1, orig_counter, src_set)

        # Log frequency distribution for debugging
        sorted_groups = sorted(groups.items(), key=lambda x: x[1][0], reverse=True)
        logger.info("--- Product groups (model-code based, %d groups) ---", len(groups))
        for key, (count, orig_counter, _) in sorted_groups[:20]:
            originals = orig_counter.most_common(3)
            orig_str = ", ".join(f"'{n}'x{c}" for n, c in originals)
            logger.info("  [%d] %s  ← %s", count, key, orig_str)

        # Phase 3: Build top N ProductMention list
        result: list[ProductMention] = []
        for key, (count, orig_counter, src_set) in sorted_groups[:top_n]:
            best_original = orig_counter.most_common(1)[0][0]
            result.append(ProductMention(
                product_name=best_original,
                normalized_name=key,
                mention_count=count,
                sources=sorted(src_set),
            ))

        return result

    @staticmethod
    def _extract_model_code(name: str) -> str:
        """Extract an alphanumeric model code from a product name.

        Model codes are 5+ char tokens containing both letters and digits,
        e.g., WF19T6000KW, F21VDSK, GR-B267CEB.

        Returns the uppercased model code, or empty string if none found.
        """
        if not name:
            return ""

        # Remove hyphens within potential model codes for matching,
        # but first try to find hyphenated patterns like GR-B267CEB
        tokens = re.findall(r"[A-Za-z0-9](?:[A-Za-z0-9\-]{3,}[A-Za-z0-9])", name)
        for token in tokens:
            clean = token.replace("-", "")
            has_letter = any(c.isalpha() for c in clean)
            has_digit = any(c.isdigit() for c in clean)
            if has_letter and has_digit and len(clean) >= 5:
                return clean.upper()

        return ""

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize a product name for deduplication (fallback for no-model entries).

        - NFKC unicode normalization
        - Lowercase
        - Collapse whitespace
        - Strip common suffixes (색상, 용량 variants)
        """
        if not name:
            return ""

        text = unicodedata.normalize("NFKC", name)
        text = text.lower().strip()
        # Remove color/capacity suffixes like "(화이트)", "[32kg]"
        text = re.sub(r"[\(\[（【][^)\]）】]*[\)\]）】]", "", text)
        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text
