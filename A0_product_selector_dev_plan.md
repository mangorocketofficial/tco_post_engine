# Module A-0: Product Selector

## Automated Product Selection Engine for TCO Comparison Pipeline

---

## Overview

This module sits **before** the existing Part A (Data Engine) and answers the critical question:

> "Which 3 products should we compare?"

Instead of relying on editorial intuition, the Product Selector uses real market data to identify the optimal 3-product comparison set for any given product category. The selection is grounded in consumer decision architecture: **Stability / Balance / Value** — a framework that maps to how real buyers think about high-ticket electronics.

### Position in Pipeline

```
[A-0: Product Selector]  ← THIS MODULE
        ↓
  3 products selected
        ↓
[A-1~4: TCO Data Engine]
        ↓
[B: Content Engine]
```

---

## Consumer Decision Architecture

### The 3-Slot Framework

When consumers compare high-ticket electronics (300K–1M+ KRW), their mental model almost always falls into three archetypes:

| Slot | Consumer Mindset | Product Profile |
|------|-----------------|-----------------|
| **Stability** | "I'll pay more if it just works without problems" | Lowest complaint rate, highest resale value, premium brand trust |
| **Balance** | "Best overall package for the money" | Highest search volume, most reviews, strongest community buzz |
| **Value** | "Minimum spend for maximum utility" | Lowest price tier with competitive features, high sales volume |

**Why exactly 3?**
- 2 products → binary choice, flat content, low engagement
- 3 products → natural comparison triangle, clear differentiation, highest conversion
- 4+ products → choice paralysis, decision fatigue, lower conversion

This 3-slot structure is **category-agnostic**. It works for robot vacuums, air purifiers, dryers, dishwashers, monitors, keyboards — any category where price tiers and reliability variance exist.

---

## Data Collection Layer

### Source 1: Sales Ranking Aggregation

**Objective:** Identify the 10–15 products that are actually selling right now.

| Source | Data Point | Role |
|--------|-----------|------|
| Naver Shopping Best | Ranking position, review count | Market validation |
| Danawa Popular Ranking | Price, ranking, spec summary | Price positioning |
| Coupang Best Seller | Sales rank, review count, rating | Purchase volume proxy |

**Cross-reference logic:**
```
For each product in category:
  naver_rank = position in Naver Shopping Best
  danawa_rank = position in Danawa Popular
  coupang_rank = position in Coupang Best Seller

  presence_score = count of platforms where product appears in top 20
  avg_rank = mean(naver_rank, danawa_rank, coupang_rank)

Filter: presence_score >= 2  →  Candidate pool (10–15 products)
```

Products appearing on only 1 platform are likely niche or promotional anomalies — excluded.

### Source 2: Search Interest

**Objective:** Measure real consumer interest level per product.

| Source | Data Point | Access |
|--------|-----------|--------|
| Naver DataLab API | Relative search volume (30/90 day) | Public API (legal) |
| Google Trends | Relative interest | Public API |

**Usage:**
- Primary ranking signal for the **Balance** slot
- Trending products (30d > 90d average) flagged as "rising" — potential fresh picks

### Source 3: Community Sentiment

**Objective:** Measure complaint rate and satisfaction signals.

| Source | Keywords | Data Point |
|--------|----------|-----------|
| Ppomppu | `{product} + [불만, 후회, 실망, 반품]` | Negative post count |
| Clien | `{product} + [고장, AS, 수리, 오류]` | Failure/repair post count |
| Naver Cafe | `{product} + [추천, 만족, 최고, 잘샀다]` | Positive post count |

**Sentiment ratio:**
```
complaint_rate = negative_posts / total_posts
satisfaction_rate = positive_posts / total_posts
```

- Primary ranking signal for the **Stability** slot (lowest complaint_rate wins)
- Secondary signal for **Value** slot (high satisfaction at low price = strong value)

### Source 4: Price Positioning

**Objective:** Classify each product into price tiers.

| Source | Data Point |
|--------|-----------|
| Danawa | Current lowest price, average price (90d) |
| Coupang | Current price, sale status |

