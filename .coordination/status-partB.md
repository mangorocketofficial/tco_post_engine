# PartB Developer Status

Last updated: 2026-02-07
Branch: dev/part-b

## Current Sprint: Phase 1 Week 2

### DIRECTIVE FROM LEAD
**Week 1 is complete and merged to main. Pull from main before starting Week 2.**
```bash
git merge master
```

### Week 1 — COMPLETED
- [x] Template Engine (Jinja2) — `src/part_b/template_engine/`
- [x] 7-section blog templates (section_0 through section_6)
- [x] Template models + renderer
- [x] Sample fixtures (JSON + Python)
- [x] Unit tests (18 tests passing)

### Week 2 Tasks
1. [ ] **Content Writer** — `src/part_b/content_writer/`
   - GPT-4o / Claude API integration for Korean blog content generation
   - System prompt engineering:
     - Blog tone guide (conversational Korean, 반말/존댓말 consistency)
     - Structure enforcement (must follow 7-section template)
     - Data insertion rules (all numbers from Part A, NEVER fabricated)
   - Input: `BlogPostData` from template engine models
   - Output: Complete Korean blog post in markdown
   - Post-processing pipeline:
     - CTA link injection at proper positions
     - Affiliate tag insertion
     - Image placeholder insertion
   - Dynamic FAQ generation: 2-3 items from repair data pain points
   - SEO: inject long-tail keywords in H2/H3 headings
   - Test with mock API responses + sample fixture data
2. [ ] **CTA Manager** — flesh out `src/part_b/cta_manager/`
   - Product → affiliate URL mapping (Coupang Partners format)
   - Placement rules: exactly 1 CTA per product in sections 3, 4, and 5
   - Unified CTA wording: "최저가 확인하기"
   - UTM parameters per section: `utm_source=blog&utm_medium=cta&utm_campaign=tco&utm_content=section_{N}`
   - Link storage: JSON or DB-backed product → URL map
3. [ ] Unit tests — `tests/part_b/`

### Key References
- Template engine: `src/part_b/template_engine/` (your Week 1 work)
- Template models: `src/part_b/template_engine/models.py`
- Sample data: `fixtures/sample_tco_data.json`, `fixtures/sample_blog_data.py`
- Shared models: `src/common/models.py` (TCOCategoryExport)
- API contract: `.coordination/api-contract.json`
- LLM settings: `src/common/config.py` (LLMSettings)
- API keys: `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` from `.env`

### Modules
| Module | Status | Notes |
|--------|--------|-------|
| template-engine | **DONE** | Jinja2 blog structure |
| content-writer | **Week 2** | GPT writer + tone guide |
| cta-manager | **Week 2** | Affiliate links + UTM |
| stats-connector | Week 4 | mangorocket-stats integration |
| publisher | Week 3 | Naver Blog, Tistory APIs |

### Progress Log
| Date | Task | Status |
|------|------|--------|
| 2026-02-07 | Branch dev/part-b created | Done |
| 2026-02-07 | Lead: Foundation ready, Week 1 tasks assigned | Done |
| 2026-02-07 | template-engine implemented (7 sections + tests) | Done |
| 2026-02-07 | Lead merged to main, 67/67 tests pass | Done |
| 2026-02-07 | Week 2 tasks assigned: content-writer + cta-manager | Ready |
