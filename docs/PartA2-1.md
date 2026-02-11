# DEV REQUEST: A2↔A1 Data Connection — Single Source of Truth for Purchase Price

> **Priority:** 🔴 Critical — mismatched base prices corrupt retention curves and TCO calculation
> **Scope:** `RUNBOOKV2.md` (A2 procedure), A2 JSON schema, `src/part_a/tco_engine/` (A4 merge logic)
> **Depends on:** A1 price tracker fix (clean `purchase_price_avg` required as input)
> **Date:** 2026-02-08

---

## 1. Problem Statement

### A1 and A2 independently estimate the same number

`purchase_price_avg` — the base price used to calculate resale retention rates and TCO — is currently determined by two different sources with no cross-reference:

| Step | How it gets `purchase_price_avg` | Method |
|------|----------------------------------|--------|
| A1 | Danawa scraper collects vendor prices → computes average | Python CLI, automated |
| A2 | Claude WebSearch estimates based on search results | Manual web research, independent |

These two numbers are never compared, validated, or reconciled. A4 TCO Engine receives both and has no rule for which to trust.

### Evidence from test run (전기면도기)

| Product | A1 price (corrupted) | A2 price (independent estimate) | Actual market price |
|---------|---------------------|--------------------------------|-------------------|
| Schtus KS0273 | 666,440원 | 26,100원 | ~26,000원 |
| 필립스 휴대용 | 75,890~134,000원 | 55,000원 | ~55,000~130,000원 |
| 브라운 면도기 5 | 99,000~389,000원 | 150,000원 | ~120,000~180,000원 |

A2 calculated retention curves using its own `purchase_price_avg`:

```json
// A2 output for Schtus
"purchase_price_avg": 26100,          // A2's own estimate
"resale_prices": { "2yr": { "price": 10440 } },
"retention_curve": { "2yr": 0.40 }    // 10440 / 26100 = 0.40 ✓ (internally consistent)
```

But if A4 merges this with A1's corrupted price (666,440원):

```
retention_2yr = 10440 / 666440 = 0.016  ← completely wrong
real_cost_3yr = 666440 + 7420 - 10440 = 663,420원  ← nonsensical
```

Even after A1 is fixed, the structural problem remains: two independent sources for the same number will inevitably diverge, and A4 has no rule for which wins.

### Root cause

The RUNBOOK A2 procedure tells Claude to search for resale prices and calculate retention rates, but never instructs it to **read A1's output first**. A2 operates in a data silo.

---

## 2. Current Data Flow (Before)

```
A0 (product selection)
  ↓ product names
A1 (Danawa prices)          A2 (resale via WebSearch)
  ↓                           ↓
  purchase_price_avg = X      purchase_price_avg = Y    ← X ≠ Y
  ↓                           ↓
  └──────────┬────────────────┘
             ↓
         A4 (TCO merge)
           purchase_price_avg = ???  ← which one to use?
```

A1 and A2 run in parallel silos. A4 receives conflicting base prices with no resolution rule.

---

## 3. Required Data Flow (After)

```
A0 (product selection)
  ↓ product names + reference prices
A1 (Danawa prices)
  ↓ purchase_price_avg (authoritative, filtered)
  ↓
A2 (resale via WebSearch)
  ↓ reads A1 output FIRST
  ↓ uses A1's purchase_price_avg as base for retention calculation
  ↓ copies A1's price into its own JSON (with source attribution)
  ↓
A4 (TCO merge)
  ↓ purchase_price_avg from A1 (single source of truth)
  ↓ no ambiguity
```

**Key principle:** `purchase_price_avg` has exactly ONE authoritative source: **A1**. A2 consumes it, A4 consumes it. Nobody re-estimates it.

---

## 4. Required Changes

### 4.1 RUNBOOK A2 Procedure — Add A1 Input Step

**Current RUNBOOK Step A2:**

