"""Naver Search Ad API client for keyword metrics.

Fetches monthly search volume, clicks, CPC, and competition level
for product keywords via the Naver Search Ad keyword tool.

API docs: https://searchad.naver.com/guide/api
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import time
from base64 import b64encode

import requests

from ..common.config import Config
from .models import KeywordMetrics

logger = logging.getLogger(__name__)

API_BASE = "https://api.searchad.naver.com"
KEYWORD_TOOL_PATH = "/keywordstool"


class NaverAdClient:
    """Client for Naver Search Ad keyword tool API.

    Usage:
        client = NaverAdClient(config)
        metrics = client.get_keyword_metrics(["LG 스탠바이미", "삼성 더 프레임"])
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self._customer_id = config.naver_searchad_customer_id
        self._api_key = config.naver_searchad_api_key
        self._secret_key = config.naver_searchad_secret_key

    @property
    def is_configured(self) -> bool:
        return bool(self._customer_id and self._api_key and self._secret_key)

    def get_keyword_metrics(
        self, keywords: list[str]
    ) -> list[KeywordMetrics]:
        """Fetch keyword metrics for a list of pre-cleaned keywords.

        Keywords should be short, space-free strings ready for the API.
        (e.g., "LG트롬", "삼성그랑데", "삼성비스포크AI콤보")

        Args:
            keywords: Short keywords to look up (no spaces).

        Returns:
            List of KeywordMetrics, one per keyword.
        """
        if not self.is_configured:
            logger.warning(
                "Naver Search Ad API not configured "
                "(NAVER_SEARCHAD_CUSTOMER_ID / API_KEY / SECRET_KEY). "
                "Returning empty metrics."
            )
            return [KeywordMetrics(product_name=kw) for kw in keywords]

        if not keywords:
            return []

        results: list[KeywordMetrics] = []

        # API accepts up to 5 keywords per request
        for i in range(0, len(keywords), 5):
            batch = keywords[i : i + 5]
            batch_results = self._fetch_batch(batch)
            results.extend(batch_results)

        # Fill in any keywords that weren't returned by the API
        found_names = {m.product_name for m in results}
        for kw in keywords:
            if kw not in found_names:
                results.append(KeywordMetrics(product_name=kw))

        return results

    def _fetch_batch(
        self,
        keywords: list[str],
    ) -> list[KeywordMetrics]:
        """Fetch metrics for a batch of up to 5 keywords."""
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(timestamp, "GET", KEYWORD_TOOL_PATH)

        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Timestamp": timestamp,
            "X-API-KEY": self._api_key,
            "X-Customer": self._customer_id,
            "X-Signature": signature,
        }

        params = {
            "hintKeywords": ",".join(keywords),
            "showDetail": "1",
        }

        try:
            resp = requests.get(
                f"{API_BASE}{KEYWORD_TOOL_PATH}",
                headers=headers,
                params=params,
                timeout=self.config.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.HTTPError as e:
            body = ""
            if e.response is not None:
                try:
                    body = e.response.text[:500]
                except Exception:
                    pass
            logger.warning(
                "Naver Search Ad API %s for keywords: %s — %s",
                e.response.status_code if e.response is not None else "?",
                keywords, body,
            )
            return []
        except Exception:
            logger.warning(
                "Naver Search Ad API request failed for keywords: %s",
                keywords, exc_info=True,
            )
            return []

        return self._parse_response(data, keywords)

    def _parse_response(
        self,
        data: dict,
        keywords: list[str],
    ) -> list[KeywordMetrics]:
        """Parse API response into KeywordMetrics.

        Matches returned keywords to our query keywords using
        normalized exact match (case-insensitive, space-stripped).
        """
        # Normalized lookup: "lg트롬" → "LG트롬"
        keyword_lookup = {kw.lower(): kw for kw in keywords}
        results: list[KeywordMetrics] = []
        matched_keywords: set[str] = set()

        for item in data.get("keywordList", []):
            rel_keyword = item.get("relKeyword", "").strip()
            rel_normalized = rel_keyword.lower().replace(" ", "")

            # 1. Exact match (normalized)
            matched = keyword_lookup.get(rel_normalized)

            # 2. Substring match: our keyword in API result or vice versa
            if not matched:
                for kw_lower, kw_original in keyword_lookup.items():
                    if kw_lower in rel_normalized or rel_normalized in kw_lower:
                        matched = kw_original
                        break

            if not matched or matched in matched_keywords:
                continue
            matched_keywords.add(matched)

            pc_search = _safe_int(item.get("monthlyPcQcCnt", 0))
            mobile_search = _safe_int(item.get("monthlyMobileQcCnt", 0))
            pc_clicks = _safe_int(item.get("monthlyAvePcClkCnt", 0))
            mobile_clicks = _safe_int(item.get("monthlyAveMobileClkCnt", 0))
            avg_cpc = _safe_int(item.get("plAvgDepth", 0))
            comp_idx = item.get("compIdx", "낮음")

            results.append(KeywordMetrics(
                product_name=matched,
                monthly_pc_search=pc_search,
                monthly_mobile_search=mobile_search,
                monthly_search_volume=pc_search + mobile_search,
                monthly_pc_clicks=pc_clicks,
                monthly_mobile_clicks=mobile_clicks,
                monthly_clicks=pc_clicks + mobile_clicks,
                avg_cpc=avg_cpc,
                competition=_map_competition(comp_idx),
            ))

        return results

    def _generate_signature(self, timestamp: str, method: str, path: str) -> str:
        """Generate HMAC-SHA256 signature for API auth."""
        message = f"{timestamp}.{method}.{path}"
        sign = hmac.new(
            self._secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return b64encode(sign).decode("utf-8")


def _clean_keyword(product_name: str) -> str:
    """Clean product name into API-compatible keyword.

    Naver Search Ad keywordstool rejects keywords with spaces.
    Also strips parenthesized model codes, kg/size suffixes, and
    manufacturer prefixes to get a short brand+model keyword.

    Examples:
        "LG전자 LG 트롬 21kg 스테인리스 실버(F21VDSK)" → "LG트롬"
        "삼성전자 비스포크AI콤보 WD80F25CH 화이트(WD80F25CHW)" → "삼성비스포크AI콤보"
        "삼성전자 그랑데 세탁기 21 kg 화이트(WF21T6000KW)" → "삼성그랑데세탁기"
    """
    name = product_name.strip()

    # Remove parenthesized content: (F21VDSK), (WD80F25CHW)
    name = re.sub(r"\([^)]*\)", "", name)

    # Remove common manufacturer prefixes (keep brand name)
    # "LG전자 LG 트롬" → "LG트롬", "LG전자 트롬" → "LG트롬"
    name = re.sub(r"^LG전자\s*(LG\s*)?", "LG", name)
    name = re.sub(r"^삼성전자\s*(삼성\s*)?", "삼성", name)

    # Remove color/finish suffixes: 화이트, 실버, 블랙, 그레이지, etc.
    name = re.sub(
        r"\s*(화이트|블랙|실버|그레이지|베이지|그린|다크스틸|"
        r"스테인리스\s*실버|네이처\s*에센스\s*블랙|네이처\s*베이지|네이처\s*그린)\s*$",
        "", name,
    )

    # Remove model codes (alphanumeric sequences like WD80F25CH, F21VDSK)
    name = re.sub(r"\b[A-Z]{1,3}\d{2,}[A-Z0-9]*\b", "", name)

    # Remove size/weight specs: 21kg, 25/18kg, 9kg, 12kg
    name = re.sub(r"\d+(/\d+)?\s*kg", "", name)

    # Remove generic product category words that add noise
    name = re.sub(r"\b(원룸|오피스텔|빌트인|소형|사업자용|신모델)\b", "", name)

    # Remove year references
    name = re.sub(r"\b20\d{2}\b", "", name)

    # Remove LCD size specs
    name = re.sub(r"\d+(\.\d+)?mm\s*LCD", "", name)

    # Remove special characters
    name = re.sub(r"[+/()~]", "", name)

    # Remove all spaces (API requirement)
    name = name.replace(" ", "").strip()

    # If too long, truncate (API works best with short keywords)
    if len(name) > 20:
        name = name[:20]

    return name


def _safe_int(value) -> int:
    """Safely convert API value to int (handles '< 10' style strings)."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        # API sometimes returns "< 10" for low volumes
        cleaned = value.replace("<", "").replace(",", "").strip()
        try:
            return int(cleaned)
        except ValueError:
            return 0
    return 0


def _map_competition(comp_idx: str) -> str:
    """Map Korean competition index to English."""
    mapping = {"높음": "high", "중간": "medium", "낮음": "low"}
    return mapping.get(comp_idx, "low")
