# DEV REQUEST: Pipeline Test 결과 수정 — 가습기 카테고리

> **Priority:** 🔴 Critical — TCO 계산 오류로 블로그 수치 신뢰 불가
> **Trigger:** 가습기 카테고리 end-to-end 테스트 결과 검증
> **Date:** 2026-02-09

---

## 수정 1: A2 RUNBOOK — 추정값 금지 규칙 추가

### 문제

A2에서 Claude WebSearch가 실제 중고 매물을 충분히 찾지 못하자, "신품가의 약 48%"라는 공식으로 가격을 **생성**했다. 3개 제품 모두 잔존율이 48~49%로 거의 동일하고, `collected_prices`가 비현실적으로 균일하다:

```
조지루시: [155000, 158000, 160000, 162000, 165000]  ← 2,000~3,000원 간격
케어미스트: [55000, 58000, 60000, 62000]             ← 2,000~3,000원 간격
스텐팟: [168000, 170000, 172000, 175000, 178000]     ← 2,000~3,000원 간격
```

실제 중고 매물 가격은 이렇게 균일하지 않다. 이건 실제 데이터가 아니라 Claude가 만든 추정값이다.

### 수정

**RUNBOOKV3 Step A2 실행 절차에 아래 규칙을 추가한다:**

```markdown
### ⚠️ 데이터 수집 원칙 (필수)

1. **추정/계산 금지** — "신품가의 X%", "일반적으로 중고가는..." 같은 
   공식 기반 추정값을 절대 사용하지 않는다.
2. **실제 매물만 수집** — 당근마켓/번개장터/중고나라에서 실제로 
   게시된 매물의 가격만 collected_prices에 기록한다.
3. **출처 명시** — 가능하면 매물 URL 또는 "당근마켓 2026-02-08 게시" 
   같은 구체적 출처를 notes에 기록한다.
4. **못 찾으면 0으로 처리** — 실제 매물을 3건 이상 찾지 못하면:
   - confidence: "none"
   - resale_price: 0
   - filter_note: "실제 매물 부족 — 중고 환급액 0으로 처리"
   - TCO에서 중고 환급 없이 계산 (보수적 추정)
5. **균일 간격 자기 검증** — collected_prices의 간격이 비정상적으로 
   균일하면 (모든 간격이 동일) 실제 매물인지 재확인한다.
```

### 영향

`resale_price: 0`이 되면 TCO가 높아지지만, 거짓 데이터로 낮은 TCO를 보여주는 것보다 낫다. 블로그에서는 "중고 거래 데이터가 부족하여 환급액을 반영하지 않았습니다"로 표현하면 된다.

---

## 수정 2: TCO 수식 — expected_repair_cost 기간 정의 명확화

### 문제

A3의 `expected_repair_cost`는 **1회 기대값** (고장유형별 `avg_cost × probability` 합산)이다:

```
조지루시: 35000×0.08 + 45000×0.05 + 28000×0.04 + ... = 28,500원
```

그런데 TCO export에는 `expected_repair_cost_3yr: 85,500` (= 28,500 × 3)이 존재하고, `real_cost_3yr` 계산에 이 3년치 값을 사용한 제품과 사용하지 않은 제품이 섞여 있다.

**검증:**

```
조지루시:  329,000 + 85,500 - 160,000 = 254,500  ← export 값과 일치 (3년 수리비 사용)
스텐팟:    349,000 + 90,600 - 172,000 = 267,600  ← export 값과 일치 (3년 수리비 사용)
케어미스트: 125,000 + 77,400 - 60,000 = 142,400  ← export는 42,400 (불일치 ❌)
```

케어미스트만 42,400원으로, 어떤 조합으로도 이 숫자가 도출되지 않는다. 계산 버그가 있다.

### 수정

#### 2-1. 기간 정의 통일

**RUNBOOK A3와 A4에 명확히 정의한다:**

```markdown
A3 output:
  expected_repair_cost = 1회 기대 수리비 (고장유형별 avg_cost × probability 합산)

A4 TCO 계산:
  expected_repair_cost_3yr = expected_repair_cost × 3 (3년간 매년 동일 확률 가정)
  
  real_cost_3yr = purchase_price + expected_repair_cost_3yr - resale_price
               = purchase_price + (expected_repair_cost × 3) - resale_price
```

> **× 3 곱셈은 A4에서 수행한다.** A3는 1회 기대값만 출력한다.

#### 2-2. A4 코드 수정

`A4_schema_sync.md`의 TCO 수식을 업데이트한다:

```python
# calculator.py
expected_repair_3yr = a3_product["expected_repair_cost"] * 3
real_cost_3yr = purchase_price + expected_repair_3yr - resale_price
```

#### 2-3. A4 Export 스키마 수정

```json
{
  "tco": {
    "purchase_price": 329000,
    "expected_repair_cost": 28500,
    "expected_repair_cost_3yr": 85500,
    "resale_price": 160000,
    "resale_confidence": "low",
    "real_cost_3yr": 254500
  }
}
```

두 필드를 모두 출력한다:
- `expected_repair_cost` — A3 원본 (1회 기대값). 투명성을 위해 유지.
- `expected_repair_cost_3yr` — A4가 계산한 3년치. `real_cost_3yr` 계산에 사용된 값.

Part B 블로그에서는:
- Section 4-4 정량 비교표: `expected_repair_cost_3yr` 사용 (3년 실비용이니까)
- 개별 제품 설명: "연간 기대 수리비 약 28,500원 (3년 누적 85,500원)" 으로 표현

