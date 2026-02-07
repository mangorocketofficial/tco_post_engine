# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TCO-Driven Affiliate Marketing Automation System — an automated pipeline that collects real TCO (Total Cost of Ownership) data from Korean e-commerce platforms and communities, then generates high-conversion affiliate blog posts grounded in actual cost analysis.

**Core formula:** `Real Cost (3yr) = Purchase Price + Expected Repair Cost − Resale Value`

The system has two major parts:
- **Part A (Data Engine):** Scrapes pricing, resale, repair data → processes into structured TCO metrics
- **Part B (Content Engine):** Takes TCO data → generates Korean affiliate blog posts via GPT/Claude API

## Tech Stack

- **Language:** Python 3.12
- **Scraping:** requests, playwright, BeautifulSoup
- **NLP/Extraction:** GPT-4o API (structured output)
- **Storage:** SQLite (MVP) → PostgreSQL
- **Template Engine:** Jinja2
- **Content Generation:** GPT-4o / Claude API
- **Publishing:** Naver Blog, Tistory platform APIs
- **Analytics:** mangorocket-stats (existing dashboard at `C:\Users\User\Desktop\project\mangorocket_universe\mangorocket-stats\`)
- **Orchestration:** cron (MVP) → Airflow or n8n

## Architecture

```
PART A: Data Engine
├── price-tracker/       # Danawa/Coupang/Naver Shopping daily price scraping
├── resale-tracker/      # Danggeun/Bunjang completed sale transactions (weekly)
├── repair-analyzer/     # Community posts (Ppomppu/Clien/Naver Cafe) + GPT extraction
├── maintenance-calc/    # Official manuals + user reports → monthly time cost
└── tco-engine/          # TCO calculator + JSON export API for Part B

PART B: Content Engine
├── template-engine/     # Jinja2 blog structure templates with variable slots
├── content-writer/      # GPT writer with tone guide + data insertion rules
├── cta-manager/         # Affiliate link storage, placement rules, UTM tracking
├── stats-connector/     # Push metrics to mangorocket-stats dashboard
└── publisher/           # Post-processing + platform API publishing
```

## Storage Schema

```
products
├── id, name, brand, category, release_date
├── prices[]               (time-series, daily)
├── resale_transactions[]  (weekly)
├── repair_reports[]       (weekly, GPT-extracted)
├── maintenance_tasks[]    (semi-manual)
└── tco_summary            (calculated, refreshed weekly)
```

## TCO Data Points

| Metric | Type | Source |
|--------|------|--------|
| Q1: Purchase Price | Quantitative (KRW) | Danawa, Coupang price history |
| Q2: Resale Value | Quantitative (KRW) | Danggeun, Bunjang transactions |
| Q3: Expected Repair Cost | Quantitative (KRW) | Community posts, probability-weighted |
| S1: AS Turnaround Time | Qualitative (days) | Community AS review posts |
| S2: Maintenance Time | Qualitative (min/month) | Official specs + user reports |

## Blog Post Structure (6 Sections)

0. Hook (1-min summary, 3 picks) → 1. Credibility ("자체 분석 N건") → 2. Criteria Framing (myth-busting) → 3. Quick Pick Table (CTA per product) → 4. TCO Deep Dive (quantitative + qualitative tables) → 5. Action Trigger (price volatility + disclosure) → 6. FAQ (SEO long-tail targets)

---

## Agent Team Development (agent-team-dev)

This project uses a **3-person agent development team** coordinated via git worktree and Windows Terminal split panes.

### Team Structure

| Role | Branch | Worktree Path | Scope |
|------|--------|---------------|-------|
| **Lead** | `main` | `TCO_Post_Engine/` (this directory) | Architecture, coordination, integration testing |
| **PartA Dev** | `dev/part-a` | `TCO_Post_Engine-partA/` | Data Engine (all A modules) |
| **PartB Dev** | `dev/part-b` | `TCO_Post_Engine-partB/` | Content Engine (all B modules) |

### Git Worktree Layout

```
C:\Users\User\Desktop\project\
├── TCO_Post_Engine/           # main branch — Lead developer
├── TCO_Post_Engine-partA/     # dev/part-a branch — PartA developer
└── TCO_Post_Engine-partB/     # dev/part-b branch — PartB developer
```

### Role Definitions

#### Lead Developer (main branch)
- Coordinates overall development per dev_agent.md specification
- Communicates directly with PartA/PartB developers via shared files in `.coordination/`
- Reviews and merges PRs from dev/part-a and dev/part-b into main
- Runs cross-team integration tests
- Manages team status via `.coordination/status.md`
- Has authority to direct both PartA and PartB developers

#### PartA Developer (dev/part-a branch)
- Implements all Part A modules: price-tracker, resale-tracker, repair-analyzer, maintenance-calc, tco-engine
- Commits at every major update point
- Follows Lead developer's directives
- Runs unit tests for data collection and processing
- Updates `.coordination/status-partA.md` with progress

#### PartB Developer (dev/part-b branch)
- Implements all Part B modules: template-engine, content-writer, cta-manager, stats-connector, publisher
- Commits at every major update point
- Follows Lead developer's directives
- Runs unit tests for content generation and publishing
- Updates `.coordination/status-partB.md` with progress

### Coordination Protocol

1. **Status updates:** Each developer updates their status file after completing a task
2. **Blocking issues:** Write to `.coordination/blockers.md` with description and needed resolution
3. **Integration points:** Part B depends on Part A's TCO JSON export API — coordinate schema via `.coordination/api-contract.json`
4. **Commit discipline:** Commit at every meaningful milestone with descriptive messages prefixed by `[PartA]` or `[PartB]`
5. **Cross-testing:** Lead merges both branches and runs end-to-end tests

### Terminal Launch

Three Windows Terminal panes are used to run each developer's Claude Code instance simultaneously:

```bash
# Launch script (run from Git Bash):
wt.exe -d "C:/Users/User/Desktop/project/TCO_Post_Engine" bash -c "echo '[LEAD] main branch'; exec bash" \; \
  split-pane -H -d "C:/Users/User/Desktop/project/TCO_Post_Engine-partA" bash -c "echo '[PART-A] dev/part-a branch'; exec bash" \; \
  split-pane -V -d "C:/Users/User/Desktop/project/TCO_Post_Engine-partB" bash -c "echo '[PART-B] dev/part-b branch'; exec bash"
```

Each pane runs its own `claude` CLI instance targeting its respective worktree.

---

## Development Rules

### General
- All code in Python 3.12, type-hinted
- GPT/Claude API calls NEVER fabricate data — all numbers come from Part A scrapers
- Raw HTML is cached for audit; processed data goes to DB
- Every scraper must respect rate limits and use rotating proxies
- Minimum data threshold: 30 community posts before generating TCO for a product
- All Korean text processing must handle encoding (UTF-8) correctly

### Commit Rules
- Prefix commits: `[Lead]`, `[PartA]`, `[PartB]` per developer role
- Commit at every major update (new module, feature complete, bug fix)
- Never commit API keys, tokens, or credentials — use `.env` files (gitignored)

### Testing
- Each module must have unit tests
- Part A: test scrapers with cached HTML fixtures, test TCO calculations
- Part B: test template rendering, test CTA injection, test output format
- Lead runs integration tests after merging branches

### Branch Strategy
- `main`: stable, integration-tested code (Lead manages)
- `dev/part-a`: Part A development (PartA Dev)
- `dev/part-b`: Part B development (PartB Dev)
- Merge flow: `dev/part-a` → `main` ← `dev/part-b` via pull request

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run individual scrapers
python -m src.part_a.price_tracker.main
python -m src.part_a.resale_tracker.main
python -m src.part_a.repair_analyzer.main

# Run TCO calculation
python -m src.part_a.tco_engine.main

# Generate blog post
python -m src.part_b.content_writer.main --category "로봇청소기"

# Run tests
pytest tests/
pytest tests/part_a/       # Part A tests only
pytest tests/part_b/       # Part B tests only
pytest tests/integration/  # Integration tests (Lead)

# Run single test file
pytest tests/part_a/test_price_tracker.py -v
```

## Key Design Decisions
- **Category-agnostic pipeline:** Swap product keyword + keyword map + maintenance template to target any appliance category
- **GPT as narrator, not data source:** Writer generates narrative flow and tone; all numbers are injected from Part A
- **Resale price retention curve:** Track `resale_price / original_price` at 6mo, 12mo, 18mo, 24mo intervals
- **CTA placement:** Exactly 1 CTA per product in Section 3, Section 4, and Section 5
- **Publishing disclosure:** Every post includes "국내 주요 커뮤니티 리뷰 데이터 N건을 자체 분석한 결과"
