"""Tests for the Final Selector — A-0 + A-0.1 merge pipeline.

Tests cover:
- Product matching (model code + substring fallback)
- Overlap detection
- 3-case merge logic (default, overlap-1, overlap-2)
- Edge cases (empty results, single V product, all overlaps)
- FinalProduct / FinalSelectionResult serialization
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from src.part_a.product_selector.final_selector import (
    FinalSelector,
    _extract_model_tokens,
    find_overlaps,
    match_product,
)
from src.part_a.product_selector.models import (
    CandidateProduct,
    FinalProduct,
    FinalSelectionResult,
    ProductMention,
    ProductScores,
    RecommendationResult,
    SelectedProduct,
    SelectionResult,
    ValidationResult,
)


# ======================================================================
# Test helpers
# ======================================================================


def _make_candidate(
    name: str,
    brand: str = "브랜드",
    price: int = 1_000_000,
) -> CandidateProduct:
    return CandidateProduct(
        name=name,
        brand=brand,
        category="드럼세탁기",
        price=price,
    )


def _make_scores(name: str, total: float = 0.5) -> ProductScores:
    return ProductScores(
        product_name=name,
        clicks_score=total,
        cpc_score=total,
        search_volume_score=total,
        competition_score=total,
    )


def _make_selected(
    name: str,
    brand: str = "브랜드",
    rank: int = 1,
    price: int = 1_000_000,
    total_score: float = 0.5,
) -> SelectedProduct:
    candidate = _make_candidate(name, brand, price)
    scores = _make_scores(name, total_score)
    return SelectedProduct(
        rank=rank,
        candidate=candidate,
        scores=scores,
        selection_reasons=[f"A-0 rank #{rank}"],
    )


def _make_mention(
    product_name: str,
    normalized_name: str,
    mention_count: int = 5,
    sources: list[str] | None = None,
) -> ProductMention:
    return ProductMention(
        product_name=product_name,
        normalized_name=normalized_name,
        mention_count=mention_count,
        sources=sources or [],
    )


def _make_a0_result(
    products: list[SelectedProduct],
    category: str = "드럼세탁기",
) -> SelectionResult:
    return SelectionResult(
        category=category,
        selection_date=date(2026, 2, 8),
        data_sources={"candidates": "naver_shopping_api", "scoring": "naver_searchad_api"},
        candidate_pool_size=20,
        selected_products=products,
        validation=[ValidationResult("brand_diversity", True, "OK")],
    )


def _make_a0_1_result(
    products: list[ProductMention],
    keyword: str = "드럼세탁기",
) -> RecommendationResult:
    return RecommendationResult(
        keyword=keyword,
        search_query=f"가성비 {keyword}",
        total_blogs_searched=96,
        total_products_extracted=70,
        top_products=products,
        search_date="2026-02-08T15:00:00",
    )


# ======================================================================
# Product matching tests
# ======================================================================


class TestMatchProduct:
    def test_match_by_model_code(self):
        """Same model code in both names should match."""
        selected = _make_selected("삼성전자 그랑데 드럼 세탁기 WF19T6000KW 화이트")
        mention = _make_mention("삼성전자 그랑데 WF19T6000KW", "WF19T6000KW")
        is_match, method = match_product(selected, mention)
        assert is_match is True
        assert method == "model_code"

    def test_no_match_different_model_codes(self):
        """Different model codes should not match."""
        selected = _make_selected("삼성전자 WF19T6000KW")
        mention = _make_mention("LG전자 트롬 F21VDSK", "F21VDSK")
        is_match, method = match_product(selected, mention)
        assert is_match is False
        assert method == "none"

    def test_match_via_normalized_name_model_code(self):
        """A-0.1's normalized_name (model code) should match A-0 product."""
        selected = _make_selected("LG전자 트롬 오브제 F21VDSK 화이트")
        mention = _make_mention("LG 트롬 F21VDSK", "F21VDSK")
        is_match, method = match_product(selected, mention)
        assert is_match is True
        assert method == "model_code"

    def test_match_by_substring_fallback(self):
        """When no model code, substring match on normalized names."""
        selected = _make_selected("LG 트롬 오브제컬렉션 세탁기 21kg")
        mention = _make_mention(
            "LG 트롬 오브제컬렉션", "lg 트롬 오브제컬렉션",
        )
        is_match, method = match_product(selected, mention)
        assert is_match is True
        assert method == "substring"

    def test_no_match_completely_different(self):
        """Completely different products should not match."""
        selected = _make_selected("삼성전자 비스포크 냉장고 RF85B9002AP")
        mention = _make_mention("LG 트롬 오브제컬렉션", "lg 트롬 오브제컬렉션")
        is_match, method = match_product(selected, mention)
        assert is_match is False

    def test_match_model_code_case_insensitive(self):
        """Model code matching should be case-insensitive (both uppercased)."""
        selected = _make_selected("삼성전자 WF19t6000kw")
        mention = _make_mention("삼성 WF19T6000KW", "WF19T6000KW")
        is_match, method = match_product(selected, mention)
        assert is_match is True
        assert method == "model_code"

    def test_empty_names_no_crash(self):
        """Empty product names should not crash."""
        selected = _make_selected("")
        mention = _make_mention("", "")
        is_match, method = match_product(selected, mention)
        assert is_match is False

    def test_short_substring_no_false_positive(self):
        """Very short normalized names (< 5 chars) should not match via substring."""
        selected = _make_selected("삼성전자 세탁기 모델")
        mention = _make_mention("삼성", "삼성")
        is_match, method = match_product(selected, mention)
        assert is_match is False

    def test_match_by_prefix_truncated_code(self):
        """Truncated model code from Naver Shopping (RP13) should prefix-match full code (RP13C1022S9)."""
        selected = _make_selected(
            "삼성 김치냉장고 뚜껑형 소형 슬림 와인 술장고 미니김치냉장고 김냉 1인용 플러스 RP13"
        )
        mention = _make_mention(
            "삼성전자 김치플러스 뚜껑형 김치냉장고 RP13C1022S9",
            "RP13C1022S9",
        )
        is_match, method = match_product(selected, mention)
        assert is_match is True
        assert method == "model_code_prefix"

    def test_match_by_prefix_longer_a0_code(self):
        """Prefix match should work both ways (longer A-0 code, shorter V code)."""
        selected = _make_selected("삼성전자 김치플러스 RP13C1022S9 화이트")
        mention = _make_mention("삼성 김치냉장고 RP13", "RP13")
        is_match, method = match_product(selected, mention)
        assert is_match is True
        assert method == "model_code_prefix"

    def test_prefix_no_false_positive_different_series(self):
        """Different model series with shared prefix < 4 chars should not match."""
        selected = _make_selected("삼성 WF19T6000KW")
        mention = _make_mention("삼성 WF21B6000KW", "WF21B6000KW")
        is_match, method = match_product(selected, mention)
        # Both have full model codes but they're different — exact match fails, prefix doesn't apply
        assert is_match is False


