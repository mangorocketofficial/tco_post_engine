# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TCO-Driven Affiliate Marketing Automation System — collects real TCO (Total Cost of Ownership) data from Korean e-commerce platforms/communities and generates affiliate blog posts grounded in actual cost analysis.

**Core formula:** `Real Cost = Purchase Price + (Annual Consumable Cost × tco_years)` (tech=3yr, pet=2yr)

- **Part A (Data Engine):** Product selection (A0), consumable pricing (A2 WebSearch), review insights (A5 WebSearch) → TCO calculation (A4) → JSON export
- **Part B (Content Engine):** Takes TCO data → generates Korean affiliate blog posts via Claude Code (direct HTML)

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (pytest configured in pyproject.toml with -v --tb=short)
pytest tests/                              # All tests
pytest tests/part_a/                       # Part A tests only
pytest tests/part_b/                       # Part B tests only
pytest tests/integration/                  # Integration tests
pytest tests/part_a/test_price_tracker.py -v   # Single test file

# Run individual modules
python -m src.part_a.price_tracker.main
python -m src.part_a.tco_engine.main --category "로봇청소기" --config config/category_robot_vacuum.yaml --a0-data {a0.json} --a2-data {a2.json} --output {output.json}
# Part B content generation is now handled by Claude Code directly (no CLI entry point)
```

## Architecture & Data Flow

```
A0(Product Selection) → A-CTA(Affiliate Links) → A-IMG(Product Images) → A-VERIFY(CTA/Image Verification) → A2(Consumable WebSearch) → A5(Review WebSearch) → A4(TCO Calculator) → JSON export → Claude Code (Step B + Step C) → PostProcessor → Platform publish
```

### Pipeline Steps

| Step | Type | Description |
|------|------|-------------|
| A0 | Python module | Product selection from Naver Shopping/Danawa |
| A-CTA | Playwright | Affiliate link extraction from Coupang Partners |
| A-IMG | Playwright | Product image extraction from Coupang |
| A-VERIFY | Claude Code Multimodal | CTA link & image verification (visual + WebFetch) |
| A2 | Claude Code WebSearch | Consumable price research per product |
| A5 | Claude Code WebSearch | Review insights + AS reputation |
| A4 | Python module | TCO calculation + JSON export |
| B | Claude Code | Comparison blog post (HTML) |
| C | Claude Code | Individual review posts (HTML) |
| D | Python module | Post-processing + publish |

### Two Config Systems (Important)

Part A and Part B use **different configuration patterns**:
- **Part A:** `src/part_a/common/config.py` — `@dataclass Config` loaded from env vars (`.env`). Uses `Config.database_abs_path` for DB path resolution relative to project root.
- **Part B / Shared:** `src/common/config.py` — Pydantic `Settings` loaded from `config/settings.yaml` with `Settings.load()`. Singleton `settings` instance at module level.

Both load `.env` from project root via `python-dotenv`.

### Part A → Part B Contract

The data boundary between Part A and Part B is a JSON file. Part A exports via `TCOExporter.export_from_files()` → JSON file in `data/exports/` → Claude Code generates HTML directly → `PostProcessor` → publish.

Key flow: `TCOCalculator.calculate_from_files(a0_path, a2_path, tco_years=N)` → `TCOExporter.export_from_files()` → JSON

### Dual Model Layers

Data models are defined in **two places** for historical reasons:
- `src/common/models.py` — Pydantic models (Part A data types + API contract types like `ProductTCOExport`, `TCOCategoryExport`, `ConsumableItem`)
- `src/part_b/template_engine/models.py` — `@dataclass` models for blog post data structure (`BlogPostData`, `Product`, `TCOData`, `ConsumableItem`)

### Database

SQLite with WAL mode and foreign keys enabled. Schema defined in `src/part_a/database/connection.py`. Tables: `products`, `prices`, `product_selections`. Products use auto-increment integer IDs internally, string IDs in exports. Unique constraint on `(name, brand, category)` — supports same product names across different categories.

### Scraping Infrastructure

All scrapers use `src/part_a/common/http_client.py` (`HTTPClient`) which provides rate limiting (token bucket), proxy rotation, retry with backoff, User-Agent rotation, and raw HTML caching under `data/raw_html/`.

### Blog Section Structure

**Step B (비교 글):** 6-section blog format (Section 0–5): hook+credibility → criteria → quick pick → TCO deep dive (소모품 비교표 포함) → checklist → FAQ. HTML is generated directly by Claude Code — no Jinja2 templates.

**Step C (개별 리뷰):** 5-section format (Section 0–4): 한줄 결론 → 구매동기 분석 → 만족/불만 → AS 평판·소모품 관리 → 정리+내부 링크. 제품당 1개, CTA 없음 (SEO 서포트 글). Spec: `Spec stepC individualreview.md`

### Publishing Pipeline

`PublishPipeline` in `src/part_b/publisher/pipeline.py` accepts pre-generated HTML → `PostProcessor` (disclosure, SEO tags) → platform publish (Naver Blog, Tistory).

## Category Configuration

Category configs are YAML files under `config/` (e.g., `category_robot_vacuum.yaml`). Each config includes search terms, price range, keywords, consumable information, and multi-category metadata:

```yaml
# Multi-category fields (optional — defaults to tech)
tco_years: 3               # tech=3, pet=2, baby=1~3 (per category)
domain: "tech"              # "tech" | "pet" | "baby"
subscription_model: false   # GPS trackers, smart litter boxes
multi_unit_label: null      # pet: "마리", tech: null

