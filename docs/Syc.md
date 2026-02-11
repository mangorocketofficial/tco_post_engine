# DEV REQUEST: A4 TCO Engine — Schema Sync & Formula Update

> **Priority:** 🔴 Critical — A4 cannot consume new A2 output without this change
> **Scope:** `src/part_a/tco_engine/` — `exporter.py`, `calculator.py`, `main.py`
> **Depends on:** A2 resale schema change (median ±10%), A1 removal (A0 price as source)
> **Date:** 2026-02-08

---

## 1. Problem

A4's current code reads fields that no longer exist after A2 simplification and A1 removal:

```python
# exporter.py — current code reads these fields:
tco["tco"]["purchase_price_avg"]    # ← was from A1, now from A0 as "price"
tco["tco"]["purchase_price_min"]    # ← was from A1, removed
tco["tco"]["resale_value_1yr"]      # ← was from A2 year-segmented, removed
tco["tco"]["resale_value_2yr"]      # ← was from A2 year-segmented, removed

# main.py — current log format:
logger.info("resale(1yr/2yr/3yr+)=%s/%s/%s", ...)  # ← year segments no longer exist
```

If A4 runs against the new A2 JSON, it will crash on missing keys or produce wrong TCO values.

---

## 2. Input Schema Changes (What A4 Now Receives)

### A0 Input (unchanged)

```json
{
  "selected_products": [
    { "name": "...", "brand": "...", "price": 75900 }
  ]
}
```

`price` = purchase price (Naver Shopping `lprice`). Single source, no fallback.

### A2 Input (CHANGED)

**Before:**
```json
{
  "resale_prices": {
    "1yr": {"price": 29250},
    "2yr": {"price": 18000},
    "3yr_plus": {"price": 9000}
  },
  "retention_curve": { "1yr": 0.65, "2yr": 0.40, "3yr_plus": 0.20 }
}
```

**After:**
```json
{
  "purchase_price": 75900,
  "purchase_price_source": "a0",
  "resale": {
    "resale_price": 23500,
    "median_raw": 23000,
    "filter_range_pct": 10,
    "sample_count": 9,
    "sample_count_after_filter": 4,
    "confidence": "high",
    "sources": ["당근마켓", "번개장터"],
    "collected_prices": [15000, 18000, 20000, 22000, 23000, 24000, 25000, 28000, 45000],
    "filter_note": ""
  }
}
```

### A3 Input (unchanged)

```json
{
  "expected_repair_cost": 8400,
  "avg_as_days": 3.0,
  "maintenance_tasks": [...],
  "automation_rate": 80
}
```

---

## 3. TCO Formula Change

**Before:**
```
real_cost_3yr = purchase_price_avg + expected_repair_cost - resale_value_2yr
```

**After:**
```
real_cost_3yr = purchase_price + expected_repair_cost - resale_price
```

Where:
- `purchase_price` = A0 `selected_products[].price`
- `expected_repair_cost` = A3 `products[].expected_repair_cost`
- `resale_price` = A2 `products[].resale.resale_price`

Edge cases:
- `resale_price == 0` (no data) → `real_cost_3yr = purchase_price + expected_repair_cost`
- `purchase_price == 0` → log warning, exclude product from export
- `expected_repair_cost == 0` (no failure data) → treat as 0, proceed normally

---

## 4. A4 Output Schema (Export JSON)

### Before:

```json
{
  "tco": {
    "purchase_price_avg": 0,
    "purchase_price_min": 0,
    "resale_value_1yr": 0,
    "resale_value_2yr": 0,
    "expected_repair_cost": 0,
    "real_cost_3yr": 0
  }
}
```

### After:

```json
{
  "tco": {
    "purchase_price": 0,
    "resale_price": 0,
    "resale_confidence": "high | medium | low | none",
    "expected_repair_cost": 0,
    "real_cost_3yr": 0
  }
}
```

**Removed fields:**
- `purchase_price_avg` → renamed to `purchase_price`
- `purchase_price_min` → removed (single source, no min/avg distinction)
- `resale_value_1yr` → removed (no year segmentation)
- `resale_value_2yr` → replaced by `resale_price`

**Added fields:**
- `resale_confidence` → pass through from A2's `resale.confidence` (for Part B to display confidence indicator)

### Full Export Schema:

```json
{
  "category": "{CATEGORY}",
  "generated_at": "ISO 8601",
  "products": [
    {
      "product_id": "product_slug",
      "product_name": "제품 전체명",
      "brand": "브랜드명",
      "tco": {
        "purchase_price": 0,
        "resale_price": 0,
        "resale_confidence": "high | medium | low | none",
        "expected_repair_cost": 0,
        "real_cost_3yr": 0
      },
      "qualitative": {
        "as_turnaround_days": 0,
        "warranty_months": 0,
        "maintenance_tasks": [
          {"task": "유지관리 항목", "automated": true}
        ],
        "automation_rate": 0
      },
      "review_insights": {
        "reviews_collected": 0,
        "purchase_motivations": [
          {
            "spec_or_criteria": "",
            "mention_count": 0,
            "appears_in_satisfaction": true,
            "appears_in_complaints": false,
            "verdict": "overrated | justified | underrated"
          }
        ],
        "sentiment_keywords": {
          "positive": [{"keyword": "", "count": 0}],
          "negative": [{"keyword": "", "count": 0}]
        },
        "hidden_differentiator": "",
        "environment_splits": [
          {
            "environment": "",
            "key_issue": "",
            "sentiment": "positive | negative",
            "typical_comment": ""
          }
        ]
      }
    }
  ],
  "category_insights": {
    "most_overrated_spec": "",
    "real_differentiator": "",
    "decision_forks": [
      {
        "user_type": "",
        "priority": "",
        "recommended_product": "해당 유형에 맞는 제품명"
      }
    ]
  },
  "credibility": {
    "total_review_count": 0,
    "resale_sample_count": 0,
    "repair_report_count": 0,
    "collection_period": "",
    "review_sources": ["쿠팡", "네이버쇼핑"]
  }
}
```

---

## 5. File-by-File Changes

### `calculator.py`

Update TCO calculation:

```python
# Before
real_cost = purchase_price_avg + repair_cost - resale_value_2yr

# After
real_cost = purchase_price + repair_cost - resale_price
```

Update input reading to match new A2 schema:
- `resale_prices.2yr.price` → `resale.resale_price`
- Remove references to `1yr`, `3yr_plus`, `retention_curve`

### `exporter.py`

**`export_category()` method:**

Update `product_export` dict construction:

```python
# Before
"tco": {
    "purchase_price_avg": ...,
    "purchase_price_min": ...,
    "resale_value_1yr": ...,
    "resale_value_2yr": ...,
    "expected_repair_cost": ...,
    "real_cost_3yr": ...,
}

# After
"tco": {
    "purchase_price": a0_product["price"],
    "resale_price": a2_product["resale"]["resale_price"],
    "resale_confidence": a2_product["resale"]["confidence"],
    "expected_repair_cost": a3_product["expected_repair_cost"],
    "real_cost_3yr": calculated_value,
}
```

Remove fields from export:
- `price_history` → was from A1, no longer collected
- `resale_curve` → year-segmented, no longer exists

Keep fields:
- `qualitative` (from A3) — unchanged
- `review_insights` (from A5) — unchanged
- `category_insights` (from A5) — unchanged
- `credibility` (aggregated) — update `resale_sample_count` to read from A2's `resale.sample_count`

### `main.py`

Update log format:

```python
# Before
logger.info(
    "  %s: purchase=%s, resale(1yr/2yr/3yr+)=%s/%s/%s, repair=%s → real_cost=%s원",
    ...
)

# After
logger.info(
    "  %s: purchase=%s, resale=%s (%s), repair=%s → real_cost=%s원",
    product["name"],
    tco["purchase_price"],
    tco["resale_price"],
    tco["resale_confidence"],
    tco["expected_repair_cost"],
    tco["real_cost_3yr"],
)
```

Add `--a0-data` argument if not already present (for reading purchase prices directly from A0 JSON).

---

## 6. Part B Template Impact

Part B templates currently reference these TCO fields. After A4 schema change, templates must also update:

| Template | Current Field | New Field |
|----------|--------------|-----------|
| `section_3_quick_pick.jinja2` | `product.tco.real_cost_3yr` | `product.tco.real_cost_3yr` (unchanged) |
| `section_4_tco_deep_dive.jinja2` | `product.tco.purchase_price_avg` | `product.tco.purchase_price` |
| `section_4_tco_deep_dive.jinja2` | `product.tco.resale_value_2yr` | `product.tco.resale_price` |

> Part B template changes are minor (field rename only) and can be done alongside A4 code changes.

---

## 7. Blog Expression Rule

A4 export에 포함된 `resale_price`를 Part B가 블로그로 렌더링할 때:

**사용하지 않을 표현:** "3년 뒤 중고가", "2년 후 예상 잔존가"

**사용할 표현:** "중고 매각 시 예상 회수액", "중고 환급 예상액"

이유: `resale_price`는 미래 예측이 아니라 현재 중고 시세 기반 추정값이다.

---

*Document version: 1.0*
*Author: Lead*