```markdown
## Step A2: 중고 시세 조사 (Claude Code WebSearch)

### 실행 절차
1. 검색 수행 — 제품별로 아래 검색어로 WebSearch 실행:
   - "{PRODUCT_N} 중고 시세 당근마켓 번개장터"
2. 가격 추출 — 중고가 중앙값 수집
3. 잔존율 계산:
   - retention_2yr = resale_2yr / purchase_price_avg     ← WHERE DOES THIS COME FROM?
```

**Required RUNBOOK Step A2:**

```markdown
## Step A2: 중고 시세 조사 (Claude Code WebSearch)

### 사전 입력
A1 출력 파일을 먼저 읽는다: `data/processed/a1_prices_{CATEGORY}.json`

각 제품의 `purchase_price_avg`를 기록한다:
  - PRODUCT_1_PRICE = a1_output.products[0].purchase_price_avg
  - PRODUCT_2_PRICE = a1_output.products[1].purchase_price_avg
  - PRODUCT_3_PRICE = a1_output.products[2].purchase_price_avg

이 가격이 A2 전체에서 잔존율 계산의 기준(base price)이 된다.

### 실행 절차
1. 검색 수행 — (기존과 동일)
2. 가격 추출 — (기존과 동일)
3. 잔존율 계산:
   - retention_1yr = resale_1yr / PRODUCT_N_PRICE    ← A1 가격 사용
   - retention_2yr = resale_2yr / PRODUCT_N_PRICE    ← A1 가격 사용
   - retention_3yr = resale_3yr / PRODUCT_N_PRICE    ← A1 가격 사용

### 교차 검증 (NEW)
A1 가격과 A2에서 검색 중 발견한 신품 시세를 비교한다:
  - 차이 20% 이내 → 정상, A1 가격 사용
  - 차이 20~50% → notes에 "A1 가격과 시세 차이 존재" 기록, A1 가격 사용
  - 차이 50% 초과 → notes에 경고 기록, A1 가격 사용하되 A4에서 재검증 필요 플래그
```

### 4.2 A2 JSON Schema — Source Attribution

**Current A2 JSON:**

```json
{
  "product_name": "Schtus KS0273",
  "purchase_price_avg": 26100,
  "resale_prices": { ... },
  "retention_curve": { "1yr": 0.60, "2yr": 0.40, "3yr_plus": 0.20 }
}
```

**Required A2 JSON:**

```json
{
  "product_name": "Schtus KS0273",
  "purchase_price_avg": 26100,
  "purchase_price_source": "a1",
  "purchase_price_cross_check": {
    "a1_price": 26100,
    "market_price_observed": 25000,
    "deviation_pct": 4.2,
    "status": "ok"
  },
  "resale_prices": { ... },
  "retention_curve": { "1yr": 0.60, "2yr": 0.40, "3yr_plus": 0.20 }
}
```

New fields explained:

| Field | Purpose |
|-------|---------|
| `purchase_price_source` | Always `"a1"` — documents where the number came from |
| `purchase_price_cross_check.a1_price` | Copied from A1 output (for traceability) |
| `purchase_price_cross_check.market_price_observed` | Price Claude encountered during web search (if any) |
| `purchase_price_cross_check.deviation_pct` | `abs(a1 - observed) / a1 × 100` |
| `purchase_price_cross_check.status` | `"ok"` (<20%), `"warning"` (20-50%), `"alert"` (>50%) |

The `cross_check` block is for debugging and audit only. It does NOT override A1's price. It just flags discrepancies for human review.

### 4.3 A4 TCO Engine — Price Priority Rule

A4 merges A1 + A2 + A3 + A5 data. Add an explicit priority rule for `purchase_price_avg`:

```
Priority 1: A1 clean price (filtered average from Danawa)
  → Use when: A1 output exists and product has valid price records

Priority 2: A2 cross-check observed price
  → Use when: A1 failed for this product (0 records after filtering)
  → Log warning: "Using A2 observed price as fallback for {product}"

Priority 3: A0 Naver Shopping lprice
  → Use when: Both A1 and A2 have no price data
  → Log warning: "Using A0 reference price as last resort for {product}"
```

