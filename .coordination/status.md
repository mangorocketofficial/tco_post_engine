# Team Status Board

Last updated: 2026-02-07
Phase: 1 (MVP) — Week 2

## Lead Developer (main)
- **Status:** Active — Week 1 merge + integration complete
- **Current task:** Coordinating Week 2 tasks, monitoring progress
- **Completed:**
  - Project directory structure (all Part A + Part B modules)
  - Shared Pydantic data models (`src/common/models.py`)
  - SQLite database schema + utilities (`src/common/database.py`)
  - Config system with settings.yaml + .env (`src/common/config.py`)
  - Logging module (`src/common/logging.py`)
  - Test fixtures + conftest.py (with `temp_db` and `db_conn`)
  - MVP product list: 3 robot vacuums (`config/products_robot_vacuum.yaml`)
  - API contract JSON (`api-contract.json`)
  - **Week 1 merge:** dev/part-a + dev/part-b merged into main, 67/67 tests passing
- **Blockers:** None

## PartA Developer (dev/part-a)
- **Status:** Week 1 COMPLETE — pull from main and start Week 2
- **Week 1 Completed:**
  - [x] Price Tracker (Danawa) — `src/part_a/price_tracker/`
  - [x] Resale Tracker (Danggeun) — `src/part_a/resale_tracker/`
  - [x] Database layer — `src/part_a/database/`
  - [x] HTTP client + rate limiter — `src/part_a/common/`
  - [x] Unit tests (24 tests passing)
- **Week 2 Tasks:**
  1. **Pull from main first:** `git pull origin master` to get merged code + conftest.py fix
  2. **Repair Analyzer** — implement `src/part_a/repair_analyzer/`
     - Scrape community posts (Ppomppu, Clien, Naver Cafe)
     - Keywords: `{product_name} + [수리, AS, 고장, 서비스센터, 교체, 부품]`
     - Use GPT API for structured extraction:
       - `repair_cost`: KRW amount
       - `as_days`: turnaround days
       - `failure_type`: categorize (sensor, motor, software, battery, etc.)
       - `sentiment`: positive/negative/neutral
     - Calculate expected_repair_cost: `Σ(repair_cost × probability_of_failure_type)`
     - Store as RepairReport model + repair_reports table
  3. **Maintenance Calculator** — implement `src/part_a/maintenance_calc/`
     - Load maintenance task templates from `config/products_robot_vacuum.yaml`
     - Per-product override support (auto-clean station = 0 min vs manual = 15 min/week)
     - Calculate total_monthly_minutes per product
     - Store as MaintenanceTask model
  4. Write unit tests for both modules in `tests/part_a/`
- **Dependencies:** Uses shared Config, DB, HTTP client from Week 1
- **Blockers:** None

## PartB Developer (dev/part-b)
- **Status:** Week 1 COMPLETE — pull from main and start Week 2
- **Week 1 Completed:**
  - [x] Template Engine (7-section Jinja2) — `src/part_b/template_engine/`
  - [x] Template models + renderer
  - [x] Sample fixtures (JSON + Python)
  - [x] Unit tests (18 tests passing)
- **Week 2 Tasks:**
  1. **Pull from main first:** `git pull origin master` to get merged code + conftest.py fix
  2. **Content Writer** — implement `src/part_b/content_writer/`
     - GPT-4o / Claude API integration for blog content generation
     - System prompt: blog tone guide + structure enforcement + data insertion rules
     - Input: BlogPostData (template context with TCO data)
     - Output: Complete Korean blog post in markdown
     - Post-processing: CTA link injection, affiliate tag insertion
     - Writer NEVER fabricates data — all numbers injected from Part A
     - Generate 2-3 FAQ items dynamically from repair data pain points
     - SEO: inject long-tail keywords in H2/H3 headings
  3. **CTA Manager** — flesh out `src/part_b/cta_manager/`
     - Product → affiliate URL mapping (Coupang Partners)
     - Placement rules: 1 CTA per product in sections 3, 4, 5
     - Unified wording: "최저가 확인하기"
     - UTM parameters per section for click attribution
  4. Write unit tests for content generation in `tests/part_b/`
- **Dependencies:** Uses template engine from Week 1, TCO data models
- **Blockers:** None

## Integration Log
| Date | Action | Result |
|------|--------|--------|
| 2026-02-07 | Project initialized, worktrees created | OK |
| 2026-02-07 | Lead: Foundation complete — models, DB, config, tests | OK |
| 2026-02-07 | PartA: Week 1 complete — price-tracker + resale-tracker | OK |
| 2026-02-07 | PartB: Week 1 complete — template-engine (7 sections) | OK |
| 2026-02-07 | Lead: Merged dev/part-a into main (fast-forward) | OK |
| 2026-02-07 | Lead: Merged dev/part-b into main (conflict resolved: tests/__init__.py) | OK |
| 2026-02-07 | Lead: Added temp_db + db_conn fixtures to conftest.py | OK |
| 2026-02-07 | Lead: Full test suite — 67/67 passed | OK |
| 2026-02-07 | Lead: Week 2 tasks assigned to PartA + PartB | OK |
