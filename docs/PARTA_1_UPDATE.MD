# DEV REQUEST: A1 Price Tracker — Data Quality & Targeted Scraping

> **Priority:** 🔴 Critical — corrupted price data propagates to A4 TCO calculation and Part B blog output
> **Scope:** `src/part_a/price_tracker/`
> **Depends on:** A0 slot framework fix (A0 JSON with product names required as input)
> **Date:** 2026-02-08

---

## 1. Problem Statement

### Three distinct failures observed in test run (전기면도기)

**Failure 1 — Garbage prices parsed from non-price HTML elements:**

```
Product 1 (Schtus KS0273, expected ~26,100원):
  841, 1707, 896, 787원  ← shipping fees, reward points, UI numbers

Product 2 (필립스 면도기, expected ~55,000~130,000원):
  3, 7, 13원             ← coupon percentages or badge counts

Product 3 (브라운 면도기 5, expected ~99,000~150,000원):
  143, 493원             ← review counts or other UI metrics
```

**Failure 2 — Wrong products scraped entirely:**

```
Product 1 JSON contains: 666,440 ~ 700,120원
  → These are air purifier prices (다이슨, LG 퓨리케어), NOT the 26,100원 Schtus shaver.
  → The keyword search returned unrelated products and all were scraped indiscriminately.

Product names in TCO export:
  - "다이슨 빅+콰이엇 포름알데히드 BP04VS검색하기VS검색 도움말추천상품과스펙비교하세요.닫기"
  - "필터나라 위닉스 타워 엣지 호환용 일체형필터VS검색하기VS검색 도움말추천상품과스펙비교하세요.닫기"
  → Air purifier filter products with HTML button text embedded in name.
```

**Failure 3 — Zero filtering between parse and save:**

All garbage prices (3원, 7원, 666,440원) were written directly to DB and JSON. The A4 TCO engine then read the entire DB and exported 34 contaminated product records instead of the 3 products A0 selected.

### Impact

The TCO export (`tco_전기면도기.json`) is completely unusable:
- 34 products instead of 3
- Product names contain HTML artifacts
- Prices range from 2원 to 997,930원 for what should be electric shavers
- All `resale_curve`, `repair_stats`, `maintenance_tasks` fields are empty (A2/A3 data not merged)

---

## 2. Root Cause Analysis

### 2.1 Garbage prices — `_parse_price()` is too permissive

Location: `danawa_scraper.py :: _parse_price()`

```python
@staticmethod
def _parse_price(text: str) -> int:
    price_part = re.split(r"[원~(]", text)[0]
    digits = re.sub(r"[^\d]", "", price_part)
    return int(digits) if digits else 0
```

This function accepts ANY string containing digits as a valid price. When Danawa's `div.sell-price` selector captures shipping fees ("3,000원"), reward points ("787P"), coupon badges ("13%할인"), or review counts, they all parse into small integers.

Additionally, **Strategy 3** in `get_product_prices()` is a dangerous fallback:

```python
# Strategy 3: Any element with price-like number in price containers
if not records:
    for el in soup.select("div.price_unit, div.sell-price"):
        price = self._parse_price(el.get_text(strip=True))
```

This grabs text from broad container divs and treats anything numeric as a price.

### 2.2 Wrong products — keyword search with no product matching

Location: `main.py :: main()`

```python
products = scraper.search_products(args.keyword, args.max_results)  # keyword → N results
for product in products:
    records = scraper.get_product_prices(product["product_code"])    # scrape ALL of them
    all_records.extend(records)                                      # mix into one list
```

The flow is: search keyword → take top 5 search results → scrape all their prices → dump into one JSON. There is no validation that the search results actually match the intended product.

When `--keyword "Schtus 휴대용 전기 면도기 3in1"` is passed, Danawa may return completely different products in its search results (air purifiers, accessories, etc.). All get scraped and mixed together.

### 2.3 Product name HTML contamination

Location: `danawa_scraper.py :: get_product_prices()`

```python
title_el = (
    soup.select_one(".top-summary .text__title")
    or soup.select_one(".prod_tit, #blog_content .tit")
)
product_name = title_el.get_text(strip=True) if title_el else f"product_{product_code}"
```

`get_text(strip=True)` on the title element captures adjacent button text ("VS검색하기", "VS검색 도움말", "추천상품과스펙비교하세요", "닫기") because these elements are nested inside or adjacent to the title container in Danawa's current HTML structure.

### 2.4 No filter between parse and storage

Location: `danawa_scraper.py :: save_prices_to_db()`

```python
for record in records:
    product_id = self._ensure_product(conn, record)
    conn.execute("INSERT INTO prices ...", (product_id, record.date, record.price, ...))
```

Every record is inserted regardless of price value. A record with price=3 is saved alongside price=113,000.

