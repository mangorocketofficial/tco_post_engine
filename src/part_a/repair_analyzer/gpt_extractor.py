"""GPT API-based extraction of repair data from community posts.

Uses OpenAI's GPT-4o structured output to extract:
- repair_cost: numeric KRW amount
- as_days: number of days for AS turnaround
- failure_type: categorized failure (sensor, motor, software, battery, etc.)
- sentiment: positive/negative/neutral about AS experience
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date

from .models import CommunityPost, RepairRecord

logger = logging.getLogger(__name__)

# Standard failure type categories
FAILURE_TYPES = [
    "sensor", "motor", "software", "battery",
    "brush", "mop", "charging", "suction",
    "noise", "navigation", "water_leak", "other",
]

EXTRACTION_PROMPT = """You are analyzing a Korean community forum post about a product repair or after-service (AS) experience.

Extract the following information from the post. If a field is not mentioned, use null.

Product being discussed: {product_name}

Return a JSON object with these fields:
- "mentions_product": boolean - does this post actually discuss the specified product?
- "failure_type": one of {failure_types} - what failed/broke
- "repair_cost": integer or null - repair cost in KRW (원). Convert 만원 notation (e.g., 15만원 = 150000)
- "as_days": integer or null - number of days from sending to receiving back from AS center
- "sentiment": "positive", "negative", or "neutral" - overall feeling about the AS/repair experience
- "summary": brief 1-line summary of the repair situation in Korean

Post title: {title}
Post content: {body}

