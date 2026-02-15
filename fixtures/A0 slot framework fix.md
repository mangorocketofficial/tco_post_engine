# DEV REQUEST: A0 Tier-Based Slot Selection Framework

> **Priority:** 🔴 Critical — blocks all downstream pipeline steps (A1→A4→B)
> **Scope:** `src/part_a/product_selector/`
> **Date:** 2026-02-08

---

## 1. Problem Statement

### What's broken

The current A0 product selection pipeline selects TOP 3 products purely by keyword metric score (`clicks × 0.4 + cpc × 0.3 + search_volume × 0.2 + competition × 0.1`). This causes **price-tier collapse** — multiple products from the same price range get selected, leaving the 3-slot framework (Stability / Balance / Value) unfulfilled.

### Evidence from test run (전기면도기)

| Rank | Product | Price | Slot? |
|------|---------|-------|-------|
| 1 | Schtus KS0273 (no-name Chinese) | 26,100원 | Value |
| 2 | 필립스 휴대용 미니 | 20,900원 | Value |
| 3 | 브라운 면도기 5 (from A0.1) | N/A | Stability |

Two out of three products occupy the same budget tier. The Balance (mid-range) slot is empty. The blog output requires all three tiers to generate Section 3 (Quick Pick Table) with the `안정형 / 균형형 / 가성비형` columns.

### Why it matters

The Part B content structure (defined in `PartB_update.md`) is built around a 3-slot comparison:

```
Section 0: 3 situation-based picks → needs 3 distinct price tiers
Section 3: Quick Pick Table → columns are Stability / Balance / Value
Section 4: Per-product deep dive → needs meaningful price spread for TCO comparison
```

If A0 outputs two products in the same tier, the entire blog persuasion flow breaks. The reader has no reason to compare two similarly-priced budget products in a TCO framework.

### Root cause

`TopSelector` in `slot_selector.py` only enforces **brand diversity** (no duplicate manufacturers). It has zero awareness of price tiers. `PriceClassifier` exists in `price_classifier.py` but is **never called** in the pipeline.

---

## 2. Current Architecture (Before)

```
pipeline.py :: run()
│
├─ Step 1: _discover_candidates()     → 20 candidates from Naver Shopping API
├─ Step 2: _fetch_keyword_metrics()   → keyword scores populated
├─ Step 3: TopSelector.select()       → sort by total_score, brand dedup, pick top 3
├─ Step 4: _validate()                → brand_diversity + keyword_data checks
│
└─ Output: SelectionResult (3 products, no slot assignment)

final_selector.py :: merge()
│
├─ Takes A0 result (top 2) + A0.1 result (blog recommendations)
├─ Merge cases: default / overlap_1 / overlap_2
├─ 3rd slot always filled by A0.1's top blog recommendation
│
└─ Output: FinalSelectionResult (3 products, no slot labels)
```

### Files involved

| File | Current role | Issue |
|------|-------------|-------|
| `pipeline.py` | Orchestrator | Never calls PriceClassifier |
| `slot_selector.py` | TopSelector — score-only ranking | No tier awareness |
| `price_classifier.py` | PriceClassifier — tier assignment | **Exists but unused** |
| `models.py` | Data models | `SelectedProduct` has no `slot` field |
| `final_selector.py` | A0 + A0.1 merge | No slot preservation or assignment |
| `scorer.py` | ProductScorer — keyword metric scoring | No blog recommendation bonus |

---

## 3. Required Changes

### 3.1 Activate PriceClassifier in pipeline

Insert a new step between Step 2 (keyword metrics) and Step 3 (selection) in `pipeline.py`:

- Call `PriceClassifier.classify_candidates()` on the 20 candidates.
- Produce a `tier_map: dict[str, str]` mapping product_name → "premium" | "mid" | "budget".
- The existing relative percentile logic (bottom 30% / middle 40% / top 30%) is correct — **keep it as-is**.
- Pass `tier_map` to the selector in Step 3.

### 3.2 Replace TopSelector with SlotSelector

Refactor `slot_selector.py`. The new `SlotSelector` must:

1. **Group candidates by tier** using the tier_map from PriceClassifier.
2. **Within each tier**, rank by `total_score` descending.
3. **Pick 1 product per tier**, enforcing brand diversity across all 3 picks (not just within-tier).
4. **Assign slot labels**:
   - premium tier pick → `slot = "stability"`
   - mid tier pick → `slot = "balance"`
   - budget tier pick → `slot = "value"`

#### Fallback rules (when a tier is empty)

If any tier has 0 candidates after the Naver Shopping API returns:

1. First, check A0.1 blog recommendations for a product that fits the empty tier's price range.
2. If no A0.1 candidate available, pick a 2nd product from the adjacent tier (mid tier preferred).
3. Mark the fallback pick with a reason string like `"(tier fallback: no premium candidates in pool)"`.

The fallback order: A0.1 blog recommendation → adjacent tier → brand diversity relaxation.

### 3.3 Integrate A0.1 blog recommendation as score bonus

Currently A0.1 results are only used in the merge step (`final_selector.py`). Change this:

- **Before** SlotSelector runs, check if any candidate in the 20-product pool matches an A0.1 blog recommendation (use the existing `match_product()` function from `final_selector.py`).
- If a candidate has a blog mention, apply a **score bonus** to its `total_score` before tier-based selection.
- Suggested bonus logic: multiply `total_score` by a factor based on mention count, OR add a fixed bonus (e.g., +0.1 per mention). The exact formula is up to implementation — the key constraint is that **blog mentions should boost a product's rank within its tier, but not move it to a different tier**.
- This means A0.1 influences **which product wins within each tier**, not which tier a product belongs to.

### 3.4 Add `slot` field to models

Add a `slot: str` field to `SelectedProduct` and `FinalProduct` in `models.py`:

- Accepted values: `"stability"`, `"balance"`, `"value"`, or `""` (unassigned).
- This field must propagate through the entire pipeline: A0 → FinalSelector → A4 TCO export → Part B.
- The `to_dict()` methods must include the slot field in JSON output.

### 3.5 Update FinalSelector merge logic

`final_selector.py` currently treats the 3rd slot as "the blog recommendation slot." After this change:

- A0 now outputs 3 products with slot labels already assigned.
- FinalSelector should **preserve slot assignments** from A0 rather than overwriting.
- If A0.1 recommends a product that wasn't in A0's top 20, FinalSelector assigns it a slot based on its price relative to the A0 picks (e.g., if blog-recommended product costs more than all 3 A0 picks → stability slot, displacing A0's stability pick).
- Merge cases may need revision since A0 now outputs 3 tier-separated products instead of 2 score-ranked products.

### 3.6 Add validation: price_spread

Add a new validation check in Step 4 alongside `brand_diversity` and `keyword_data`:

- `price_spread`: Verify that the 3 selected products span at least 2 distinct price tiers.
- FAIL condition: all 3 products are in the same tier.
- This acts as a safety net for edge cases where the tier selection logic degrades.

---

## 4. Expected Output (After)

### A0 JSON output should look like:

```json
{
  "selected_products": [
    {
      "rank": 1,
      "name": "브라운 시리즈 9 Pro+",
      "brand": "브라운",
      "price": 350000,
      "slot": "stability",
      "selection_reasons": [
        "Premium tier: highest score in top 30% price range",
        "Blog recommendation bonus (+2 mentions)",
        "Total score: 0.870"
      ]
    },
    {
      "rank": 2,
      "name": "필립스 7000시리즈 S7786",
      "brand": "필립스",
      "price": 130000,
      "slot": "balance",
      "selection_reasons": [
        "Mid tier: highest score in middle 40% price range",
        "Total score: 0.793"
      ]
    },
    {
      "rank": 3,
      "name": "Schtus KS0273",
      "brand": "Schtus",
      "price": 26100,
      "slot": "value",
      "selection_reasons": [
        "Budget tier: highest score in bottom 30% price range",
        "Total score: 0.970"
      ]
    }
  ],
  "validation": {
    "brand_diversity": "PASS — 3 unique manufacturers",
    "keyword_data": "PASS — 3/3 products have keyword metrics",
    "price_spread": "PASS — 3 distinct tiers: premium, mid, budget"
  }
}
```

---

## 5. What NOT to Change

- **PriceClassifier tier logic** — relative percentile (30/40/30) split is correct. Do not add absolute price thresholds.
- **Keyword metric scoring formula** — the 4-dimension weighted score (`clicks × 0.4 + cpc × 0.3 + search_volume × 0.2 + competition × 0.1`) remains the primary ranking signal within each tier.
- **A0.1 RecommendationPipeline** — blog search + DeepSeek extraction pipeline is working correctly. No changes needed.
- **Naver Shopping API candidate discovery** (Step 1) — the 20-candidate pool generation is fine.

---

## 6. Test Requirements

### Existing tests to update

- `tests/part_a/test_product_selector.py` — `TestTopSelector` (5 tests) must be adapted for SlotSelector.

### New test scenarios required

| Scenario | Input | Expected |
|----------|-------|----------|
| Normal 3-tier | 20 candidates with spread prices | 1 pick per tier, 3 distinct slots |
| Tier empty (no premium) | 20 candidates all under 50k | Fallback: A0.1 recommendation OR 2nd mid-tier pick |
| Blog bonus | Candidate X has 5 blog mentions | X wins its tier even if raw score is lower |
| Brand conflict across tiers | Premium best = 삼성, Mid best = 삼성 | Mid falls to 2nd-best (different brand) |
| Single brand dominance | 15/20 candidates are 삼성 | Still picks 3 different brands across 3 tiers |
| Price tie | Multiple products at exact same price | Score breaks the tie |

### Validation test

- Run with `--keyword "전기면도기"` and confirm the output has 3 products in 3 different price tiers with slot labels assigned.

---

## 7. Downstream Impact

After this change, the following files consume the `slot` field and may need minor adjustments:

| Consumer | File | What it reads |
|----------|------|--------------|
| A4 TCO Engine | `src/part_a/tco_engine/` | `product.slot` for export JSON |
| B Content Writer | `src/part_b/content_writer/` | `product.slot` for Section 3 column assignment |
| B Template Engine | `src/part_b/template_engine/templates/section_3_quick_pick.jinja2` | `product.slot_label` already exists in template |

The `section_3_quick_pick.jinja2` template already references `product.slot_label`, confirming Part B was designed for this field. A0 just never populated it.

---

*Document version: 1.0*
*Author: Lead*
*Relates to: A0_product_selector_dev_plan.md, PartB_update.md, RUNBOOKV2.md*