---

## 3. Required Changes

### 3.1 Three-Layer Price Filtering Pipeline

Implement filtering at three distinct levels, each catching different error types:

#### Layer 1: Absolute Floor (at parse time)

**Where:** `_parse_price()` return value, or a wrapper applied immediately after.

**Rule:** If parsed value < 1,000 (원), treat as 0 (not a valid product price).

**Rationale:** No consumer product tracked by this system costs less than 1,000원. Values below this threshold are always parsing artifacts (shipping fees, coupon %, badge counts, review numbers).

**Scope:** This is a universal rule — applies to all categories, all products.

#### Layer 2: Statistical Outlier Removal (at collection time)

**Where:** New filtering function called at the end of `get_product_prices()`, before returning the records list.

**Method:** IQR-based outlier removal on the collected price list for a single product.

```
Given prices for one product: [75890, 79012, 79810, 80620, 80990, 83730, 88260, 89100, 113000, 113480, ...]
  Q1 = 25th percentile
  Q3 = 75th percentile
  IQR = Q3 - Q1
  Keep only: Q1 - 1.5×IQR ≤ price ≤ Q3 + 1.5×IQR
```

**Important:** This filter runs AFTER Layer 1 (so sub-1000원 values are already gone) and operates on the prices of a single product_code, not across products.

**Edge case:** If fewer than 4 price records remain after Layer 1, skip IQR filtering (not enough data points) and keep all remaining records.

#### Layer 3: A0 Reference Price Cross-Check (at pipeline level)

**Where:** `main.py` or a new orchestration function that receives A0 data.

**Rule:** If A0 provides a reference price for the product, discard any price record where:
- `price < reference_price × 0.3` (less than 30% of A0 price)
- `price > reference_price × 3.0` (more than 300% of A0 price)

**Rationale:** A0 collects Naver Shopping `lprice` which is a reasonable market price estimate. A Danawa price 10× higher means we scraped a different product. A price 70%+ lower means we parsed a non-price element.

**Fallback:** If A0 provides no reference price (e.g., A0.1 blog-only product with `price=0`), skip Layer 3 for that product and rely on Layers 1+2 only.

### 3.2 Targeted Product Scraping (Replace Keyword Dump)

#### Current flow (broken):

```
CLI: --keyword "필립스 면도기"
  → search_products("필립스 면도기", max_results=5)
  → 5 different Danawa products returned (some unrelated)
  → scrape ALL 5 → mix prices into one JSON
```

#### Required flow:

```
CLI: --a0-data data/processed/a0_selected_전기면도기.json
  → Read 3 product names from A0 JSON
  → For each product:
      1. search_products(product_name, max_results=5)
      2. Score search results by name similarity to A0 product name
      3. Select the BEST MATCH (highest similarity, above threshold)
      4. get_product_prices(best_match.product_code)
      5. Apply 3-layer filtering
      6. Output as separate per-product price record
```

**Name similarity matching:** Use a simple approach — count overlapping tokens (split by space) between A0 product name and Danawa search result name. Require at least 50% token overlap to consider a match. If no result meets the threshold, log a warning and skip (do not scrape random products).

**CLI changes to `main.py`:**

Add a new argument: `--a0-data <path>` that reads the A0 JSON file and iterates over `final_products[]`. This becomes the primary mode for pipeline execution. The existing `--keyword` mode can remain for manual/debug use but should NOT be used in the RUNBOOK pipeline.

**Output format change:**

Currently all prices dump into one flat JSON array. Change to per-product structured output:

```json
{
  "category": "전기면도기",
  "collected_at": "ISO 8601",
  "products": [
    {
      "product_name": "A0에서 받은 원본 제품명",
      "danawa_product_code": "매칭된 다나와 코드",
      "danawa_product_name": "다나와에서 찾은 제품명",
      "match_score": 0.85,
      "purchase_price_avg": 0,
      "purchase_price_min": 0,
      "price_records": [ ... ],
      "records_before_filter": 14,
      "records_after_filter": 10,
      "filter_log": "Layer 1: removed 3, Layer 2: removed 1, Layer 3: removed 0"
    }
  ]
}
```

This structured output lets A2 read `purchase_price_avg` directly, and lets A4 consume clean per-product data.

### 3.3 Product Name Cleaning

**Where:** New utility function, called in both `_parse_search_item()` and `get_product_prices()` wherever `product_name` is assigned.

**What to strip:**

| Pattern | Example | Source |
|---------|---------|--------|
| "VS검색하기" | "BP04VS검색하기VS검색" | Danawa compare button |
| "VS검색 도움말" | | Danawa tooltip |
| "추천상품과스펙비교하세요" | | Danawa suggestion banner |
| "닫기" (at end of string) | | Danawa modal close button |
| "(일반구매)" / "(공식판매)" | "AS305DWWA (일반구매)" | Danawa purchase type label |

