# TCO Affiliate Blog — Content Structure Specification

## RAG Reference Document v1.0

> This document is the **single source of truth** for blog content generation.
> When generating any TCO comparison blog post, follow this structure exactly.

---

## 1. FINAL BLOG STRUCTURE (7 Sections)

### Section 0: 결론 먼저 (Conclusion First)

**Purpose:** Kill bounce rate in 5 seconds. Give the answer immediately.

**Format:** 3 situation-based recommendations + 1-line TCO summary per product.

**Template:**
```
🚀 1분 요약: [카테고리]는 뭘 사야 할까?
✅ [상황1]: [제품A] ([TCO 핵심 수치])
✅ [상황2]: [제품B] ([TCO 핵심 수치])
✅ [상황3]: [제품C] ([TCO 핵심 수치])
```

**Rules:**
- MUST start with conclusions, NOT questions or problem statements
- Each recommendation includes the specific situation + product + one data point
- No "구매가만 보고 후회하셨나요?" style hooks — those are generic and low-conversion
- This section is the #1 differentiator from other affiliate blogs

**❌ WRONG (current implementation):**
```
"구매가만 보고 샀다가 후회하셨나요? 3년 실비용을 보면..."
```

**✅ CORRECT:**
```
🚀 1분 요약: 공기청정기는 뭘 사야 할까?
✅ 고장 스트레스 싫은 분: 다이슨 빅+콰이엇 (3년 실비용 606,330원, AS 평균 3일)
✅ 가성비 최우선: 위닉스 타워엣지 (3년 실비용 167,150원, 유지 자동화 75%)
✅ 최저 비용: 씽크에어 ZERO (3년 실비용 50,120원)
```

**Length:** 5–7 lines max.

---

### Section 1: 신뢰성 확보 (Credibility)

**Purpose:** Answer "why should I trust this post?" with concrete numbers.

**Format:** Data authority claim with specific counts.

**Template:**
```
이 글은 [소스 설명]을 교차 검증한 분석입니다.

- 커뮤니티 리뷰 데이터: {{ total_review_count }}건 자체 분석
- 중고 실거래 데이터: {{ resale_sample_count }}건 수집
- 수리/AS 후기: {{ repair_report_count }}건 종합
- 데이터 수집 기간: {{ collection_period }}
```

**Rules:**
- Use "국내 주요 커뮤니티 리뷰 데이터 N건을 자체 분석한 결과" as standard disclosure
- All numbers come from Part A data — never fabricate
- Do NOT name specific community sources (뽐뿌, 클리앙 etc.)
- Keep factual and brief — credibility comes from numbers, not lengthy explanation

**Length:** 6–8 lines.

---

### Section 2: 카테고리 특화 기준 3가지 (Category-Specific Criteria)

**Purpose:** Reframe how the reader thinks about this purchase. Build the mental model that leads to TCO-based decision making.

**Format:** 3 sub-sections, each with a specific role in the persuasion chain.

#### 2-1. 미신 깨기 (Myth Busting)

**Role:** Destroy the spec-comparison mindset.

**Logic:** "[Commonly cited spec] looks important, but actual test data shows [minimal real-world difference]. So stop comparing [spec] and start looking at [what actually matters]."

**Category examples for LLM prompt:**
- Robot vacuum → "흡입력 7,000Pa vs 11,000Pa, 실제 픽업률 차이 1~2%"
- Air purifier → "CADR 500 vs 800, 20평 기준 둘 다 충분, 체감 차이는 소음과 필터"
- Dryer → "건조 용량 16kg vs 19kg, 실사용 1회 빨래량은 평균 5~6kg"
- Dishwasher → "식기 수용 개수 12인용 vs 16인용, 실사용은 절반도 안 채움"

**LLM generation field:** `category_criteria.myth_busting`

#### 2-2. 진짜 차별점 (Real Differentiator)

**Role:** Introduce the hidden cost factor that this blog uniquely covers.

**Logic:** "[Year]년 [카테고리] 차별점은 [commonly compared feature]가 아니라 [hidden cost factor]로 이동했습니다. 이게 3년 실비용에서 [specific impact]만큼 차이를 만듭니다."

**Category examples for LLM prompt:**
- Robot vacuum → "차별점은 흡입이 아니라 물걸레 위생(온수 세척)"
- Air purifier → "차별점은 CADR이 아니라 필터 교체 비용 (3년이면 구매가를 넘길 수 있음)"
- Dryer → "차별점은 용량이 아니라 전기료 (히트펌프 vs 히터식, 3년 전기료 차이 30만원+)"
- Dishwasher → "차별점은 수용량이 아니라 건조 방식 (자연건조 vs 열풍건조 = 위생 + 시간)"

