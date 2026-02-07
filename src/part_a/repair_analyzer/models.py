"""Data models for repair analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from statistics import mean


@dataclass
class CommunityPost:
    """A raw community post before GPT extraction."""

    title: str
    body: str
    source: str  # ppomppu | clien | naver_cafe
    source_url: str = ""
    date: date | None = None
    author: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "body": self.body[:200],
            "source": self.source,
            "source_url": self.source_url,
            "date": self.date.isoformat() if self.date else None,
        }


@dataclass
class RepairRecord:
    """GPT-extracted repair data from a community post.

    Maps to API contract: { product_id, failure_type, repair_cost, as_days, source_url, date }
    """

    product_name: str
    failure_type: str  # sensor | motor | software | battery | brush | mop | charging | other
    repair_cost: int  # KRW
    as_days: int | None = None  # AS turnaround days
    sentiment: str = "neutral"  # positive | negative | neutral
    source: str = ""  # ppomppu | clien | naver_cafe
    source_url: str = ""
    date: date | None = None

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "failure_type": self.failure_type,
            "repair_cost": self.repair_cost,
            "as_days": self.as_days,
            "sentiment": self.sentiment,
            "source": self.source,
            "source_url": self.source_url,
            "date": self.date.isoformat() if self.date else None,
        }


@dataclass
class RepairStats:
    """Aggregated repair statistics for a product."""

    product_name: str
    total_reports: int = 0
    expected_repair_cost: int = 0  # Probability-weighted KRW
    avg_as_days: float = 0.0
    failure_breakdown: list[FailureTypeStat] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "total_reports": self.total_reports,
            "expected_repair_cost": self.expected_repair_cost,
            "avg_as_days": round(self.avg_as_days, 1),
            "repair_stats": {
                "total_reports": self.total_reports,
                "failure_types": [f.to_dict() for f in self.failure_breakdown],
            },
        }


@dataclass
class FailureTypeStat:
    """Aggregated statistics for a single failure type."""

    type: str
    count: int
    avg_cost: int
    probability: float  # 0.0 - 1.0

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "count": self.count,
            "avg_cost": self.avg_cost,
            "probability": round(self.probability, 3),
        }


def calculate_repair_stats(records: list[RepairRecord]) -> RepairStats:
    """Calculate aggregated repair statistics from individual records.

    Expected repair cost = sum(avg_cost_per_type * probability_of_type)
    """
    if not records:
        return RepairStats(product_name="unknown")

    product_name = records[0].product_name
    total = len(records)

    # Group by failure type
    type_groups: dict[str, list[RepairRecord]] = {}
    for r in records:
        type_groups.setdefault(r.failure_type, []).append(r)

    failure_stats: list[FailureTypeStat] = []
    expected_cost = 0

    for ftype, group in type_groups.items():
        count = len(group)
        costs = [r.repair_cost for r in group if r.repair_cost > 0]
        avg_cost = int(mean(costs)) if costs else 0
        probability = count / total

        failure_stats.append(FailureTypeStat(
            type=ftype,
            count=count,
            avg_cost=avg_cost,
            probability=probability,
        ))
        expected_cost += int(avg_cost * probability)

    # Average AS turnaround days
    as_days_list = [r.as_days for r in records if r.as_days is not None and r.as_days > 0]
    avg_as = mean(as_days_list) if as_days_list else 0.0

    return RepairStats(
        product_name=product_name,
        total_reports=total,
        expected_repair_cost=expected_cost,
        avg_as_days=avg_as,
        failure_breakdown=sorted(failure_stats, key=lambda f: f.count, reverse=True),
    )