# ======================================================================
# _extract_model_tokens tests
# ======================================================================


class TestExtractModelTokens:
    def test_extracts_full_model_code(self):
        tokens = _extract_model_tokens("삼성전자 WF19T6000KW 화이트")
        assert "WF19T6000KW" in tokens

    def test_extracts_short_4_char_token(self):
        """Should extract 4-char tokens like RP13 (which _extract_model_code misses)."""
        tokens = _extract_model_tokens("삼성 김치냉장고 RP13")
        assert "RP13" in tokens

    def test_no_tokens_from_korean_text(self):
        tokens = _extract_model_tokens("삼성전자 김치냉장고")
        assert tokens == []

    def test_skips_pure_numbers(self):
        """Pure numbers (e.g. 24kg → '24KG' has letters) but '1234' should be skipped."""
        tokens = _extract_model_tokens("모델 1234 제품")
        assert tokens == []

    def test_multiple_tokens(self):
        tokens = _extract_model_tokens("삼성 RP13 김치플러스 RP13C1022S9")
        assert "RP13" in tokens
        assert "RP13C1022S9" in tokens


# ======================================================================
# find_overlaps tests
# ======================================================================


class TestFindOverlaps:
    def test_no_overlaps(self):
        a0 = [
            _make_selected("삼성전자 WF19T6000KW", rank=1),
            _make_selected("LG전자 F21VDSK", rank=2),
        ]
        v = [
            _make_mention("위니아 DWF15GAWP", "DWF15GAWP"),
            _make_mention("대우 DWD09RCWF", "DWD09RCWF"),
        ]
        overlaps = find_overlaps(a0, v)
        assert overlaps == {}

    def test_v1_overlaps_a1(self):
        a0 = [
            _make_selected("삼성전자 WF19T6000KW", rank=1),
            _make_selected("LG전자 F21VDSK", rank=2),
        ]
        v = [
            _make_mention("삼성 WF19T6000KW", "WF19T6000KW"),
            _make_mention("위니아 DWF15GAWP", "DWF15GAWP"),
        ]
        overlaps = find_overlaps(a0, v)
        assert 0 in overlaps  # V1 overlaps
        assert overlaps[0] == (0, "model_code")  # With A1
        assert 1 not in overlaps  # V2 does not overlap

    def test_both_overlap(self):
        a0 = [
            _make_selected("삼성전자 WF19T6000KW", rank=1),
            _make_selected("LG전자 F21VDSK", rank=2),
        ]
        v = [
            _make_mention("삼성 WF19T6000KW", "WF19T6000KW"),
            _make_mention("LG 트롬 F21VDSK", "F21VDSK"),
        ]
        overlaps = find_overlaps(a0, v)
        assert 0 in overlaps  # V1 overlaps A1
        assert 1 in overlaps  # V2 overlaps A2

    def test_v1_overlaps_a2(self):
        a0 = [
            _make_selected("삼성전자 WF19T6000KW", rank=1),
            _make_selected("LG전자 F21VDSK", rank=2),
        ]
        v = [
            _make_mention("LG 트롬 F21VDSK", "F21VDSK"),  # V1 matches A2
            _make_mention("위니아 DWF15GAWP", "DWF15GAWP"),
        ]
        overlaps = find_overlaps(a0, v)
        assert 0 in overlaps
        assert overlaps[0] == (1, "model_code")  # V1 matches A2 (index 1)


