# Team Status Board

Last updated: 2026-02-07
Phase: 1 (MVP) — Week 1

## Lead Developer (main)
- **Status:** Active
- **Current task:** Project foundation complete — shared models, DB, config ready
- **Completed:**
  - Project directory structure (all Part A + Part B modules)
  - Shared Pydantic data models (`src/common/models.py`)
  - SQLite database schema + utilities (`src/common/database.py`)
  - Config system with settings.yaml + .env (`src/common/config.py`)
  - Logging module (`src/common/logging.py`)
  - Test fixtures + conftest.py
  - MVP product list: 3 robot vacuums (`config/products_robot_vacuum.yaml`)
  - API contract JSON (`api-contract.json`)
- **Blockers:** None

## PartA Developer (dev/part-a)
- **Status:** Ready to start
- **Week 1 Tasks:**
  1. **Price Tracker (Danawa)** — implement `src/part_a/price_tracker/`
     - Scrape Danawa product pages for price history
     - Store daily price records to SQLite via `src/common/database.py`
     - Use models from `src/common/models.py` (PriceRecord, PriceSource)
     - Cache raw HTML to `data/raw/`
     - Target products: see `config/products_robot_vacuum.yaml`
  2. **Resale Tracker (Danggeun)** — implement `src/part_a/resale_tracker/`
     - Scrape Danggeun Market for completed sales
     - Use Playwright (JS-heavy SPA)
     - Store as ResaleTransaction model
     - Filter completed sales only, estimate months_since_release
  3. Write unit tests in `tests/part_a/`
- **Dependencies:** Use shared models + DB from `src/common/`
- **Blockers:** None

## PartB Developer (dev/part-b)
- **Status:** Ready to start
- **Week 1 Tasks:**
  1. **Blog Template** — finalize in `src/part_b/template_engine/`
     - Create Jinja2 markdown templates matching the 6-section blog structure
     - Section 0 (Hook) through Section 6 (FAQ)
     - Define all variable slots: `{product_name}`, `{tco_table}`, etc.
     - Template must consume TCOCategoryExport model from `src/common/models.py`
  2. **CTA Manager skeleton** — set up `src/part_b/cta_manager/`
     - Define affiliate link storage schema
     - CTA placement rules (1 per product in sections 3, 4, 5)
  3. Write unit tests for template rendering in `tests/part_b/`
- **Dependencies:** Uses TCOCategoryExport model for template variables
- **Blockers:** None

## Integration Log
| Date | Action | Result |
|------|--------|--------|
| 2026-02-07 | Project initialized, worktrees created | OK |
| 2026-02-07 | Lead: Foundation complete — models, DB, config, tests | OK |