**LLM generation field:** `category_criteria.real_differentiator`

#### 2-3. 우리 집 갈림길 (Your Home Decision Fork)

**Role:** Make the reader self-categorize. This bridges directly to Section 3 recommendations.

**Logic:** Present 2–3 home/lifestyle types and show which factor matters most for each.

**Category examples for LLM prompt:**
- Robot vacuum → "전선/양말 많은 집 vs 깔끔한 집 → 카메라 AI 필요 여부 갈림"
- Air purifier → "원룸(소음 우선) vs 거실 30평+(커버리지 우선) vs 반려동물(탈취 우선)"
- Dryer → "매일 돌리는 집(전기료 우선) vs 주 2회(용량 우선) vs 빨래방 대체(건조 품질 우선)"
- Dishwasher → "2인 가구(소형 필요) vs 4인+(용량 필요) vs 프라이팬 세척(고온 고압 필요)"

**LLM generation field:** `category_criteria.decision_fork`

**Section 2 total length:** ~20 lines.

**❌ WRONG (current implementation):**
```
## Section 2: 선정 기준
TCO 공식: 구매가 + 수리비 - 중고 환급액 = 3년 실비용
```
This is generic, applies to every category identically, and teaches formula instead of building purchase intuition.

**✅ CORRECT:** Category-specific insights that make the reader think "이 사람 진짜 아는구나" before seeing any product recommendation.

---

### Section 3: 상황별 추천 요약표 (Quick Pick Table)

**Purpose:** Instant decision for readers who don't need deep analysis.

**Format:** 3-column comparison table matching the 3-slot framework (Stability / Balance / Value).

**Template:**
```
| | 안정형 | 균형형 | 가성비형 |
|---|---|---|---|
| 제품명 | {{ stability.name }} | {{ balance.name }} | {{ value.name }} |
| 핵심 포인트 | {{ stability.highlight }} | {{ balance.highlight }} | {{ value.highlight }} |
| 3년 실비용 | {{ stability.real_cost_3yr }} | {{ balance.real_cost_3yr }} | {{ value.real_cost_3yr }} |
| | [최저가 확인하기]({{ stability.cta_link }}) | [최저가 확인하기]({{ balance.cta_link }}) | [최저가 확인하기]({{ value.cta_link }}) |
```

**Rules:**
- Slot labels should use contextual names, not just "안정형/균형형/가성비형"
  - Example: "고장 스트레스 제로 / 풀옵션 올인원 / 최소 비용 실속"
- CTA wording MUST be unified: "최저가 확인하기" for all products
- Include exactly 1 CTA per product in this section
- Table must include 3년 실비용 row — this is the key differentiator

**Length:** ~10 lines.

---

### Section 4: TCO 심층 분석 (TCO Deep Dive)

**Purpose:** Provide evidence for Section 3 recommendations. This is where data credibility is built.

**Format:** 5 sub-sections.

#### 4-1 to 4-3: 제품별 상세 (Per-Product Analysis)

**Per product, include:**
```
### [번호]. {{ product.name }}

👍 추천: {{ product.recommendation_reason }}
👎 주의: {{ product.caution_reason }}

- 구매가(평균): {{ product.tco.purchase_price_avg }}원
- 2년 중고가: {{ product.tco.resale_value_2yr }}원
- 예상 수리비: {{ product.tco.expected_repair_cost }}원
- 3년 실비용: **{{ product.tco.real_cost_3yr }}원**

[최저가 확인하기]({{ product.cta_link }})
```

**Rules:**
- 추천/주의 reasons must cite TCO data, not generic statements
- All numbers injected from Part A — LLM never generates numbers
- Include exactly 1 CTA per product
- Do NOT repeat Section 3 content — go deeper here (repair context, community insights)

#### 4-4: 정량 비교표 (Quantitative TCO Table)

**Template:**
```
| 항목 (3년) | {{ product1.name }} | {{ product2.name }} | {{ product3.name }} |
|---|---|---|---|
| 초기 구매가 | {{ p1.purchase_price_avg }}원 | {{ p2.purchase_price_avg }}원 | {{ p3.purchase_price_avg }}원 |
| 2년 중고 판매가 | -{{ p1.resale_value_2yr }}원 | -{{ p2.resale_value_2yr }}원 | -{{ p3.resale_value_2yr }}원 |
| 예상 수리비 | +{{ p1.expected_repair_cost }}원 | +{{ p2.expected_repair_cost }}원 | +{{ p3.expected_repair_cost }}원 |
| **3년 실비용** | **{{ p1.real_cost_3yr }}원** | **{{ p2.real_cost_3yr }}원** | **{{ p3.real_cost_3yr }}원** |
```