# ======================================================================
# FinalSelector merge tests — 3 core cases
# ======================================================================


class TestFinalSelectorMerge:
    def _make_a0_top3(self):
        return [
            _make_selected("삼성전자 WF19T6000KW", brand="그랑데", rank=1, total_score=1.0),
            _make_selected("LG전자 F21VDSK", brand="트롬", rank=2, total_score=0.8),
            _make_selected("위니아 DWF15GAWP", brand="위니아", rank=3, total_score=0.5),
        ]

    def test_default_case(self):
        """V1 not in {A1, A2} → [A1, A2, V1]."""
        a0 = _make_a0_result(self._make_a0_top3())
        v = _make_a0_1_result([
            _make_mention("대우 DWD09RCWF", "DWD09RCWF", 8),
            _make_mention("일렉트로룩스 EWF1408", "EWF1408", 4),
        ])

        result = FinalSelector().merge(a0, v)

        assert result.merge_case == "default"
        assert len(result.final_products) == 3
        assert "WF19T6000KW" in result.final_products[0].name  # A1
        assert "F21VDSK" in result.final_products[1].name      # A2
        assert result.final_products[2].name == "대우 DWD09RCWF"  # V1
        assert result.final_products[2].source == "a0.1"
        assert result.final_products[2].recommendation_mention_count == 8

    def test_overlap_1_case(self):
        """V1 in {A1,A2}, V2 not → [A1, A2, V2]."""
        a0 = _make_a0_result(self._make_a0_top3())
        v = _make_a0_1_result([
            _make_mention("삼성 WF19T6000KW", "WF19T6000KW", 10),  # V1 == A1
            _make_mention("대우 DWD09RCWF", "DWD09RCWF", 5),       # V2 unique
        ])

        result = FinalSelector().merge(a0, v)

        assert result.merge_case == "overlap_1"
        assert len(result.final_products) == 3
        assert "WF19T6000KW" in result.final_products[0].name  # A1
        assert "F21VDSK" in result.final_products[1].name      # A2
        assert result.final_products[2].name == "대우 DWD09RCWF"  # V2
        assert result.final_products[2].source == "a0.1"

    def test_overlap_2_case(self):
        """V1, V2 both in {A1,A2} → [A1, A3, A2(gaseonbi)]."""
        a0 = _make_a0_result(self._make_a0_top3())
        v = _make_a0_1_result([
            _make_mention("LG 트롬 F21VDSK", "F21VDSK", 12),       # V1 == A2
            _make_mention("삼성 WF19T6000KW", "WF19T6000KW", 8),    # V2 == A1
        ])

        result = FinalSelector().merge(a0, v)

        assert result.merge_case == "overlap_2"
        assert len(result.final_products) == 3
        assert "WF19T6000KW" in result.final_products[0].name  # A1
        assert "DWF15GAWP" in result.final_products[1].name    # A3 promoted
        assert "F21VDSK" in result.final_products[2].name      # A2 → gaseonbi slot
        assert result.final_products[2].source == "both"
        assert result.final_products[2].recommendation_mention_count == 12

    def test_default_a0_product_annotated_when_matching_blog(self):
        """In default case, if A1 matches a V product, it should be annotated."""
        a0_top3 = self._make_a0_top3()
        a0 = _make_a0_result(a0_top3)
        v = _make_a0_1_result([
            _make_mention("대우 DWD09RCWF", "DWD09RCWF", 8),  # V1 unique
        ])

        result = FinalSelector().merge(a0, v)

        # A1, A2 should NOT have blog annotation (no overlap)
        for reason in result.final_products[0].selection_reasons:
            assert "blog" not in reason.lower()

    def test_overlap_1_a0_product_gets_blog_annotation(self):
        """In overlap-1, the A-0 product that matches V1 should get annotation."""
        a0 = _make_a0_result(self._make_a0_top3())
        v = _make_a0_1_result([
            _make_mention("삼성 WF19T6000KW", "WF19T6000KW", 10),
            _make_mention("대우 DWD09RCWF", "DWD09RCWF", 5),
        ])

        result = FinalSelector().merge(a0, v)

        # A1 should have "Also blog recommendation" annotation
        a1_reasons = result.final_products[0].selection_reasons
        assert any("blog recommendation" in r.lower() for r in a1_reasons)

    def test_ranks_are_sequential(self):
        """Final products should always have ranks 1, 2, 3."""
        a0 = _make_a0_result(self._make_a0_top3())
        v = _make_a0_1_result([
            _make_mention("대우 DWD09RCWF", "DWD09RCWF", 8),
        ])

        result = FinalSelector().merge(a0, v)

        ranks = [fp.rank for fp in result.final_products]
        assert ranks == [1, 2, 3]


