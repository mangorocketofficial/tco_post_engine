# TCO-Driven Affiliate Marketing Automation System

## Development Plan v1.0

---

## Executive Summary

This project builds an **automated affiliate marketing content pipeline** that differentiates from generic product comparison blogs by grounding every recommendation in **real TCO (Total Cost of Ownership) data**.

The system collects pricing, resale, and repair data from Korean e-commerce platforms and communities, processes it into structured TCO metrics, and generates high-conversion affiliate blog posts using a proven content structure template.

### Core Thesis

> Most affiliate blogs compare specs. We compare **what you actually pay over 3 years** — and prove it with data no one else has.

### System Architecture (High Level)

```
┌─────────────────────────────────────────────────────────┐
│                    PART A: Data Engine                   │
│                                                         │
│  [Scrapers]          [Processors]        [Storage]      │
│  ├─ Danawa/Coupang   ├─ Price tracker    ├─ Raw DB     │
│  ├─ Danggeun/Bunjang  ├─ GPT classifier  ├─ TCO DB    │
│  └─ Communities      └─ TCO calculator   └─ API        │
│                                                         │
└──────────────────────────┬──────────────────────────────┘
                           │ TCO Data API
┌──────────────────────────▼──────────────────────────────┐
│                  PART B: Content Engine                  │
│                                                         │
│  [Template]          [Generator]         [Analytics]    │
│  ├─ Blog structure   ├─ GPT writer       ├─ Stats      │
│  ├─ TCO tables       ├─ CTA injector     │  Dashboard  │
│  └─ FAQ builder      └─ SEO optimizer    │  (existing) │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## TCO Framework

### Quantitative Metrics (3 items — displayed as comparison table)

| # | Metric | Source | Unit |
|---|--------|--------|------|
| Q1 | **Initial Purchase Price** | Danawa, Coupang price history | KRW |
| Q2 | **Resale Value** | Danggeun, Bunjang actual transactions | KRW (negative = value recovered) |
| Q3 | **Repair Cost (Expected)** | Community posts: repair/AS/breakdown keywords | KRW (probability-weighted) |

**TCO Formula:**
```
Real Cost (3yr) = Q1 + Q3 − Q2
```

### Qualitative Metrics (2 items — displayed as experience comparison)

| # | Metric | Source | Unit |
|---|--------|--------|------|
| S1 | **AS Turnaround Time** | Community AS review posts | Days (avg) |
| S2 | **Maintenance Time Cost** | Official specs + user reports | Minutes/month |

**Disclosure format:**
> "국내 주요 커뮤니티 리뷰 데이터 N건을 자체 분석한 결과"

---

## PART A: Data Collection Engine

### A1. Purpose

Automatically collect, process, and store the 5 TCO data points for any given product category. The engine must be **category-agnostic** — swap the product keyword and the same pipeline works for robot vacuums, air purifiers, dryers, dishwashers, etc.

### A2. Module Breakdown

#### A2-1. Price Tracker (`price-tracker`)

**Objective:** Track initial purchase price history over 3–6 months.

| Item | Detail |
|------|--------|
| **Sources** | Danawa (primary), Coupang (secondary), Naver Shopping |
| **Data points** | Product name, current price, lowest price, avg price (30/90/180d), sale event dates |
| **Frequency** | Daily scrape, stored as time-series |
| **Output** | `{ product_id, date, price, source, is_sale }` |
| **Tech** | Python + requests/playwright, rotating proxies |

**Key implementation notes:**
- Danawa has semi-structured product pages; parse price history chart data
- Coupang prices fluctuate intraday; capture at fixed time (e.g., 09:00 KST)
- Store raw + processed: raw HTML cached for audit, processed prices in DB

#### A2-2. Resale Value Tracker (`resale-tracker`)

**Objective:** Track actual resale transaction prices by product age.

| Item | Detail |
|------|--------|
| **Sources** | Danggeun Market, Bunjang |
| **Data points** | Product name, sale price, listing date, product age (estimated from release date), condition |
| **Frequency** | Weekly scrape |
| **Output** | `{ product_id, platform, sale_price, months_since_release, condition }` |
| **Tech** | Python + playwright (both are JS-heavy SPAs) |

**Key implementation notes:**
- Filter for completed sales only (not active listings)
- Estimate product age: `listing_date − product_release_date`
- Build **price retention curve**: `resale_price / original_price` at 6mo, 12mo, 18mo, 24mo
- Need to handle variant matching (e.g., "로보락 Q Revo S 풀세트" vs "로보락 Q Revo S 본체만")

#### A2-3. Repair & AS Analyzer (`repair-analyzer`)

**Objective:** Extract repair cost and AS turnaround data from community posts.

| Item | Detail |
|------|--------|
| **Sources** | Ppomppu, Clien, Naver Cafe (major appliance cafes) |
| **Keywords** | `{product_name} + [수리, AS, 고장, 서비스센터, 교체, 부품]` |
| **Data points** | Product name, failure type, repair cost, AS duration (days), sentiment |
| **Frequency** | Weekly scrape |
| **Output** | `{ product_id, failure_type, repair_cost, as_days, source_url, date }` |
| **Tech** | Python scraper + GPT API for extraction |

**Key implementation notes:**
- Community posts are unstructured text → use GPT API to extract:
  - `repair_cost`: numeric KRW amount mentioned
  - `as_days`: number of days from send to return
  - `failure_type`: categorize (sensor, motor, software, battery, etc.)
  - `sentiment`: positive/negative/neutral about AS experience
- Calculate **expected repair cost**: `Σ(repair_cost × probability_of_failure_type)`
- Calculate **avg AS turnaround**: mean days across all reports

#### A2-4. Maintenance Time Calculator (`maintenance-calc`)

**Objective:** Estimate monthly time cost for each product.

| Item | Detail |
|------|--------|
| **Sources** | Official product manuals, official brand websites, user reports |
| **Data points** | Maintenance task, frequency, estimated time per task |
| **Output** | `{ product_id, task, frequency_per_month, minutes_per_task, total_monthly_minutes }` |

**Key implementation notes:**
- This is partially manual at setup (reading manuals), partially automated (user reports)
- Standard tasks: tray cleaning, filter replacement, brush cleaning, water tank refill, station cleaning
- Compare: "auto-clean station" (0 min) vs "manual tray wash" (15 min/week = 60 min/month)
- Output: monthly minutes → 3-year total hours

### A3. Data Processing & Storage

#### TCO Calculator (`tco-engine`)

```python
# Core calculation
tco_3yr = {
    "purchase_price": avg_price_from_tracker,           # Q1
    "resale_value": estimated_resale_at_24mo,            # Q2
    "repair_cost": expected_repair_cost,                 # Q3
    "real_cost": Q1 + Q3 - Q2,                          # Quantitative TCO
    "as_turnaround_days": avg_as_days,                   # S1
    "monthly_maintenance_minutes": total_monthly_min,    # S2
}
```

#### Storage Schema

```
products
├── id, name, brand, category, release_date
├── prices[] (time-series)
├── resale_transactions[]
├── repair_reports[]
├── maintenance_tasks[]
└── tco_summary (calculated, refreshed weekly)
```

**Tech:** SQLite for MVP → PostgreSQL for scale. JSON export for Part B consumption.

### A4. Category Expansion Strategy

The pipeline is parameterized by:
1. **Product list** (name, brand, release date)
2. **Community keyword map** (repair/AS terms per category)
3. **Maintenance task template** (tasks differ by category)

To add a new category (e.g., air purifiers):
1. Define product list
2. Update keyword map (filter replacement, noise complaints, etc.)
3. Define maintenance tasks (filter change frequency, etc.)
4. Run pipeline → TCO data ready

---

## PART B: Content Engine

### B1. Purpose

Automatically generate high-conversion affiliate blog posts using the TCO data from Part A, following a proven content structure template. Integrate post performance tracking with the existing MangoRocket stats dashboard.

### B2. Blog Structure Template

Based on the analyzed reference post, the template follows this exact flow:

```
[SECTION 0] Hook — 1-min Summary (5 lines)
  → Situation-based conclusions (3 picks)
  → Video CTA (if applicable)