**Implementation:** A single regex-based cleaner function that strips known Danawa UI text patterns from product names. This function should be applied to ALL product names at parse time, before they enter any data model or DB.

### 3.4 RUNBOOK Integration

Update `RUNBOOKV2.md` Step A1 to reflect the new flow:

**Before:**
```bash
python -m src.part_a.price_tracker.main --keyword "{PRODUCT_1}" --save-db --output ...
python -m src.part_a.price_tracker.main --keyword "{PRODUCT_2}" --save-db --output ...
python -m src.part_a.price_tracker.main --keyword "{PRODUCT_3}" --save-db --output ...
```

**After:**
```bash
python -m src.part_a.price_tracker.main \
  --a0-data data/processed/a0_selected_{CATEGORY}.json \
  --save-db \
  --output data/processed/a1_prices_{CATEGORY}.json
```

Single invocation, reads all 3 products from A0, outputs one structured JSON with per-product pricing.

---

## 4. What NOT to Change

- **`get_price_history()` and `_parse_price_history_response()`** — The AJAX price history endpoint parsing is a separate concern. Only apply Layer 1 (absolute floor) there; do not restructure.
- **`HTTPClient` and caching** — Raw HTML caching under `data/raw_html/` is working correctly and is essential for audit. Do not change.
- **`_parse_price()` core logic** — The regex split at `[원~(]` is correct for Korean price text. Only add the floor threshold; do not rewrite the parsing approach.
- **DB schema** — The `products` and `prices` tables are fine. The issue is what gets inserted, not the schema.

---

## 5. Test Requirements

### Existing tests to check

- `tests/part_a/test_price_tracker.py` — verify existing tests still pass after adding filters.

### New test scenarios

| Scenario | Input | Expected |
|----------|-------|----------|
| Layer 1: sub-1000 filtering | `[3, 7, 13, 787, 841, 75890, 79810]` | `[75890, 79810]` |
| Layer 2: IQR outlier removal | `[75890, 79810, 80620, 80990, 83730, 389000]` | `389000 removed` |
| Layer 3: A0 cross-check | A0 price=26100, scraped=666440 | `666440 removed (>3× reference)` |
| All layers combined | Full product1 raw data from test run | Only prices in 20,000~80,000 range survive |
| Edge: fewer than 4 records | `[75890, 79810]` after Layer 1 | IQR skipped, both kept |
| Edge: A0 price=0 | A0.1 product with no price | Layer 3 skipped, Layers 1+2 only |
| Name cleaning | `"다이슨 BP04VS검색하기VS검색 도움말추천상품과스펙비교하세요.닫기"` | `"다이슨 BP04"` |
| Targeted scraping | A0 product="브라운 면도기 5", search returns 5 results | Best name-match selected, others ignored |
| No match found | A0 product="존재하지않는제품XYZ", search returns 0 | Warning logged, no data (not random scrape) |

### Integration test

Run the full A0 → A1 pipeline with `--keyword "전기면도기"`:
1. A0 selects 3 products with slot labels
2. A1 reads A0 JSON, finds matching Danawa products, collects clean prices
3. Verify: each product has 5+ valid price records, no sub-1000 values, no cross-product contamination

---

## 6. Downstream Impact

| Consumer | What changes |
|----------|-------------|
| **A2 (중고 시세)** | A1 now outputs `purchase_price_avg` per product → A2 can read this as input instead of estimating independently. RUNBOOK A2 step should reference A1 output. |
| **A4 (TCO Engine)** | A1 output changes from flat price array to structured per-product JSON. A4's DB reader or JSON reader needs to handle the new format. |
| **DB consumers** | `products` table will have clean names (no HTML artifacts). `prices` table will have only validated prices. Any existing contaminated data from test runs should be purged. |

---

## 7. File Change Summary

| File | Change type | What |
|------|------------|------|
| `danawa_scraper.py` | Modify | Add absolute floor to `_parse_price()`, add IQR filter function, add name cleaning function, apply filters in `get_product_prices()` |
| `main.py` | Modify | Add `--a0-data` argument, implement targeted per-product scraping flow, output structured JSON |
| `models.py` (price_tracker) | Possibly modify | Add fields for match_score, filter_log if needed in PriceRecord or ProductPriceSummary |
| `RUNBOOKV2.md` | Update | Step A1 command changes from 3× keyword calls to 1× a0-data call |

No new files required. All changes are modifications to existing code.

---

*Document version: 1.0*
*Author: Lead*
*Depends on: A0_slot_framework_fix.md*
*Relates to: RUNBOOKV2.md Step A1, A4 TCO Engine integration*