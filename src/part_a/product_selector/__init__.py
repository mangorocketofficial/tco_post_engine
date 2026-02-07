"""Product Selector Module (A-0) — Automated 3-product selection for TCO comparison.

Selects optimal Stability / Balance / Value products from market data
before the TCO data collection pipeline runs.
"""

from .models import (
    CandidateProduct,
    ProductScores,
    SelectionResult,
    SlotAssignment,
    ValidationResult,
)

__all__ = [
    "CandidateProduct",
    "ProductScores",
    "SelectionResult",
    "SlotAssignment",
    "ValidationResult",
]