This priority rule should be implemented in the A4 TCO engine code as an explicit function, not buried in merge logic. The function signature should be something like:

```python
def resolve_purchase_price(a0_price, a1_price, a2_cross_check_price) -> tuple[int, str]:
    """Returns (resolved_price, source_label)."""
```

The `source_label` (e.g., `"a1"`, `"a2_fallback"`, `"a0_fallback"`) should be included in the final TCO export JSON so downstream consumers (and humans) can see which source was used.

### 4.4 A2 Fallback — When A1 Has Not Run Yet

Edge case: A2 is executed before A1 (e.g., during manual testing or partial pipeline runs).

**Rule:** If `a1_prices_{CATEGORY}.json` does not exist when A2 starts:
1. Use A0's `final_products[].price` as the base price.
2. Set `purchase_price_source` to `"a0_fallback"`.
3. Log a warning in `notes`: "A1 output not available. Using A0 reference price. Re-run A2 after A1 completes for accurate retention curves."

This ensures A2 never invents its own price estimate under any circumstances.

---

## 5. What NOT to Change

- **A2 resale price collection** — The web search queries, resale price extraction logic, and sample counting are all fine. Only the base price source changes.
- **A2 retention curve formula** — `retention = resale / purchase_price_avg` is correct. Only the denominator source changes (from self-estimated to A1-provided).
- **A1 output format** — A1 already outputs `purchase_price_avg` per product (after the A1 fix). A2 just needs to read it. No A1 schema changes needed.
- **A3, A5 steps** — These do not consume `purchase_price_avg`. No impact.

---

## 6. Validation Checklist

After implementation, verify with a test run:

| Check | How to verify |
|-------|--------------|
| A2 reads A1 output | A2 JSON `purchase_price_source` field is `"a1"` for all products |
| Prices match | A2 JSON `purchase_price_avg` equals A1 JSON `products[].purchase_price_avg` for each product |
| Retention math is correct | `retention_2yr × purchase_price_avg ≈ resale_2yr_price` (within rounding) |
| Cross-check works | `deviation_pct` is calculated and `status` reflects actual deviation |
| A4 uses A1 price | TCO export `purchase_price_avg` matches A1, not A2's independent estimate |
| Fallback works | If A1 file missing, A2 uses A0 price and marks source as `"a0_fallback"` |

---

## 7. RUNBOOK Execution Order Enforcement

The current RUNBOOK already shows `A1 → A2` order, but it's not enforced. Add an explicit dependency check:

**Current:**
```
Step A1: 신품 가격 수집 (Python)
Step A2: 중고 시세 조사 (Claude Code WebSearch)
```

**Required:**
```
Step A1: 신품 가격 수집 (Python)

Step A2: 중고 시세 조사 (Claude Code WebSearch)
  ⚠️ PREREQUISITE: Step A1 must be completed first.
  ⚠️ Verify file exists: data/processed/a1_prices_{CATEGORY}.json
  ⚠️ If A1 output is missing, use A0 prices as fallback (see Section 4.4).
```

---

## 8. File Change Summary

| File | Change type | What |
|------|------------|------|
| `RUNBOOKV2.md` | Modify | A2 procedure: add "read A1 output first" step, add cross-check procedure, add prerequisite warning |
| A2 JSON schema (in RUNBOOK) | Modify | Add `purchase_price_source`, `purchase_price_cross_check` fields |
| `src/part_a/tco_engine/` | Modify | Add `resolve_purchase_price()` priority function, include `source_label` in export |
| No new files required | | |

### Changes NOT in `src/part_a/price_tracker/`

This fix does not touch A1 code at all. A1 already outputs clean per-product `purchase_price_avg` (after the A1 fix). This request is about making A2 and A4 **consume** that output correctly.

---

*Document version: 1.0*
*Author: Lead*
*Depends on: A1_price_tracker_fix.md (A1 must output clean per-product prices)*
*Relates to: RUNBOOKV2.md Steps A2 and A4*