# ======================================================================
# Edge cases
# ======================================================================


class TestFinalSelectorEdgeCases:
    def _make_a0_top3(self):
        return [
            _make_selected("삼성전자 WF19T6000KW", rank=1, total_score=1.0),
            _make_selected("LG전자 F21VDSK", rank=2, total_score=0.8),
            _make_selected("위니아 DWF15GAWP", rank=3, total_score=0.5),
        ]

    def test_a0_1_empty_results(self):
        """No A-0.1 results → pure A-0 Top 3."""
        a0 = _make_a0_result(self._make_a0_top3())
        v = _make_a0_1_result([])

        result = FinalSelector().merge(a0, v)

        assert result.merge_case == "default"
        assert len(result.final_products) == 3
        assert "WF19T6000KW" in result.final_products[0].name
        assert "F21VDSK" in result.final_products[1].name
        assert "DWF15GAWP" in result.final_products[2].name

    def test_single_v_no_overlap(self):
        """Only V1 available, no overlap → [A1, A2, V1]."""
        a0 = _make_a0_result(self._make_a0_top3())
        v = _make_a0_1_result([
            _make_mention("대우 DWD09RCWF", "DWD09RCWF", 6),
        ])

        result = FinalSelector().merge(a0, v)

        assert result.merge_case == "default"
        assert len(result.final_products) == 3
        assert result.final_products[2].name == "대우 DWD09RCWF"

    def test_single_v_with_overlap(self):
        """Only V1 available, overlaps A1 → fall back to pure A-0 (only V1, can't try V2)."""
        a0 = _make_a0_result(self._make_a0_top3())
        v = _make_a0_1_result([
            _make_mention("삼성 WF19T6000KW", "WF19T6000KW", 10),  # V1 == A1
        ])

        result = FinalSelector().merge(a0, v)

        # V1 overlaps, no V2 → overlap_1 branch but only 1 V product
        # Should still produce 3 products — A1 gets annotated, A-0 Top 3 used
        assert len(result.final_products) == 3

    def test_v1_matches_a3_not_a1_a2(self):
        """V1 matches A3 (not in top 2) → default case, V1 as 3rd slot."""
        a0 = _make_a0_result(self._make_a0_top3())
        v = _make_a0_1_result([
            _make_mention("위니아 DWF15GAWP", "DWF15GAWP", 7),  # V1 matches A3
            _make_mention("대우 DWD09RCWF", "DWD09RCWF", 3),
        ])

        result = FinalSelector().merge(a0, v)

        # V1 matches A3, but we only check overlap with A1, A2
        # So V1 is not in {A1, A2} → default case
        assert result.merge_case == "default"
        assert result.final_products[2].name == "위니아 DWF15GAWP"

    def test_all_v_overlap_with_same_a0_product(self):
        """V1 and V2 both match A1 → overlap-2 case."""
        a0 = _make_a0_result(self._make_a0_top3())
        v = _make_a0_1_result([
            _make_mention("삼성전자 그랑데 WF19T6000KW", "WF19T6000KW", 10),
            _make_mention("삼성 WF19T6000KW 화이트", "WF19T6000KW", 5),
        ])

        result = FinalSelector().merge(a0, v)

        # Both V1 and V2 overlap with A1 → overlap_2
        assert result.merge_case == "overlap_2"
        assert len(result.final_products) == 3

    def test_kimchi_fridge_truncated_code_real_case(self):
        """Real-world case: 김치냉장고 RP13 (truncated) should match RP13C1022S9."""
        a0_products = [
            _make_selected(
                "삼성 김치냉장고 뚜껑형 소형 슬림 와인 술장고 미니김치냉장고 김냉 1인용 플러스 RP13",
                brand="삼성",
                rank=1,
                total_score=0.731,
            ),
            _make_selected(
                "미닉스 소형미니김치냉장고 MNKR-100G",
                brand="미닉스",
                rank=2,
                total_score=0.510,
            ),
            _make_selected(
                "LG전자 디오스 김치톡톡 K332S14",
                brand="LG",
                rank=3,
                total_score=0.400,
            ),
        ]
        a0 = _make_a0_result(a0_products, category="김치냉장고")

        v_products = [
            _make_mention(
                "삼성전자 김치플러스 뚜껑형 김치냉장고 RP13C1022S9",
                "RP13C1022S9",
                5,
            ),
            _make_mention(
                "삼성 김치플러스 RP22C3111Z1",
                "RP22C3111Z1",
                3,
            ),
        ]
        v = _make_a0_1_result(v_products, keyword="김치냉장고")

        result = FinalSelector().merge(a0, v)

        # V1 (RP13C1022S9) should match A1 (RP13) via prefix
        assert result.merge_case == "overlap_1"
        assert len(result.final_products) == 3
        # A1 stays, A2 stays, V2 fills 3rd slot
        assert "RP13" in result.final_products[0].name
        assert "MNKR" in result.final_products[1].name
        assert "RP22C3111Z1" in result.final_products[2].name