**Rules:**
- Exactly 4 rows: 구매가, 중고 판매가, 수리비, 3년 실비용
- All numbers from Part A TCO engine
- 3년 실비용 row must be bold

#### 4-5: 정성 비교표 (Qualitative Experience Table) ← NEW

**Template:**
```
| 체감 비교 | {{ product1.name }} | {{ product2.name }} | {{ product3.name }} |
|---|---|---|---|
| AS 평균 대기일 | {{ p1.as_turnaround_days }}일 | {{ p2.as_turnaround_days }}일 | {{ p3.as_turnaround_days }}일 |
| 유지관리 자동화율 | {{ p1.automation_rate }}% | {{ p2.automation_rate }}% | {{ p3.automation_rate }}% |
```

**AS 대기일:** Extracted from community AS review posts (Part A repair-analyzer).

**유지관리 자동화율 (Maintenance Automation Rate):** Calculated as percentage of maintenance tasks that are automated.

Calculation method:
```
For each product:
  1. List all maintenance tasks from official spec/manual
  2. Classify each task: ✅ auto / ❌ manual
  3. automation_rate = (auto_count / total_count) × 100
```

Standard maintenance task checklist (adapt per category):

**Robot vacuum tasks:**
| Task | Check |
|------|-------|
| 걸레 세척 | auto or manual |
| 먼지통 비우기 | auto or manual |
| 필터 청소 | auto or manual |
| 물탱크 리필 | auto or manual |
| 브러시 청소 | auto or manual |
| 세제 투입 | auto or manual |

**Air purifier tasks:**
| Task | Check |
|------|-------|
| 필터 교체 알림 | auto or manual |
| 프리필터 세척 | auto or manual |
| 자동 풍량 조절 | auto or manual |
| 필터 잔여 수명 표시 | auto or manual |
| 공기질 자동 감지 | auto or manual |

**Data source:** Official product specifications (100% verifiable, no estimation needed).

**❌ WRONG approach (removed):**
```
| 월 유지시간 | 36분 | 96분 | 45분 |
```
Minutes per task cannot be reliably sourced — estimation violates data integrity principle.

**✅ CORRECT approach (adopted):**
```
| 유지관리 자동화율 | 67% (4/6 자동) | 33% (2/6 자동) | 50% (3/6 자동) |
```
Binary auto/manual classification from official specs — 100% verifiable.

**Section 4 total length:** ~30 lines (largest section).

---

### Section 5: 행동 유도 (Action Trigger)

**Purpose:** Create urgency without being pushy. Push toward CTA click.

**Format:** Price volatility mention + final CTA per product.

**Template:**
```
[카테고리] 가격은 시즌/이벤트에 따라 급변합니다. 
지금 당장 구매하지 않더라도, 현재 조건을 확인해두면 손해 보지 않습니다.

- {{ product1.name }}: [최저가 확인하기]({{ cta_link }})
- {{ product2.name }}: [최저가 확인하기]({{ cta_link }})
- {{ product3.name }}: [최저가 확인하기]({{ cta_link }})

💡 "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
```

**Rules:**
- Do NOT repeat Section 3 recommendations — this is about urgency, not summary
- Include affiliate disclosure
- Include exactly 1 CTA per product (3rd and final CTA placement)
- Tone: helpful advisor, not salesman

**❌ WRONG (current implementation):**
```
TOP 3 요약 + 재촉구
```
This repeats Section 3 content and feels like a second sales pitch.

**✅ CORRECT:** Focus on price volatility and "지금 확인만 해두세요" framing.

**Length:** 5–7 lines.

---

### Section 6: FAQ (Objection Handling + SEO Long-tail)

**Purpose:** Catch exit-intent readers with answers to questions NOT covered in main content. Also serves as SEO long-tail keyword targets.

**Rules — CRITICAL:**
- FAQ questions must NOT repeat main content
- Section 2-1 (myth busting) content → DO NOT repeat in FAQ
- Section 4 (per-product analysis) content → DO NOT repeat in FAQ
- FAQ should cover NEW angles: specific concerns, edge cases, comparison questions

**Good FAQ topics (generated from Part A repair-analyzer data):**
- Specific failure modes: "[제품] ○○ 고장 자주 나나요?"
- AS experience: "[브랜드] AS 센터 어디있나요? 택배 수리만 되나요?"
- Compatibility: "우리 집 ○평인데 [제품] 충분한가요?"
- Noise: "[제품] 소음 어느 정도인가요?"
- Consumable sourcing: "[제품] 호환 필터 있나요?"
- Comparison not in main content: "[제품A] vs [제외된 제품D] 뭐가 나아요?"

