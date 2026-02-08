# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TCO-Driven Affiliate Marketing Automation System — collects real TCO (Total Cost of Ownership) data from Korean e-commerce platforms/communities and generates affiliate blog posts grounded in actual cost analysis.

**Core formula:** `Real Cost (3yr) = Purchase Price + Expected Repair Cost − Resale Value`

- **Part A (Data Engine):** Scrapes pricing, resale, repair data → processes into structured TCO metrics
- **Part B (Content Engine):** Takes TCO data → generates Korean affiliate blog posts via LLM

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (pytest configured in pyproject.toml with -v --tb=short)
pytest tests/                              # All tests (257 passing)
pytest tests/part_a/                       # Part A tests only
pytest tests/part_b/                       # Part B tests only
pytest tests/integration/                  # Integration tests
pytest tests/part_a/test_price_tracker.py -v   # Single test file

# Run individual modules
python -m src.part_a.price_tracker.main
python -m src.part_a.resale_tracker.main
python -m src.part_a.repair_analyzer.main
python -m src.part_a.tco_engine.main
python -m src.part_b.content_writer.main --category "로봇청소기"
```

## Architecture & Data Flow

```
Part A scrapers → SQLite DB → TCO calculator → JSON export → Part B content writer → Jinja2 render → Platform publish
```

### Two Config Systems (Important)

Part A and Part B use **different configuration patterns**:
- **Part A:** `src/part_a/common/config.py` — `@dataclass Config` loaded from env vars (`.env`). Uses `Config.database_abs_path` for DB path resolution relative to project root.
- **Part B / Shared:** `src/common/config.py` — Pydantic `Settings` loaded from `config/settings.yaml` with `Settings.load()`. Singleton `settings` instance at module level.

Both load `.env` from project root via `python-dotenv`.

### Part A → Part B Contract

The data boundary between Part A and Part B is a JSON file matching the schema in `.coordination/api-contract.json`. Part A exports `TCOCategoryExport` (defined in `src/common/models.py`), Part B consumes it.

Key flow: `TCOCalculator.calculate_for_product()` → `TCOExporter.export_category()` → JSON file in `data/exports/` → `ContentWriter.generate(tco_data_path=...)` → `BlogPostData` → `TemplateRenderer.render()` → markdown → `PostProcessor` → HTML/publish.

### Dual Model Layers

Data models are defined in **two places** for historical reasons:
- `src/common/models.py` — Pydantic models (Part A data types + API contract types like `ProductTCOExport`, `TCOCategoryExport`)
- `src/part_b/template_engine/models.py` — `@dataclass` models for template rendering (`BlogPostData`, `Product`, `TCOData`)

The `ContentWriter` bridges these: it reads Part A's JSON export and builds Part B's `@dataclass` objects.

### Database

SQLite with WAL mode and foreign keys enabled. Schema defined in `src/part_a/database/connection.py`. Tables: `products`, `prices`, `resale_transactions`, `repair_reports`, `maintenance_tasks`, `tco_summaries`. Products use auto-increment integer IDs internally, string IDs in exports.

### Scraping Infrastructure

All scrapers use `src/part_a/common/http_client.py` (`HTTPClient`) which provides rate limiting (token bucket), proxy rotation, retry with backoff, User-Agent rotation, and raw HTML caching under `data/raw_html/`.

### Blog Template Structure

Jinja2 templates in `src/part_b/template_engine/templates/` — 7 section templates (`section_0_hook` through `section_6_faq`) composed by `blog_post.jinja2`. Each section maps to the 6-section blog format (hook → credibility → criteria → quick pick → TCO deep dive → action trigger → FAQ).

### Publishing Pipeline

`PublishPipeline` in `src/part_b/publisher/pipeline.py` orchestrates the full flow: `ContentWriter` → CTA link injection → template render → `PostProcessor` (HTML/markdown export, SEO tags) → platform publish (Naver Blog, Tistory).

## Category Configuration

Products are defined in YAML files under `config/` (e.g., `products_robot_vacuum.yaml`). Each category config includes product list, community keyword map for repair search, and maintenance task templates. The system is category-agnostic — swap the YAML to target a different appliance category.

## Key Design Rules

- **GPT as narrator, not data source:** LLM generates narrative and tone; all numbers are injected from Part A. `ContentWriter` never fabricates quantitative data.
- **CTA placement:** Exactly 1 CTA per product in Section 3, Section 4, and Section 5.
- **Minimum data threshold:** 30 community posts before generating TCO for a product.
- **Raw HTML caching:** All scraped HTML is cached for audit; processed data goes to DB.
- **Korean text:** All processing must handle UTF-8 encoding correctly.

## Test Fixtures

- `fixtures/sample_tco_data.json` — Sample Part A export for testing the Part B pipeline
- `fixtures/sample_blog_data.py` — Pre-built `BlogPostData` objects
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
