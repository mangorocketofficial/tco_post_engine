# DEV REQUEST UPDATE v2: A0 — Single-Tier Selection (Winning Tier × 3 Products)

> **Supersedes:** A0_slot_framework_fix.md Section 3.2 (SlotSelector logic)
> **Priority:** 🔴 Critical — fundamental product selection paradigm change
> **Scope:** `src/part_a/product_selector/`, `PartB_update.md` (Section 3 template)
> **Date:** 2026-02-08

---

## 1. Why This Change

### The real-world shopping behavior

People don't search "전기면도기 추천" and compare a 190,000원 product against a 26,100원 product. They already have a budget in mind:

```
"가성비 전기면도기 추천"       → budget is ~3~5만원
"전기면도기 추천 10만원대"     → budget is ~10~15만원
"브라운 시리즈9 vs 필립스 9000" → budget is 20만원+
```

A blog comparing 190,000원 vs 45,000원 vs 26,100원 forces 2 out of 3 products to be irrelevant to any given reader. The 26,100원 reader skips the premium section entirely. The premium reader ignores the budget pick.

### The correct approach

Select the **single price tier where demand is highest**, then compare 3 products within that tier. This produces a blog that matches how people actually search:

- "10만원대 전기면도기 비교" → Premium tier: 필립스 7000 vs 브라운 9 vs 파나소닉 LV67
- "가성비 전기면도기 비교" → Budget tier: Schtus vs 샤오미 vs 플라이코

### TCO differentiation within same tier

Same price tier ≠ same TCO. Products at similar purchase prices can have very different:
- Repair costs (AS warranty coverage varies by brand)
- Resale retention (brand reputation affects used market value)
- Maintenance costs (blade replacement cycles, cleaning solution costs)

"비슷한 가격인데 3년 쓰면 이만큼 차이난다" is actually a **stronger** message than cross-tier comparison where the conclusion is obvious (expensive = better quality, cheap = lower cost).

Additionally, Section 2 category-specific criteria (myth busting / real differentiator / decision fork) provide qualitative differentiation that compensates for narrower TCO spread.

---

## 2. Selection Logic Change

### Before (A0_slot_framework_fix.md):

```
20 candidates → PriceClassifier → 3 tiers
  → Pick 1 per tier (stability / balance / value)
  → Output: 3 products from 3 DIFFERENT tiers
```

### After (this update):

```
20 candidates → PriceClassifier → 3 tiers
  → Score each tier: sum of top-3 product scores within tier
  → Select WINNING TIER (highest aggregate score)
  → Pick top 3 from winning tier (brand diversity enforced)
  → Output: 3 products from SAME tier
```

### Tier Scoring Formula

For each tier (premium / mid / budget):

```
tier_score = sum of top 3 total_scores within that tier
```

If a tier has fewer than 3 products, it is penalized:
- 2 products: `tier_score = sum of 2 scores × (2/3)` — penalty for shallow pool
- 1 product: `tier_score = score × (1/3)` — heavy penalty
- 0 products: `tier_score = 0` — excluded

This naturally selects the tier where the market has the most competitive, well-known products — which is also the tier readers are most likely searching for.

### Why aggregate score works as demand proxy

The keyword metric score (`clicks × 0.4 + cpc × 0.3 + search_volume × 0.2 + competition × 0.1`) measures **consumer search interest**. If the top 3 premium products have high aggregate scores, it means people are actively searching for premium electric shavers. If budget products dominate, the market demand is in the budget tier.

### Example (전기면도기):

```
Premium tier (10만원+):
  필립스 7000 (0.793) + 브라운 9 (0.65) + 파나소닉 LV67 (0.52) = 1.963

Mid tier (3~10만원):
  브라운 310BT (0.358) + 필립스 3000 (0.31) + 제이린드버그 (0.28) = 0.948

Budget tier (~3만원):
  Schtus (0.970) + 샤오미 S101 (0.42) + 플라이코 (0.38) = 1.770

Winner: Premium (1.963)
→ Final 3: 필립스 7000 / 브라운 9 / 파나소닉 LV67
```

---

## 3. Required Code Changes

### 3.1 `slot_selector.py` — Replace tier-per-slot with winning-tier selection

Remove the current SlotSelector logic that picks 1 product per tier.

New `SlotSelector` (or rename to `TierSelector`) must:

1. Receive `candidates`, `scores`, and `tier_map` (from PriceClassifier).
2. Group candidates by tier.
3. **Score each tier** by summing top-3 scores within that tier (with penalty for <3 candidates).
4. **Select the winning tier**.
5. **Pick top 3 from winning tier**, enforcing brand diversity (no duplicate manufacturers).
6. Assign `rank: 1, 2, 3` by score within the winning tier.

#### Fallback: fewer than 3 products in winning tier after brand dedup