**LLM generation field:** `faqs` — must receive repair_context from Part A to generate data-grounded answers.

**Length:** ~20 lines (5 Q&A pairs).

---

## 2. TCO FRAMEWORK SPECIFICATION

### Quantitative Metrics (displayed in Section 4-4)

| # | Metric | Source | Calculation |
|---|--------|--------|-------------|
| Q1 | 초기 구매가 (avg) | Danawa/Coupang price tracker | 90-day average |
| Q2 | 2년 중고 판매가 | Danggeun/Bunjang transactions | Median sale price at 24 months |
| Q3 | 예상 수리비 | Community repair posts | Σ(repair_cost × failure_probability) |

**TCO Formula:**
```
3년 실비용 = Q1 + Q3 − Q2
```

### Qualitative Metrics (displayed in Section 4-5)

| # | Metric | Source | Calculation |
|---|--------|--------|-------------|
| S1 | AS 평균 대기일 | Community AS review posts | Mean days from send to return |
| S2 | 유지관리 자동화율 | Official product specs | (auto_tasks / total_tasks) × 100% |

### Removed Metrics

| Metric | Reason for removal |
|--------|-------------------|
| 전기료 | 3-year difference < 20,000 KRW — negligible impact on decision |
| 공식 소모품가 (standalone) | Unrealistic — most users buy compatible parts |
| 월 유지시간 (minutes) | Cannot be reliably sourced — violates data integrity principle |
| 만족도 변화곡선 | Excluded from TCO scope (separate content opportunity) |

---

## 3. CTA PLACEMENT RULES

| Section | CTA Count | Format |
|---------|-----------|--------|
| Section 0 (Hook) | 0 | No CTA — pure value delivery |
| Section 1 (Credibility) | 0 | No CTA — trust building |
| Section 2 (Criteria) | 0 | No CTA — education |
| Section 3 (Quick Pick) | **1 per product** | Table cell: "최저가 확인하기" |
| Section 4 (Deep Dive) | **1 per product** | End of each 4-1/4-2/4-3 block |
| Section 5 (Action) | **1 per product** | Final CTA with urgency framing |
| Section 6 (FAQ) | 0 | No CTA — information only |

**Total CTA per product: exactly 3**
**CTA wording: always "최저가 확인하기"** (unified, no A/B variants like "가격 보기" / "할인가 보기")
**UTM tracking: section parameter for click attribution** (e.g., `utm_content=section3`)

---

## 4. LLM GENERATION BOUNDARIES

### LLM DOES generate:

| Field | Section | Description |
|-------|---------|-------------|
| `situation_picks` | 0 | 3 situation-based recommendations (uses TCO data) |
| `category_criteria.myth_busting` | 2-1 | Category-specific spec myth |
| `category_criteria.real_differentiator` | 2-2 | Hidden cost factor unique to category |
| `category_criteria.decision_fork` | 2-3 | Home/lifestyle type branching |
| `product.highlight` | 3 | One-line product highlight |
| `product.recommendation_reason` | 4 | Why to buy (must cite TCO) |
| `product.caution_reason` | 4 | Why to avoid (must cite data) |
| `faqs` | 6 | 5 Q&A pairs (NOT repeating main content) |
| `title` | — | Blog post title with SEO keywords |

### LLM NEVER generates:

| Data | Source |
|------|--------|
| Any price or cost number | Part A: price-tracker |
| Resale values | Part A: resale-tracker |
| Repair costs | Part A: repair-analyzer |
| AS turnaround days | Part A: repair-analyzer |
| Automation rate percentage | Part A: maintenance-calc |
| Review/sample counts | Part A: all modules |
| TCO calculation results | Part A: tco-engine |

**Enforcement:** ContentWriter injects all numbers from Part A JSON. LLM output is parsed for narrative fields only. Any number in LLM output is discarded and replaced with Part A data.

---

## 5. CONTENT ANTI-PATTERNS

### DO NOT:

| Anti-pattern | Why it's bad | Correct approach |
|-------------|-------------|-----------------|
| Start with question hook ("후회하셨나요?") | Generic, every affiliate blog does this | Start with conclusion (situation picks) |
| Explain TCO formula in Section 2 | Same content for every category, no differentiation | Use category-specific criteria |
| Repeat Section 3 in Section 5 | Reader feels "I already read this" | Section 5 = urgency framing only |
| Repeat Section 2 in FAQ | Inflates word count without new value | FAQ = new angles only |
| Use different CTA wording per product | Confuses reader, complicates testing | Unified: "최저가 확인하기" |
| Show "월 유지시간: 36분" | Cannot be reliably sourced | Show "자동화율: 67%" instead |
| Let LLM generate any numbers | Hallucination risk | All numbers from Part A only |

