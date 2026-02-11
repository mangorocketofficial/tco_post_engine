# DEV REQUEST: Remove A1 Step — Use A0 Price as Single Source of Truth

> **Priority:** 🔴 Pipeline simplification
> **Obsoletes:** A1_price_tracker_fix.md (entire document)
> **Modifies:** A2_A1_data_connection_fix.md, RUNBOOKV2.md, A4 TCO Engine
> **Date:** 2026-02-08

---

## Rationale

A1 (Danawa price scraping) collects vendor price lists to produce `purchase_price_avg`. But A0 already has a usable price from Naver Shopping API (`lprice`) for every selected product.

What A1 adds vs. A0:

| | A0 (Naver `lprice`) | A1 (Danawa scraping) |
|--|--|--|
| Price source | Naver Shopping API | Danawa vendor listings |
| Values per product | 1 (lowest) | 5~15 (multiple vendors) |
| Reliability | High (API structured data) | Low (HTML scraping, garbage data issues) |
| Pipeline cost | Already collected | Separate Python CLI step |
| Used downstream for | — | `purchase_price_avg` in A2 and A4 |

A1's multi-vendor price collection was intended to give a more accurate average, but in practice:
- A1 has critical scraping bugs (garbage prices, wrong products — see test results)
- The difference between Naver's `lprice` and a true market average is typically <5%
- A1 adds a full pipeline step with scraping fragility for marginal accuracy gain
- Price history feature (A1's secondary purpose) is not yet consumed by Part B

**Decision: Remove A1. Use A0's `lprice` as `purchase_price` throughout the pipeline.**

---

## Changes

### 1. RUNBOOK — Remove Step A1

**Before:**
```
A0 (product selection) → A1 (Danawa prices) → A2 (resale) → A3 (repair) → A5 (reviews) → A4 (TCO merge) → B (blog)
```

**After:**
```
A0 (product selection) → A2 (resale) → A3 (repair) → A5 (reviews) → A4 (TCO merge) → B (blog)
```

Delete the entire Step A1 section from RUNBOOKV2.md. No A1 CLI commands, no A1 output files.

### 2. A0 Output — `price` field is now the canonical purchase price

A0 already outputs `price` per product (from Naver Shopping `lprice`):

```json
{
  "name": "필립스 5000시리즈 S5466/17 로열블루",
  "price": 75900
}
```

This `price` field is now the **single source of truth** for purchase price used in:
- A2 retention curve calculation (denominator)
- A4 TCO formula (`purchase_price_avg`)
- Part B blog content (displayed price)

No schema change needed in A0 — the field already exists.

### 3. A2 — Read price from A0 (not A1)

**Replaces:** A2_A1_data_connection_fix.md (all references to A1)

RUNBOOK A2 procedure change:

```markdown
## Step A2: 중고 시세 조사

### 사전 입력
A0 출력 파일을 읽는다: `data/processed/a0_selected_{CATEGORY}.json`

각 제품의 구매가를 확인한다:
  - PRODUCT_1_PRICE = a0_output.selected_products[0].price  ← changed from A1
  - PRODUCT_2_PRICE = a0_output.selected_products[1].price
  - PRODUCT_3_PRICE = a0_output.selected_products[2].price

이 가격이 잔존율 계산의 기준(base price)이 된다.
```

A2 JSON schema — update source attribution:

```json
{
  "purchase_price_avg": 75900,
  "purchase_price_source": "a0"
}
```

The `purchase_price_cross_check` block from A2_A1_data_connection_fix.md still applies — A2 can compare A0's price against market prices encountered during web search and flag deviations. Just change the reference from A1 to A0.

### 4. A4 TCO Engine — Price priority simplification

**Before (3-level fallback):**
```
Priority 1: A1 clean price
Priority 2: A2 cross-check price
Priority 3: A0 Naver lprice
```

**After (single source):**
```
purchase_price = A0 selected_products[].price
No fallback needed — A0 always has a price.
```

The `resolve_purchase_price()` function proposed in A2_A1_data_connection_fix.md becomes unnecessary. A4 simply reads `price` from A0 JSON.

**Edge case:** A0.1 blog-only products may have `price: 0`. But per the A0 updates (v2, v3), all products now come from tier-based selection within A0's Naver Shopping candidates, so every product has a Naver `lprice`. The only scenario where `price: 0` could occur is if Naver API returns `lprice: "0"` for a product — in that case, A4 should log a warning and exclude the product from TCO calculation.

### 5. Code — No deletion required now, deprecate later

`src/part_a/price_tracker/` still contains working code (DanawaScraper, etc.). **Do not delete it now.** It may be useful in a future version for:
- Price history tracking (Part B Section 5 urgency triggers)
- Multi-source price validation
- Price alert features

For now:
- Remove A1 from RUNBOOK pipeline steps
- Remove A1 from any orchestration scripts that chain A0 → A1 → A2
- Leave `src/part_a/price_tracker/` code in place but unused

---

## Updated Pipeline Flow

```
A0 (product selection)
  ↓ selected_products[].price = canonical purchase price
  ├──→ A2 (resale) — reads A0 price as base for retention curves
  ├──→ A3 (repair) — no price dependency
  └──→ A5 (reviews) — no price dependency
         ↓
       A4 (TCO merge)
         ↓ purchase_price = A0 price (single source)
         ↓ resale = A2 data
         ↓ repair = A3 data
         ↓ real_cost_3yr = A0.price + A3.repair - A2.resale
         ↓
       Part B (blog generation)
```

---

## Document Status

| Document | Status |
|----------|--------|
| `A1_price_tracker_fix.md` | ❌ **OBSOLETE** — do not implement |
| `A2_A1_data_connection_fix.md` | ⚠️ **MODIFIED** — replace all "A1" references with "A0". Core logic (single source of truth, cross-check, fallback) still applies, just sourced from A0 instead of A1. |
| `A0_slot_framework_fix.md` | ✅ No change |
| `A0_single_tier_selection_v2.md` | ✅ No change |
| `A0_brand_and_score_floor_v3.md` | ✅ No change |

---

*Document version: 1.0*
*Author: Lead*