If the winning tier has fewer than 3 unique-brand products:
1. Relax brand diversity within the tier (allow same brand).
2. If still fewer than 3, pull from the adjacent tier (2nd-place tier) to fill.
3. Mark pulled products with reason: `"(pulled from adjacent tier: insufficient candidates in winning tier)"`.

### 3.2 `pipeline.py` — Wire tier scoring

After PriceClassifier runs (Step 2.5), add tier scoring step:

```
Step 2.5: PriceClassifier → tier_map
Step 2.6 (NEW): TierScorer → tier_scores, winning_tier
Step 3: SlotSelector.select(candidates, scores, tier_map, winning_tier)
```

The tier scoring logic can live in `slot_selector.py` or a new small function. It does not need its own file.

### 3.3 `models.py` — Update fields

**SelectionResult — add tier metadata:**

```python
@dataclass
class SelectionResult:
    category: str
    selection_date: date
    data_sources: dict
    candidate_pool_size: int
    selected_products: list[SelectedProduct]
    validation: list[ValidationResult]
    
    # NEW fields
    selected_tier: str          # "premium" | "mid" | "budget"
    tier_scores: dict[str, float]  # {"premium": 1.963, "mid": 0.948, "budget": 1.770}
    tier_product_counts: dict[str, int]  # {"premium": 6, "mid": 8, "budget": 6}
```

**SelectedProduct — slot meaning changes:**

```python
@dataclass
class SelectedProduct:
    rank: int           # 1, 2, 3 (within winning tier, by score)
    candidate: CandidateProduct
    scores: ProductScores
    slot: str = ""      # MEANING CHANGED — see below
    selection_reasons: list[str] = field(default_factory=list)
```

The `slot` field's meaning changes:

| Before | After |
|--------|-------|
| `"stability"` = premium tier product | `slot` = differentiation role within same tier |
| `"balance"` = mid tier product | e.g., "피부 보호형", "올인원형", "절삭력형" |
| `"value"` = budget tier product | Generated by Part B based on A5 review data |

**Important:** A0 should output `slot: ""` (empty). The slot label is now a content decision, not a price-tier decision. Part B's content writer will assign contextual labels based on A5's `decision_fork` data.

### 3.4 `final_selector.py` — Annotation only (no change from previous update)

FinalSelector still only annotates A0.1 blog recommendation matches. No slot replacement. The previous update (`A0_slot_framework_fix_update.md`) already covers this — no additional changes needed here.

### 3.5 Validation — update `price_spread` check

**Remove:** `price_spread` validation (checking 3 distinct tiers) — this no longer applies.

**Add:** `tier_depth` validation — verify the winning tier has at least 3 candidates before brand dedup.

```python
ValidationResult(
    check_name="tier_depth",
    passed=tier_product_counts[winning_tier] >= 3,
    detail=f"Winning tier '{winning_tier}' has {n} candidates (minimum 3)"
)
```

**Keep:** `brand_diversity` — still required within the winning tier.

---

## 4. A0.1 Blog Bonus — Tier-Aware Application

The A0.1 score bonus (from original A0_slot_framework_fix.md Section 3.3) still applies, but with a nuance:

**A0.1 blog mentions should boost products within any tier, but the tier selection itself should also consider blog coverage.** If premium products have high blog mentions, it signals that bloggers and readers are actively discussing premium options — reinforcing that tier as the right choice.

Implementation: Apply the A0.1 score bonus to individual product scores BEFORE tier scoring. This way, blog-popular products raise their tier's aggregate score naturally.

---

## 5. Expected Output (After)

```json
{
  "category": "전기면도기",
  "selection_date": "2026-02-08",
  "selected_tier": "premium",
  "tier_scores": {
    "premium": 1.963,
    "mid": 0.948,
    "budget": 1.770
  },
  "tier_product_counts": {
    "premium": 6,
    "mid": 8,
    "budget": 6
  },
  "selected_products": [
    {
      "rank": 1,
      "name": "필립스 면도기 7000시리즈 S7886/70",
      "brand": "필립스",
      "price": 190000,
      "slot": "",
      "selection_reasons": [
        "Winning tier: premium (score 1.963)",
        "Rank 1 in premium tier",
        "Blog recommendation bonus (+4 mentions)",
        "Total score: 0.893"
      ]
    },
    {
      "rank": 2,
      "name": "브라운 시리즈9 Pro 9477cc",
      "brand": "BRAUN",
      "price": 280000,
      "slot": "",
      "selection_reasons": [
        "Winning tier: premium (score 1.963)",
        "Rank 2 in premium tier",
        "Total score: 0.750"
      ]
    },
    {
      "rank": 3,
      "name": "파나소닉 ES-LV67",
      "brand": "파나소닉",
      "price": 170000,
      "slot": "",
      "selection_reasons": [
        "Winning tier: premium (score 1.963)",
        "Rank 3 in premium tier",
        "Blog recommendation bonus (+3 mentions)",
        "Total score: 0.620"
      ]
    }
  ],
  "validation": {
    "brand_diversity": "PASS — 3 unique manufacturers",
    "keyword_data": "PASS — 3/3 products have keyword metrics",
    "tier_depth": "PASS — premium tier has 6 candidates (minimum 3)"
  }
}
```

