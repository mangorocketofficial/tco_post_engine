# PartA Developer Status

Last updated: 2026-02-07
Branch: dev/part-a

## Current Sprint: Phase 1 Week 2

### DIRECTIVE FROM LEAD
**Week 1 is complete and merged to main. Pull from main before starting Week 2.**
```bash
git merge master
```

### Week 1 — COMPLETED
- [x] Price Tracker (Danawa) — `src/part_a/price_tracker/`
- [x] Resale Tracker (Danggeun) — `src/part_a/resale_tracker/`
- [x] Database layer — `src/part_a/database/`
- [x] HTTP client + rate limiter — `src/part_a/common/`
- [x] Unit tests (24 tests passing)

### Week 2 Tasks
1. [ ] **Repair Analyzer** — `src/part_a/repair_analyzer/`
   - Scrape Ppomppu, Clien, Naver Cafe for repair/AS posts
   - Keywords: `{product_name} + [수리, AS, 고장, 서비스센터, 교체, 부품]`
   - Use GPT API (structured output) to extract from each post:
     - `repair_cost` (KRW)
     - `as_days` (turnaround days)
     - `failure_type` (sensor, motor, software, battery, brush, mop, charging)
     - `sentiment` (positive/negative/neutral)
   - Calculate: `expected_repair_cost = Σ(repair_cost × probability_of_failure_type)`
   - Calculate: `avg_as_turnaround_days = mean(as_days)`
   - Store in `repair_reports` table via existing DB layer
   - Cache raw HTML to `data/raw/`
2. [ ] **Maintenance Calculator** — `src/part_a/maintenance_calc/`
   - Load maintenance task templates from `config/products_robot_vacuum.yaml`
   - Per-product overrides (e.g., auto-clean station = 0 min dust emptying)
   - Calculate `total_monthly_minutes` per product
   - Store in `maintenance_tasks` table
3. [ ] Unit tests for both modules — `tests/part_a/`

### Key References
- Shared models: `src/common/models.py`
- PartA Config: `src/part_a/common/config.py`
- PartA Database: `src/part_a/database/connection.py`
- PartA HTTP Client: `src/part_a/common/http_client.py`
- Product list + keywords: `config/products_robot_vacuum.yaml`
- API contract: `.coordination/api-contract.json`
- GPT API key: use `OPENAI_API_KEY` from `.env`

### Modules
| Module | Status | Notes |
|--------|--------|-------|
| price-tracker | **DONE** | Danawa primary |
| resale-tracker | **DONE** | Danggeun |
| repair-analyzer | **Week 2** | Community + GPT extraction |
| maintenance-calc | **Week 2** | YAML templates + user reports |
| tco-engine | Week 3 | Calculator + JSON export |

### Progress Log
| Date | Task | Status |
|------|------|--------|
| 2026-02-07 | Branch dev/part-a created | Done |
| 2026-02-07 | Lead: Foundation ready, Week 1 tasks assigned | Done |
| 2026-02-07 | price-tracker + resale-tracker implemented | Done |
| 2026-02-07 | Lead merged to main, 67/67 tests pass | Done |
| 2026-02-07 | Week 2 tasks assigned: repair-analyzer + maintenance-calc | Ready |