#### 2-4. 케어미스트 42,400원 디버깅

이 숫자의 출처를 확인해야 한다. 가능한 원인:

| 가설 | 계산 | 결과 | 일치? |
|------|------|------|-------|
| 1회 수리비 사용 | 125,000 + 25,800 - 60,000 | 90,800 | ❌ |
| 3년 수리비 사용 | 125,000 + 77,400 - 60,000 | 142,400 | ❌ |
| 수리비 빼기 | 125,000 - 25,800 - 60,000 | 39,200 | ❌ |
| 수리비 3년 빼기 | 125,000 - 77,400 - 60,000 | -12,400 | ❌ |
| resale - repair | 60,000 - 25,800 + 8,200? | 42,400 | 🤷 |

어떤 공식으로도 42,400이 도출되지 않는다. **이 값은 Claude WebSearch가 TCO JSON을 수동으로 작성하면서 잘못 계산한 것으로 추정된다.** A4가 Python 코드로 자동 계산하면 이 문제는 해결된다.

**즉시 조치:** A4 코드가 수정될 때까지, RUNBOOK에 **TCO 수식 검증 체크리스트**를 추가한다:

```markdown
### A4 출력 검증 (필수)

각 제품에 대해 아래 수식이 정확히 일치하는지 확인한다:

  expected_repair_cost_3yr == expected_repair_cost × 3
  real_cost_3yr == purchase_price + expected_repair_cost_3yr - resale_price

하나라도 불일치하면 계산을 다시 수행한다.
```

---

## 수정 3: TCO Export — 선정 티어 정보 포함

### 문제

TCO export에 `selected_tier`와 `tier_scores`가 없다. A0에는 이 정보가 있지만, A4 merge 과정에서 누락되었다. 어떤 가격대를 타겟한 블로그인지 메타데이터가 없으면 Part B에서 SEO 타이틀과 Section 0 hook을 적절히 생성할 수 없다.

예시:
- ✅ "가열식 가습기 추천 TOP3 — **프리미엄** 3년 실비용 비교 (2026)"
- ❌ "가열식 가습기 추천 TOP3 — 3년 실비용 비교 (2026)" ← 어떤 가격대인지 모름

### 수정

**A4 export JSON에 A0의 티어 메타데이터를 포함한다:**

```json
{
  "category": "가습기",
  "generated_at": "2026-02-09T10:15:00Z",
  "selected_tier": "premium",
  "tier_scores": {
    "premium": 1.817,
    "mid": 1.234,
    "budget": 0.891
  },
  "tier_product_counts": {
    "premium": 7,
    "mid": 8,
    "budget": 5
  },
  "products": [ ... ]
}
```

**소스:** A0 output의 `selected_tier`, `tier_scores`, `tier_product_counts` 필드를 A4가 그대로 pass-through한다.

**A4 코드 변경 (`exporter.py`):**

```python
# A0 JSON 로드 후
export["selected_tier"] = a0_data.get("selected_tier", "")
export["tier_scores"] = a0_data.get("tier_scores", {})
export["tier_product_counts"] = a0_data.get("tier_product_counts", {})
```

**Part B 활용:**

| 필드 | Part B 활용 |
|------|------------|
| `selected_tier` | Section 0 hook: "프리미엄 가습기 3개를 비교했습니다" |
| `selected_tier` | SEO 타이틀: "프리미엄 가습기 추천 TOP3 — 3년 실비용 비교" |
| `tier_scores` | Section 1 신뢰성: "20개 제품 중 프리미엄 가격대 7개를 심층 분석" |

---

## 수정 대상 파일 요약

| 수정 | 대상 | 유형 |
|------|------|------|
| 수정 1 (추정값 금지) | RUNBOOKV3.md — Step A2 | RUNBOOK 텍스트 추가 |
| 수정 2-1 (기간 정의) | RUNBOOKV3.md — Step A3, A4 | RUNBOOK 텍스트 추가 |
| 수정 2-2 (× 3 계산) | A4_schema_sync.md — calculator.py | 코드 수정 요청서 업데이트 |
| 수정 2-3 (export 스키마) | A4_schema_sync.md — exporter.py | 코드 수정 요청서 업데이트 |
| 수정 2-4 (검증 체크) | RUNBOOKV3.md — A4 확인사항 | RUNBOOK 텍스트 추가 |
| 수정 3 (티어 정보) | A4_schema_sync.md — exporter.py | 코드 수정 요청서 업데이트 |

---

## 수정 후 예상 TCO (가습기)

수정 2 적용 + 수정 1 적용 시 (중고 데이터 부족 → resale_price: 0):

```
조지루시:  329,000 + (28,500 × 3) - 0 = 414,500원
케어미스트: 125,000 + (25,800 × 3) - 0 = 202,400원
스텐팟:    349,000 + (30,200 × 3) - 0 = 439,600원
```

중고 데이터가 실제로 확보된 경우 (예: 조지루시만 실제 매물 5건 발견):

```
조지루시:  329,000 + 85,500 - 160,000 = 254,500원
케어미스트: 125,000 + 77,400 - 0       = 202,400원  (중고 데이터 없음)
스텐팟:    349,000 + 90,600 - 0        = 439,600원  (중고 데이터 없음)
```

→ 이래도 TCO 차이는 **2배 이상** 벌어지므로 블로그 변별력은 충분하다.

---

*Document version: 1.0*
*Author: Lead*