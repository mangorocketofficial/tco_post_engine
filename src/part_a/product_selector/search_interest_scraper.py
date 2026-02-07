"""Naver DataLab search trend scraper for product selection.

Uses Naver's Search Trend API (requires API key) to measure
relative search volume for candidate products.
Falls back to mock data if API key is unavailable.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

import requests

from ..common.config import Config
from ..common.http_client import HTTPClient
from .models import SearchInterest

logger = logging.getLogger(__name__)


class NaverDataLabScraper:
    """Naver DataLab API client for search trend data.

    Usage:
        with NaverDataLabScraper() as scraper:
            results = scraper.get_search_interest(
                ["로보락 S8 Pro", "삼성 제트봇 AI", "LG 코드제로"],
                period_days=90,
            )
    """

    API_URL = "https://openapi.naver.com/v1/datalab/search"

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = HTTPClient(self.config)

    def get_search_interest(
        self,
        product_names: list[str],
        period_days: int = 90,
    ) -> list[SearchInterest]:
        """Get relative search volume for multiple products.

        Args:
            product_names: List of product names to compare.
            period_days: Look-back period in days.

        Returns:
            List of SearchInterest with 30d and 90d volumes.
        """
        if not product_names:
            return []

        # Check if API keys are available
        if self.config.naver_datalab_client_id and self.config.naver_datalab_client_secret:
            return self._call_api(product_names, period_days)
        else:
            logger.warning("Naver DataLab API keys not set, using fallback estimation")
            return self._estimate_from_review_counts(product_names)

    def _call_api(
        self, product_names: list[str], period_days: int
    ) -> list[SearchInterest]:
        """Call Naver DataLab Search Trend API.

        The API accepts up to 5 keyword groups per request.
        """
        end_date = datetime.now()
        start_date_90d = end_date - timedelta(days=90)
        start_date_30d = end_date - timedelta(days=30)

        # Get 90-day data
        volumes_90d = self._fetch_volumes(
            product_names,
            start_date_90d.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        # Get 30-day data
        volumes_30d = self._fetch_volumes(
            product_names,
            start_date_30d.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        results: list[SearchInterest] = []
        for name in product_names:
            vol_30d = volumes_30d.get(name, 0.0)
            vol_90d = volumes_90d.get(name, 0.0)
            trend = self._calculate_trend(vol_30d, vol_90d)

            results.append(SearchInterest(
                product_name=name,
                volume_30d=vol_30d,
                volume_90d=vol_90d,
                trend_direction=trend,
            ))

        return results

    def _fetch_volumes(
        self,
        product_names: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, float]:
        """Fetch search volumes from the API for a date range.

        Returns dict mapping product name to average relative volume.
        """
        # API accepts up to 5 keyword groups per call
        volumes: dict[str, float] = {}

        for batch_start in range(0, len(product_names), 5):
            batch = product_names[batch_start:batch_start + 5]
            keyword_groups = [
                {"groupName": name, "keywords": [name]}
                for name in batch
            ]

            payload = {
                "startDate": start_date,
                "endDate": end_date,
                "timeUnit": "month",
                "keywordGroups": keyword_groups,
            }

            headers = {
                "X-Naver-Client-Id": self.config.naver_datalab_client_id,
                "X-Naver-Client-Secret": self.config.naver_datalab_client_secret,
                "Content-Type": "application/json",
            }

            try:
                resp = requests.post(
                    self.API_URL,
                    json=payload,
                    headers=headers,
                    timeout=self.config.request_timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                volumes.update(self._parse_api_response(data))
            except Exception:
                logger.warning("Naver DataLab API call failed", exc_info=True)
                for name in batch:
                    volumes.setdefault(name, 0.0)

        return volumes

    @staticmethod
    def _parse_api_response(data: dict) -> dict[str, float]:
        """Parse API JSON response into name → average volume mapping."""
        volumes: dict[str, float] = {}

        for result in data.get("results", []):
            group_name = result.get("title", "")
            data_points = result.get("data", [])
            if data_points:
                avg_ratio = sum(d.get("ratio", 0) for d in data_points) / len(data_points)
                volumes[group_name] = round(avg_ratio, 2)
            else:
                volumes[group_name] = 0.0

        return volumes

    def _estimate_from_review_counts(
        self, product_names: list[str]
    ) -> list[SearchInterest]:
        """Fallback: estimate search interest from product name length/popularity.

        This is a placeholder — in production, API keys should be provided.
        Returns uniform values so scoring doesn't break.
        """
        results: list[SearchInterest] = []
        for name in product_names:
            results.append(SearchInterest(
                product_name=name,
                volume_30d=50.0,
                volume_90d=50.0,
                trend_direction="stable",
            ))
        return results

    @staticmethod
    def _calculate_trend(volume_30d: float, volume_90d: float) -> str:
        """Determine trend direction.

        rising: 30d > 90d * 1.15
        declining: 30d < 90d * 0.85
        stable: otherwise
        """
        if volume_90d <= 0:
            return "stable"
        if volume_30d > volume_90d * 1.15:
            return "rising"
        if volume_30d < volume_90d * 0.85:
            return "declining"
        return "stable"

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> NaverDataLabScraper:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