[SECTION 1] Credibility — Why Trust This (8 lines)
  → "자체 분석 N건" data authority claim
  → Analysis scope: 5 verification areas

[SECTION 2] Criteria Framing — What to Look For (20 lines)
  → 2-1. Myth-busting (spec ≠ experience)
  → 2-2. Real differentiator for Korean homes
  → 2-3. "Your home type" decision fork

[SECTION 3] Recommendation Table — Quick Pick (10 lines)
  → 3-column comparison table
  → CTA link per product

[SECTION 4] Detailed Evidence — Data-Backed Deep Dive (30 lines)
  → 4-1~3. Per-product: recommend/avoid + CTA
  → 4-4. TCO comparison table (QUANTITATIVE)
  → 4-5. Experience comparison table (QUALITATIVE) ← NEW vs reference

[SECTION 5] Action Trigger — Why Check Now (5 lines)
  → Price volatility mention
  → Coupang Partners disclosure

[SECTION 6] FAQ — Objection Handling (20 lines)
  → 5 questions (NOT repeating main content)
  → SEO long-tail keyword targets
```

**Key improvements over reference post:**
- Section 4-4 TCO table now has 6–7 rows with real data (not 3 vague rows)
- Section 4-5 adds qualitative comparison (AS days, maintenance time)
- FAQ covers genuinely new questions (not section 2 rehash)
- CTA wording is unified across all products

### B3. Content Generation Pipeline

#### B3-1. Template Engine (`template-engine`)

**Objective:** Define the blog structure as a parameterized template.

| Item | Detail |
|------|--------|
| **Input** | TCO data (from Part A), product category, product list |
| **Template format** | Markdown with variable slots |
| **Variables** | `{product_name}`, `{tco_table}`, `{qualitative_table}`, `{recommendation}`, `{faq}` |
| **Output** | Structured prompt payload for GPT API |

#### B3-2. GPT Writer (`content-writer`)

**Objective:** Generate natural Korean blog content from structured data + template.

| Item | Detail |
|------|--------|
| **Model** | GPT-4o (or Claude API) |
| **System prompt** | Blog tone guide + structure enforcement + data insertion rules |
| **Input** | Template with filled data slots |
| **Output** | Complete blog post in Korean markdown |
| **Post-processing** | CTA link injection, affiliate tag insertion, image placeholder |

**Key implementation notes:**
- The writer does NOT fabricate data — all numbers come from Part A
- Writer focuses on: narrative flow, tone, transitions, myth-busting framing
- Generate 2–3 FAQ items dynamically based on community pain points from Part A repair data
- SEO: inject long-tail keywords in H2/H3 headings

#### B3-3. CTA & Affiliate Manager (`cta-manager`)

**Objective:** Manage affiliate links and CTA placement.

| Item | Detail |
|------|--------|
| **Link storage** | Product → affiliate URL mapping (Coupang Partners) |
| **Placement rules** | 1 CTA per product in Section 3, 1 in Section 4, 1 in Section 5 |
| **Link format** | Unified wording (e.g., "최저가 확인하기") |
| **Tracking** | UTM parameters per section for click attribution |

### B4. Analytics Integration

#### B4-1. Stats Dashboard Connection (`stats-connector`)
Project path: 
C:\Users\User\Desktop\project\mangorocket_universe\mangorocket-stats\

**Objective:** Push post performance data to the existing MangoRocket stats dashboard.

| Item | Detail |
|------|--------|
| **Existing system** | `mangorocket-stats` (GitHub repo) |

| **Metrics to track** | Page views, bounce rate, avg time on page, CTA click rate, conversion rate |
| **Integration method** | API push or shared DB (TBD after repo review) |
| **Dashboard additions** | Per-post TCO content performance panel |

#### B4-2. Content Performance Feedback Loop

```
Post published → Analytics collected (7/14/30 days)
        ↓