**Tier classification:**
```
products_sorted_by_price = sort(candidates, key=avg_price)

Premium tier  = top 30% by price
Mid tier      = middle 40% by price
Budget tier   = bottom 30% by price
```

### Source 5: Resale Value (Quick Check)

**Objective:** Early signal for value retention — full analysis happens in Part A.

| Source | Data Point |
|--------|-----------|
| Danggeun Market | Recent listing prices for used units |

**Quick ratio:**
```
resale_ratio = avg_used_price / avg_new_price
```

- High resale_ratio → strong brand trust → Stability slot signal
- Low resale_ratio → fast depreciation → risk flag

---

## Scoring & Selection Algorithm

### Step 1: Score Each Candidate

Each candidate product receives scores across 5 dimensions:

| Dimension | Weight | Calculation |
|-----------|--------|-------------|
| **Sales Presence** | 20% | `presence_score / max_presence_score` |
| **Search Interest** | 25% | `search_volume / max_search_volume` |
| **Sentiment** | 25% | `satisfaction_rate − complaint_rate` (normalized) |
| **Price Position** | 15% | Tier classification (premium/mid/budget) |
| **Resale Retention** | 15% | `resale_ratio / max_resale_ratio` |

### Step 2: Slot Assignment

```python
def select_products(candidates, scores):

    # STABILITY SLOT
    # Filter: Premium or Mid tier only
    # Rank by: Sentiment (highest) + Resale Retention (highest)
    stability_pool = [c for c in candidates if c.price_tier in ['premium', 'mid']]
    stability_pick = max(stability_pool, key=lambda c:
        scores[c].sentiment * 0.6 + scores[c].resale_retention * 0.4
    )

    # BALANCE SLOT
    # Exclude: stability_pick
    # Rank by: Search Interest (highest) + Sales Presence (highest)
    balance_pool = [c for c in candidates if c != stability_pick]
    balance_pick = max(balance_pool, key=lambda c:
        scores[c].search_interest * 0.5 + scores[c].sales_presence * 0.3 + scores[c].sentiment * 0.2
    )

    # VALUE SLOT
    # Exclude: stability_pick, balance_pick
    # Filter: Mid or Budget tier only
    # Rank by: Sales Presence (highest) at lowest price tier
    value_pool = [c for c in candidates
        if c != stability_pick
        and c != balance_pick
        and c.price_tier in ['mid', 'budget']
    ]
    value_pick = max(value_pool, key=lambda c:
        scores[c].sales_presence * 0.4 + (1 - scores[c].price_normalized) * 0.4 + scores[c].sentiment * 0.2
    )

    return {
        'stability': stability_pick,
        'balance': balance_pick,
        'value': value_pick
    }
```

### Step 3: Validation Checks

Before finalizing the 3 picks, run these sanity checks:

| Check | Rule | Fallback |
|-------|------|----------|
| **Brand diversity** | All 3 should be different brands | If 2 share a brand, swap the lower-scored one for next-best from different brand |
| **Price spread** | Max price should be ≥ 1.3× min price | If too close, selection lacks differentiation — widen by picking from adjacent tier |
| **Data sufficiency** | Each product needs ≥ 20 community posts | If under threshold, flag for manual review or substitute |
| **Recency** | All 3 should be released within last 18 months | Older products deprioritized unless still top-selling |
| **Availability** | All 3 must be currently purchasable | Check Coupang/Naver stock status |

---

## Output Format

The module outputs a JSON payload consumed by Part A:

```json
{
  "category": "robot_vacuum",
  "selection_date": "2026-02-07",
  "data_sources": {
    "sales_rankings": ["naver_shopping", "danawa", "coupang"],
    "search_volume": "naver_datalab",
    "community_sentiment": ["ppomppu", "clien"],
    "price_data": "danawa",
    "resale_check": "danggeun"
  },
  "candidate_pool_size": 12,
  "selected_products": [
    {
      "slot": "stability",
      "name": "로보락 Q Revo S",
      "brand": "Roborock",
      "price_tier": "premium",
      "selection_reasons": [
        "Lowest complaint_rate (0.08) among premium tier",
        "Highest resale_ratio (0.45) in category",
        "Presence on all 3 sales platforms"
      ],
      "scores": {
        "sales_presence": 0.92,
        "search_interest": 0.78,
        "sentiment": 0.91,
        "price_position": "premium",
        "resale_retention": 0.95
      }
    },
    {
      "slot": "balance",
      "name": "드리미 L10s Pro Ultra Heat",
      "brand": "Dreame",
      "price_tier": "premium",
      "selection_reasons": [
        "Highest search volume in category (30d)",
        "Most reviews on Coupang (2,847)",
        "Strong sentiment score with feature-rich positioning"
      ],
      "scores": { "..." : "..." }
    },
    {
      "slot": "value",
      "name": "에코백스 T30 Pro Omni",
      "brand": "Ecovacs",
      "price_tier": "budget",
      "selection_reasons": [
        "Lowest avg price in candidate pool",
        "Top 3 in Coupang Best Seller",
        "High sales presence despite mixed sentiment"
      ],
      "scores": { "..." : "..." }
    }
  ],
  "validation": {
    "brand_diversity": "PASS — 3 unique brands",
    "price_spread": "PASS — 1.46x ratio (650K to 950K)",
    "data_sufficiency": "PASS — min 47 community posts per product",
    "recency": "PASS — all released within 12 months",
    "availability": "PASS — all in stock on Coupang"
  }
}
```

---

## Refresh Strategy

| Trigger | Action |
|---------|--------|
| **Scheduled (monthly)** | Re-run full selection pipeline; if picks change, flag for review |
| **New product launch** | Inject into candidate pool and re-score; may displace existing pick |
| **Pick goes out of stock** | Auto-substitute with next-best in same slot |
| **Sentiment shift** | If complaint_rate doubles in 30 days, flag stability pick for review |

### Change Management

When the selector recommends a product swap:
1. **Auto-generate** new TCO data via Part A
2. **Auto-generate** updated blog post via Part B
3. **Notify** via dashboard alert (mangorocket-stats integration)
4. **Archive** old post or add "updated" banner with new recommendation

---

## Category Expansion

To run this selector on a new category, provide:

```python
category_config = {
    "name": "air_purifier",
    "search_terms": ["공기청정기"],
    "negative_keywords": ["필터 냄새", "소음", "고장", "AS", "반품"],
    "positive_keywords": ["추천", "만족", "조용", "잘샀다"],
    "price_range": {"min": 200000, "max": 800000},  # KRW
    "max_product_age_months": 18,
    "min_community_posts": 20
}
```

Everything else — scoring weights, slot logic, validation checks — remains identical.

---

## Development Estimate

| Task | Effort | Dependency |
|------|--------|-----------|
| Sales ranking scrapers (3 platforms) | 3 days | None |
| Naver DataLab API integration | 1 day | None |
| Community sentiment scraper + GPT classifier | 3 days | GPT API key |
| Price tier classifier | 0.5 day | Sales ranking data |
| Resale quick-check scraper | 1 day | None |
| Scoring algorithm + slot assignment | 1 day | All scrapers |
| Validation checks | 0.5 day | Scoring algorithm |
| JSON output + Part A integration | 0.5 day | Scoring algorithm |
| **Total** | **~10 days** | |

---

## Integration with Main Pipeline

```
[A-0: Product Selector]        ← 10 days
  │
  │  Output: 3 products + metadata JSON
  ▼
[A-1: Price Tracker]           ─┐
[A-2: Resale Tracker]           │
[A-3: Repair Analyzer]          ├─ Part A (existing plan)
[A-4: Maintenance Calculator]  ─┘
  │
  │  Output: TCO data per product
  ▼
[B-1: Template Engine]         ─┐
[B-2: Content Writer]           ├─ Part B (existing plan)
[B-3: CTA Manager]             ─┘
  │
  │  Output: Published blog post
  ▼
[B-4: Stats Dashboard]         ─── mangorocket-stats
```

---

*Module version: 1.0*
*Last updated: 2026-02-07*
*Parent document: TCO-Driven Affiliate Marketing Automation System v1.0*