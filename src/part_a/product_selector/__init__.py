"""Product Selector Module (A-0) — Automated TOP 3 product selection for TCO comparison.

Selects top 3 products by Naver Search Ad keyword metrics
before the TCO data collection pipeline runs.
"""

from .models import (
    CandidateProduct,
    FinalProduct,
    FinalSelectionResult,
    KeywordMetrics,
    ProductScores,
    SelectedProduct,
    SelectionResult,
    ValidationResult,
)

__all__ = [
    "CandidateProduct",
    "FinalProduct",
    "FinalSelectionResult",
    "KeywordMetrics",
    "ProductScores",
    "SelectedProduct",
    "SelectionResult",
    "ValidationResult",
]