# ======================================================================
# Serialization tests
# ======================================================================


class TestFinalProductSerialization:
    def test_to_dict(self):
        fp = FinalProduct(
            rank=1, name="삼성전자 WF19T6000KW", brand="그랑데",
            price=890000, source="a0",
            selection_reasons=["A-0 rank #1"],
            a0_rank=1,
            a0_scores=_make_scores("삼성전자 WF19T6000KW"),
        )
        d = fp.to_dict()
        assert d["rank"] == 1
        assert d["name"] == "삼성전자 WF19T6000KW"
        assert d["source"] == "a0"
        assert d["a0_scores"] is not None
        assert d["recommendation_mention_count"] is None

    def test_to_dict_with_recommendation(self):
        fp = FinalProduct(
            rank=3, name="대우 DWD09RCWF", brand="",
            price=0, source="a0.1",
            selection_reasons=["Blog recommendation #1"],
            recommendation_mention_count=8,
            recommendation_normalized_name="DWD09RCWF",
        )
        d = fp.to_dict()
        assert d["source"] == "a0.1"
        assert d["recommendation_mention_count"] == 8
        assert d["a0_scores"] is None


class TestFinalSelectionResultSerialization:
    def test_to_dict_structure(self):
        a0 = _make_a0_result([
            _make_selected("삼성전자 WF19T6000KW", rank=1),
        ])
        v = _make_a0_1_result([
            _make_mention("대우 DWD09RCWF", "DWD09RCWF", 5),
        ])
        result = FinalSelectionResult(
            category="드럼세탁기",
            selection_date=date(2026, 2, 8),
            merge_case="default",
            a0_result=a0,
            a0_1_result=v,
            final_products=[
                FinalProduct(1, "삼성전자 WF19T6000KW", "그랑데", 890000, "a0"),
            ],
            match_details=[],
        )
        d = result.to_dict()
        assert d["category"] == "드럼세탁기"
        assert d["merge_case"] == "default"
        assert "a0_summary" in d
        assert "a0_1_summary" in d
        assert "final_products" in d

    def test_to_json_serializable(self):
        a0 = _make_a0_result([_make_selected("Test", rank=1)])
        v = _make_a0_1_result([])
        result = FinalSelectionResult(
            category="테스트",
            selection_date=date(2026, 2, 8),
            merge_case="default",
            a0_result=a0,
            a0_1_result=v,
            final_products=[],
            match_details=[],
        )
        json_str = result.to_json()
        assert '"category": "테스트"' in json_str
        assert '"merge_case": "default"' in json_str