Performance scored:
  - High conversion → Template reinforced
  - Low time-on-page → Section 2 (criteria) needs work
  - Low CTA clicks → Section 3/4 table or CTA wording adjusted
        ↓
Template parameters updated for next generation
```

**Key metrics per section:**
| Section | Success Metric |
|---------|---------------|
| 0 (Hook) | Bounce rate < 40% |
| 2 (Criteria) | Scroll depth past section 2 > 60% |
| 3 (Table) | CTA click rate |
| 4 (TCO) | Time on section > 30s |
| 6 (FAQ) | Exit rate (lower = better) |

### B5. Publishing Pipeline

```
GPT Writer output (markdown)
        ↓
Post-processing:
  - Inject affiliate links
  - Add UTM tracking
  - Insert image placeholders
  - Apply SEO meta tags
        ↓
Export formats:
  - Naver Blog (HTML)
  - Tistory (markdown)
  - WordPress (if applicable)
        ↓
Schedule & publish via platform API
        ↓
Analytics tracking begins
```

---

## Development Phases

### Phase 1: MVP (Weeks 1–3)

**Goal:** One category (robot vacuums), one complete pipeline run.

| Week | Part A | Part B |
|------|--------|--------|
| 1 | Price tracker (Danawa) + Resale tracker (Danggeun) | Blog template finalized in markdown |
| 2 | Repair analyzer (Ppomppu/Clien) + Maintenance calc | GPT writer prompt engineering + test |
| 3 | TCO calculator + JSON export | End-to-end: data → template → published post |

**MVP Deliverable:** One published robot vacuum TCO comparison post with real data.

### Phase 2: Automation (Weeks 4–5)

| Task | Detail |
|------|--------|
| Scheduled scraping | Cron jobs for daily/weekly data collection |
| Auto-refresh TCO | Weekly recalculation when new data arrives |
| Stats integration | Connect to mangorocket-stats dashboard |
| Multi-product | Add 3–5 more products per category |

### Phase 3: Scale (Weeks 6–8)

| Task | Detail |
|------|--------|
| Category expansion | Air purifiers, dryers, dishwashers |
| Template variants | A/B test different section orders |
| Performance loop | Auto-adjust templates based on analytics |
| CTA optimization | Dynamic link selection based on conversion data |

---

## Tech Stack Summary

| Component | Technology |
|-----------|-----------|
| Scraping | Python (requests, playwright, BeautifulSoup) |
| NLP/Extraction | GPT-4o API (structured output mode) |
| Storage | SQLite (MVP) → PostgreSQL |
| TCO Engine | Python |
| Template Engine | Python (Jinja2) |
| Content Writer | GPT-4o / Claude API |
| Publishing | Platform APIs (Naver, Tistory) |
| Analytics | mangorocket-stats (existing) |
| Orchestration | Python + cron (MVP) → Airflow or n8n |

---

## Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Scraping blocked by platform | Data collection stops | Rotating proxies, rate limiting, headless browser fingerprint rotation |
| Community data too sparse for niche products | TCO accuracy drops | Set minimum N threshold (e.g., 30 posts); supplement with manual sampling |
| GPT hallucination in blog content | False claims published | All data injected from Part A; GPT only writes narrative, never invents numbers |
| Affiliate link policy changes | Revenue loss | Abstract CTA manager; swap affiliate networks without rewriting posts |
| Price data lag | Outdated recommendations | Daily price refresh; add "last updated" timestamp to posts |

---

## Success Metrics

| Metric | Target (Phase 1) | Target (Phase 3) |
|--------|------------------|------------------|
| Data collection coverage | 3 products, 1 category | 15+ products, 4+ categories |
| TCO data freshness | Weekly refresh | Daily price, weekly community |
| Post generation time | < 30 min (semi-auto) | < 5 min (fully auto) |
| Post conversion rate | Baseline measurement | 2× baseline |
| Monthly affiliate revenue | Baseline measurement | Incremental growth tracked |

---

*Document version: 1.0*
*Last updated: 2026-02-07*
*Author: MangoRocket × Claude*