Respond with ONLY a valid JSON object, no markdown formatting."""


class GPTExtractor:
    """Extract structured repair data from community posts using GPT API.

    Usage:
        extractor = GPTExtractor()
        records = extractor.extract_batch(posts, product_name="로보락 S8 Pro Ultra")
    """

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o") -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy-initialize the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise RuntimeError(
                    "openai package not installed. Run: pip install openai"
                )
        return self._client

    def extract_single(
        self, post: CommunityPost, product_name: str
    ) -> RepairRecord | None:
        """Extract repair data from a single community post.

        Args:
            post: The community post to analyze.
            product_name: Target product name for relevance filtering.

        Returns:
            RepairRecord if extraction succeeds, None if post is irrelevant.
        """
        prompt = EXTRACTION_PROMPT.format(
            product_name=product_name,
            failure_types=", ".join(FAILURE_TYPES),
            title=post.title,
            body=post.body[:2000],  # Truncate long posts
        )

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You extract structured data from Korean community posts. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=500,
            )

            content = response.choices[0].message.content or ""
            data = self._parse_response(content)

            if not data or not data.get("mentions_product", False):
                return None

            failure_type = data.get("failure_type", "other")
            if failure_type not in FAILURE_TYPES:
                failure_type = "other"

            repair_cost = data.get("repair_cost")
            if repair_cost is not None:
                repair_cost = max(0, int(repair_cost))
            else:
                repair_cost = 0

            as_days = data.get("as_days")
            if as_days is not None:
                as_days = max(0, int(as_days))

            sentiment = data.get("sentiment", "neutral")
            if sentiment not in ("positive", "negative", "neutral"):
                sentiment = "neutral"

            return RepairRecord(
                product_name=product_name,
                failure_type=failure_type,
                repair_cost=repair_cost,
                as_days=as_days,
                sentiment=sentiment,
                source=post.source,
                source_url=post.source_url,
                date=post.date,
            )

        except Exception:
            logger.warning(
                "GPT extraction failed for post: %s", post.title[:50],
                exc_info=True,
            )
            return None

    def extract_batch(
        self,
        posts: list[CommunityPost],
        product_name: str,
    ) -> list[RepairRecord]:
        """Extract repair data from multiple posts.

        Args:
            posts: Community posts to analyze.
            product_name: Target product name.

        Returns:
            List of successfully extracted RepairRecords.
        """
        records: list[RepairRecord] = []
        for i, post in enumerate(posts):
            logger.info(
                "Extracting post %d/%d: %s",
                i + 1, len(posts), post.title[:50],
            )
            record = self.extract_single(post, product_name)
            if record:
                records.append(record)

        logger.info(
            "Extracted %d records from %d posts (%.0f%% relevant)",
            len(records), len(posts),
            (len(records) / len(posts) * 100) if posts else 0,
        )
        return records

    @staticmethod
    def _parse_response(content: str) -> dict | None:
        """Parse GPT JSON response, handling potential formatting issues."""
        content = content.strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last lines (```json and ```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse GPT response: %s", content[:200])
            return None


class MockGPTExtractor(GPTExtractor):
    """Mock extractor for testing without API calls.

    Uses keyword-based heuristic extraction instead of GPT.
    """

    def __init__(self) -> None:
        super().__init__(api_key="mock")

    def extract_single(
        self, post: CommunityPost, product_name: str
    ) -> RepairRecord | None:
        """Extract using keyword heuristics instead of GPT."""
        text = f"{post.title} {post.body}".lower()

        # Check if post mentions the product
        product_words = product_name.lower().split()
        if not any(w in text for w in product_words if len(w) > 1):
            return None

        # Detect failure type by keywords
        failure_type = self._detect_failure_type(text)

        # Extract cost from Korean text
        repair_cost = self._extract_cost(text)

        # Extract AS days
        as_days = self._extract_as_days(text)

        # Detect sentiment
        sentiment = self._detect_sentiment(text)

        return RepairRecord(
            product_name=product_name,
            failure_type=failure_type,
            repair_cost=repair_cost,
            as_days=as_days,
            sentiment=sentiment,
            source=post.source,
            source_url=post.source_url,
            date=post.date,
        )

    @staticmethod
    def _detect_failure_type(text: str) -> str:
        """Detect failure type from text using keywords."""
        keyword_map = {
            "sensor": ["센서", "감지", "sensor"],
            "motor": ["모터", "motor", "소음"],
            "software": ["소프트웨어", "software", "앱", "업데이트", "펌웨어"],
            "battery": ["배터리", "battery", "충전시간"],
            "brush": ["브러시", "brush"],
            "mop": ["물걸레", "걸레", "mop"],
            "charging": ["충전", "charging", "독", "스테이션"],
            "suction": ["흡입", "suction", "흡입력"],
            "noise": ["소음", "noise", "시끄"],
            "navigation": ["네비게이션", "경로", "맵핑", "navigation", "길찾기"],
            "water_leak": ["누수", "물", "leak"],
        }
        for ftype, keywords in keyword_map.items():
            if any(kw in text for kw in keywords):
                return ftype
        return "other"

    @staticmethod
    def _extract_cost(text: str) -> int:
        """Extract repair cost from Korean text."""
        import re

        # "N만원" pattern
        man_match = re.search(r"(\d+)\s*만\s*(\d*)\s*원", text)
        if man_match:
            man = int(man_match.group(1))
            rest = int(man_match.group(2)) if man_match.group(2) else 0
            return man * 10000 + rest

        # "N,NNN원" or "NNN원" pattern (for repair costs, typically > 10000)
        won_match = re.search(r"([\d,]+)\s*원", text)
        if won_match:
            digits = won_match.group(1).replace(",", "")
            cost = int(digits) if digits else 0
            if cost >= 10000:  # Filter out small amounts unlikely to be repair costs
                return cost

        return 0

    @staticmethod
    def _extract_as_days(text: str) -> int | None:
        """Extract AS turnaround days from text."""
        import re

        # "N일" patterns near AS/수리/걸렸 keywords
        day_patterns = [
            r"(\d+)\s*일\s*(만에|걸렸|소요|걸림|후에|뒤에)",
            r"(약|대략|거의)?\s*(\d+)\s*일",
            r"(\d+)\s*영업일",
        ]
        for pattern in day_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                for g in groups:
                    if g and g.isdigit():
                        days = int(g)
                        if 1 <= days <= 60:  # Reasonable AS turnaround range
                            return days

        # "N주" pattern
        week_match = re.search(r"(\d+)\s*주", text)
        if week_match:
            weeks = int(week_match.group(1))
            if 1 <= weeks <= 8:
                return weeks * 7

        return None

    @staticmethod
    def _detect_sentiment(text: str) -> str:
        """Detect sentiment from text keywords."""
        positive = ["만족", "좋", "빠르", "친절", "추천", "감사", "훌륭"]
        negative = ["불만", "느리", "오래", "최악", "짜증", "실망", "불친절", "화남"]

        pos_count = sum(1 for w in positive if w in text)
        neg_count = sum(1 for w in negative if w in text)

        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"
