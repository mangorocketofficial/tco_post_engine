"""Product name extractor using DeepSeek LLM (A-0.1).

Sends blog search result titles and snippets to DeepSeek in batches,
extracting specific product names (brand + model) mentioned as recommendations.
"""

from __future__ import annotations

import json
import logging
import os
import re

from openai import OpenAI

from .models import BlogSearchResult

logger = logging.getLogger(__name__)

_BATCH_SIZE = 5
_MODEL = "deepseek-chat"
_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class ProductNameExtractor:
    """Extract product names from blog snippets via DeepSeek API."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self._client: OpenAI | None = None
        if self._api_key:
            self._client = OpenAI(api_key=self._api_key, base_url=_DEEPSEEK_BASE_URL)
        else:
            logger.warning("DEEPSEEK_API_KEY not set — product name extraction disabled")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_from_snippets(
        self,
        snippets: list[BlogSearchResult],
        category_keyword: str,
    ) -> list[dict]:
        """Extract product names from blog snippets in batches.

        Returns a list of ``{"product_name": str, "source_link": str}`` dicts.
        """
        if not self._client or not snippets:
            return []

        all_mentions: list[dict] = []
        batches = [snippets[i : i + _BATCH_SIZE] for i in range(0, len(snippets), _BATCH_SIZE)]

        logger.info(
            "Extracting product names: %d snippets in %d batches",
            len(snippets),
            len(batches),
        )

        for batch_idx, batch in enumerate(batches):
            try:
                mentions = self._extract_batch(batch, category_keyword)
                all_mentions.extend(mentions)
                logger.debug("Batch %d/%d: extracted %d names", batch_idx + 1, len(batches), len(mentions))
            except Exception:
                logger.exception("DeepSeek batch %d/%d failed", batch_idx + 1, len(batches))

        logger.info("Total product names extracted: %d", len(all_mentions))
        return all_mentions

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extract_batch(
        self,
        batch: list[BlogSearchResult],
        category_keyword: str,
    ) -> list[dict]:
        """Call DeepSeek for a single batch and parse the response."""
        prompt = self._build_prompt(batch, category_keyword)

        response = self._client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": "You are a product name extraction assistant. Always respond with valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
        )

        raw = response.choices[0].message.content.strip()
        product_names = self._parse_response(raw)

        # Attach source links
        results: list[dict] = []
        source_links = [s.link for s in batch]
        for name in product_names:
            results.append({
                "product_name": name,
                "source_links": source_links,
            })

        return results

    def _build_prompt(self, batch: list[BlogSearchResult], keyword: str) -> str:
        """Build the extraction prompt for a batch of snippets."""
        snippet_text = ""
        for i, item in enumerate(batch, 1):
            snippet_text += f"\n[{i}] 제목: {item.title}\n    내용: {item.snippet}\n"

        return (
            f'다음은 "{keyword}" 관련 블로그 검색 결과입니다.\n'
            f"{snippet_text}\n"
            f"위 글에서 추천하는 구체적인 제품명(브랜드 + 모델명)을 추출해주세요.\n"
            f"규칙:\n"
            f"- 실제로 추천/긍정적으로 언급된 제품만 포함\n"
            f"- 브랜드명과 모델명을 함께 포함 (예: 'LG 트롬 오브제컬렉션 FX25KSR')\n"
            f"- 광고/비추천 제품은 제외\n"
            f"- JSON 배열로만 응답: [\"제품명1\", \"제품명2\", ...]\n"
            f"- 제품이 없으면 빈 배열 [] 반환"
        )

    def _parse_response(self, raw: str) -> list[str]:
        """Parse DeepSeek response into a list of product names."""
        # Try direct JSON parse first
        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return [str(item).strip() for item in result if str(item).strip()]
        except json.JSONDecodeError:
            pass

        # Fallback: extract JSON array from markdown code block
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list):
                    return [str(item).strip() for item in result if str(item).strip()]
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse DeepSeek response: %s", raw[:200])
        return []