consumables:
  tco_tier: "essential"  # essential/recommended/optional/none
  tco_label: "3년 소모품 포함 총비용"
  items:
    - name: "필터"
      cycle: "3~6개월"
```

Three domains supported: **tech** (37 categories, 3yr TCO), **pet** (20 categories, 2yr TCO), and **baby** (21 categories, 1-3yr TCO). `Category consumables reference.md`, `Pet category consumables reference.md`, and `Baby_category_consumables_reference.md` provide the master references.

### Multi-Blog Publishing (Supabase)

Each domain publishes to a **separate Supabase project** (different Next.js blog site):
- **tech:** `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` in `.env`
- **pet:** `SUPABASE_PET_URL` + `SUPABASE_PET_SERVICE_KEY` in `.env`
- **baby:** `SUPABASE_BABY_URL` + `SUPABASE_BABY_SERVICE_KEY` in `.env`

Domain is auto-detected from `config/category_*.yaml` → `domain` field → exported in TCO JSON → publisher routes to correct Supabase project. Can also be overridden via `--domain tech|pet` CLI flag.

## Key Design Rules

- **Claude Code as narrator, not data source:** LLM generates narrative and tone; all numbers are injected from Part A. Never fabricate quantitative data.
- **CTA placement:** Exactly 1 CTA per product in Section 2, Section 3, and Section 4.
- **Raw HTML caching:** All scraped HTML is cached for audit; processed data goes to DB.
- **Korean text:** All processing must handle UTF-8 encoding correctly.
- **TCO formula is deterministic:** `real_cost_total = purchase_price + (annual_consumable_cost × tco_years)`. No probability-based estimates. `tco_years` comes from category YAML config.

## Test Fixtures

- `fixtures/sample_tco_data.json` — Sample Part A export (consumable-based) for testing the Part B pipeline
- `fixtures/sample_blog_data.py` — Pre-built `BlogPostData` objects with consumable data
- `tests/conftest.py` — Shared fixtures including `temp_db` (temporary SQLite), `db_conn`, `sample_product_data`, `sample_tco_data`

## Agent Team Development

This project uses a 3-person agent team coordinated via git worktree:

| Role | Branch | Worktree | Scope |
|------|--------|----------|-------|
| Lead | `main` | `TCO_Post_Engine/` | Architecture, coordination, integration tests |
| PartA | `dev/part-a` | `TCO_Post_Engine-partA/` | Data Engine modules |
| PartB | `dev/part-b` | `TCO_Post_Engine-partB/` | Content Engine modules |

- Commit prefixes: `[Lead]`, `[PartA]`, `[PartB]`
- Coordination via `.coordination/` directory (status files, blockers, API contract)
- Merge flow: `dev/part-a` → `main` ← `dev/part-b`
- Full team setup details in `dev_agent.md`
