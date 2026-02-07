"""Data models for maintenance time calculation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MaintenanceRecord:
    """A single maintenance task for a product.

    Maps to API contract: { task, frequency_per_month, minutes_per_task }
    """

    product_name: str
    task: str
    frequency_per_month: float  # times per month
    minutes_per_task: float  # minutes each time

    @property
    def total_monthly_minutes(self) -> float:
        return self.frequency_per_month * self.minutes_per_task

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "task": self.task,
            "frequency_per_month": self.frequency_per_month,
            "minutes_per_task": self.minutes_per_task,
            "total_monthly_minutes": round(self.total_monthly_minutes, 1),
        }


@dataclass
class MaintenanceSummary:
    """Aggregated maintenance time summary for a product."""

    product_name: str
    tasks: list[MaintenanceRecord] = field(default_factory=list)

    @property
    def total_monthly_minutes(self) -> float:
        return sum(t.total_monthly_minutes for t in self.tasks)

    @property
    def total_3yr_hours(self) -> float:
        """Total maintenance hours over 3 years."""
        return self.total_monthly_minutes * 36 / 60  # 36 months, convert to hours

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "total_monthly_minutes": round(self.total_monthly_minutes, 1),
            "total_3yr_hours": round(self.total_3yr_hours, 1),
            "tasks": [t.to_dict() for t in self.tasks],
        }