---

## 6. Downstream Impact

### Part B — Section 3 Quick Pick Table

**Before:** Column labels = `안정형 / 균형형 / 가성비형` (price-tier based)

**After:** Column labels = contextual differentiation within the same tier. Examples:

```
Premium 전기면도기: "피부 보호 특화 / 올인원 자동세척 / 절삭력 최강"
Budget 로봇청소기:  "물걸레 특화 / 흡입력 집중 / 가장 저렴한 유지비"
```

These labels are NOT generated by A0. They come from A5 review analysis (`decision_fork` field) and are assigned during Part B content generation. A0 outputs `slot: ""` and Part B fills it in.

The `section_3_quick_pick.jinja2` template already handles this — it uses `product.slot_label or product.name` as the column header, so empty slot labels will fall back to product name until Part B assigns a label.

### Part B — Section 0 Hook

**Before:** "상황별 추천: 안정형은 X, 균형형은 Y, 가성비형은 Z"

**After:** "10만원대 전기면도기 3개를 비교했습니다. 3년 실비용으로 보면 [winner]가 가장 경제적입니다."

The hook now references a **single price range** instead of spanning all tiers. This matches the search query the reader used to find the blog.

### Part B — SEO Title / Meta

Blog title changes from:
```
❌ "전기면도기 추천 TOP3 — 안정형/균형형/가성비형 비교"
✅ "10만원대 전기면도기 추천 TOP3 — 3년 실비용 비교 (2026)"
```

The price range in the title matches the selected tier, improving keyword relevance for tier-specific search queries.

### A1, A2, A3, A5 — No structural changes

These steps receive 3 product names and process them identically regardless of whether they're from the same tier or different tiers. No changes needed.

---

## 7. What NOT to Change

- **PriceClassifier** — percentile-based tier classification (30/40/30 split) remains correct
- **ProductScorer** — keyword metric scoring formula unchanged
- **A0.1 RecommendationPipeline** — blog search + extraction unchanged
- **FinalSelector annotation logic** — already fixed in previous update, no further changes
- **A1 through A5 pipeline steps** — receive 3 products regardless of tier origin

---

## 8. Test Requirements

| Scenario | Input | Expected |
|----------|-------|----------|
| Normal — clear winner | Premium top3 sum > Mid > Budget | Premium tier selected, 3 premium products |
| Tight race | Premium 1.96 vs Budget 1.95 | Higher score wins (premium) |
| Budget dominance | Budget products have highest search volume | Budget tier wins despite lower prices |
| Tier with <3 candidates | Premium has only 2 products | Penalty applied (×2/3), may lose to deeper tier |
| Brand dedup in tier | Top 3 in winning tier are all 삼성 | Pick 삼성 #1, then best non-삼성, then next |
| All products same price | 20 products within ±10% price range | One large tier wins by default, 3 selected within |
| Blog bonus shifts tier | Budget would win, but premium has heavy blog mentions | Blog bonus raises premium scores → premium wins |

---

## 9. File Change Summary

| File | Change |
|------|--------|
| `slot_selector.py` | Replace tier-per-slot → winning tier selection + top 3 within tier |
| `pipeline.py` | Add tier scoring step (2.6), pass winning_tier to selector |
| `models.py` | Add `selected_tier`, `tier_scores`, `tier_product_counts` to SelectionResult. Change `slot` to empty string default. |
| `final_selector.py` | No change (already annotation-only from previous update) |

---

## 10. Relationship to Other Documents

| Document | Impact |
|----------|--------|
| `A0_slot_framework_fix.md` | Sections 3.1 (PriceClassifier activation) and 3.3 (A0.1 bonus) still apply. Section 3.2 (SlotSelector) is **replaced** by this document. Section 3.6 (price_spread validation) replaced by tier_depth. |
| `A0_slot_framework_fix_update.md` | FinalSelector annotation-only change still applies as-is. |
| `A1_price_tracker_fix.md` | No impact — A1 reads product names from A0 JSON regardless of tier. |
| `A2_A1_data_connection_fix.md` | No impact — A2 reads A1 prices regardless of tier. |
| `PartB_update.md` | Section 3 slot labels change from price-tier to contextual. Section 0 hook references single price range. SEO title includes tier price range. |

---

*Document version: 2.0*
*Supersedes: A0_slot_framework_fix.md Section 3.2*
*Author: Lead*