---

## 6. SECTION-BY-SECTION CHANGE LOG (vs Current Implementation)

| Section | Current (Developed) | Required Change | Priority |
|---------|-------------------|-----------------|----------|
| **0** | Problem-question hook | → Conclusion-first (situation picks + TCO) | 🔴 Critical |
| **1** | Credibility stats | ✅ Keep as-is | — |
| **2** | TCO formula explanation | → Category-specific 3 criteria (myth/differentiator/fork) | 🔴 Critical |
| **3** | Quick pick table | ⚠️ Add unified CTA wording, add 3년 실비용 row | 🟡 Medium |
| **4** | TCO table (quantitative only) | → Add Section 4-5: qualitative table (AS days + automation rate) | 🔴 Critical |
| **5** | TOP 3 summary + push | → Price volatility urgency (no summary repeat) | 🟡 Medium |
| **6** | FAQ | ⚠️ Ensure no content overlap with Section 2 or 4 | 🟡 Medium |

### New LLM Prompt Fields Required:

```python
# Add to enrichment prompt output schema:
{
    "category_criteria": {
        "myth_busting": "string — category-specific spec myth to bust",
        "real_differentiator": "string — hidden cost factor for this category",
        "decision_fork": "string — home/lifestyle type branching"
    }
    # Existing fields remain unchanged
}
```

### New Template Section Required:

```
templates/
├── section_0_hook.jinja2          ← REWRITE (conclusion-first)
├── section_1_credibility.jinja2   ← keep
├── section_2_criteria.jinja2      ← REWRITE (3 category-specific criteria)
├── section_3_quick_pick.jinja2    ← minor update (unified CTA)
├── section_4_tco_deep_dive.jinja2 ← ADD section 4-5 qualitative table
├── section_5_action_trigger.jinja2← REWRITE (urgency, not summary)
├── section_6_faq.jinja2           ← ADD overlap check logic
└── blog_post.jinja2               ← keep (master assembler)
```

### New Part A Data Fields Required:

```json
{
    "product_id": "...",
    "tco": {
        "purchase_price_avg": 997930,
        "resale_value_2yr": 400000,
        "expected_repair_cost": 8400,
        "real_cost_3yr": 606330
    },
    "qualitative": {
        "as_turnaround_days": 3,
        "maintenance_tasks": [
            {"task": "필터 교체 알림", "automated": true},
            {"task": "프리필터 세척", "automated": false},
            {"task": "자동 풍량 조절", "automated": true},
            {"task": "필터 잔여 수명 표시", "automated": true},
            {"task": "공기질 자동 감지", "automated": true}
        ],
        "automation_rate": 80
    }
}
```

---

## 7. PERSUASION FLOW SUMMARY

```
Section 0: "답은 이거야" (결론)
    ↓ 독자 반응: "근데 이거 믿을 수 있어?"
Section 1: "이만큼 분석했어" (신뢰)
    ↓ 독자 반응: "그래, 근데 뭘 기준으로?"
Section 2: "너가 보던 기준은 틀렸어" (재프레이밍)
    ├─ 2-1: 스펙 미신 해체
    ├─ 2-2: 진짜 차별점 제시
    └─ 2-3: 네 집 상황에 따라 달라
    ↓ 독자 반응: "오 그럼 나는 어떤 타입이지?"
Section 3: "너는 이거 사" (즉시 추천)
    ↓ 독자 반응: "왜 이게 나한테 맞는데?"
Section 4: "데이터로 증명할게" (심층 근거)
    ├─ 4-1~3: 제품별 추천/주의 + 데이터
    ├─ 4-4: 정량 TCO 비교표
    └─ 4-5: 정성 체감 비교표
    ↓ 독자 반응: "오케이, 근데 지금 사야 해?"
Section 5: "가격은 계속 바뀌니까 지금 확인해" (행동 유도)
    ↓ 독자 반응: "아 그전에 몇 가지 궁금한 게..."
Section 6: "여기서 다 답해줄게" (이탈 방지)
```

**Core principle:** Every section answers the reader's natural next question. If any section fails to do this, the reader exits.

---

*Document version: 1.0*
*Last updated: 2026-02-08*
*Compatible with: TCO-Driven Affiliate Marketing Automation System v1.0*
*Usage: Load as RAG context for Part B ContentWriter and LLM prompt construction*