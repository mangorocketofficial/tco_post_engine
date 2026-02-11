# A4 Schema Sync — TCO 계산 및 Export 수정 사항

> **Priority:** 🔴 Critical — TCO 계산 오류, 기간 정의 불명확, 메타데이터 누락
> **Trigger:** end-to-end 파이프라인 테스트 검증 (가습기 카테고리)
> **Status:** 요청 대기 중

---

## 문제 정의

### 1. 기간 정의 불명확

A3에서 산출하는 `expected_repair_cost`는 **1회 기대값**이지만, A4에서 이를 3년치인지 1회인지 명확히 정의되지 않았다.

**현황:**
- A3: `expected_repair_cost = 28,500원` (1회 고장 시 기대 수리비)
- A4: export에 `expected_repair_cost_3yr` 필드 존재하지만 계산 방식 불명확

**결과:** 제품별로 일관되지 않은 TCO 계산
```
조지루시:  329,000 + 85,500 - 160,000 = 254,500  ← 3년 사용 (28,500 × 3)
케어미스트: 125,000 + 77,400 - 60,000 = 142,400  ← 불일치 (어떤 조합도 불가)
```

### 2. Export 필드 누락

A0에서 생성되는 `selected_tier`, `tier_scores`, `tier_product_counts`가 A4 export에 전달되지 않음.

**영향:** Part B에서 Section 0 hook, SEO 타이틀, Section 1 신뢰성 생성 불가
```
❌ "가습기 추천 TOP3 — 3년 실비용 비교" (가격대 불명)
✅ "프리미엄 가습기 추천 TOP3 — 3년 실비용 비교" (가격대 명시)
```

---

## 수정 사항

### 수정 1: 기간 정의 통일

**정의:**

```
A3 output:
  expected_repair_cost = 1회 기대 수리비
  = Σ(고장유형[i].avg_cost × 고장유형[i].probability)

A4 계산:
  expected_repair_cost_3yr = expected_repair_cost × 3
  (3년간 매년 동일 확률로 고장 발생 가정)

  real_cost_3yr = purchase_price + expected_repair_cost_3yr - resale_price
```

**수정 대상: `src/part_a/tco_engine/calculator.py`**

```python
# 현재 (불명확)
expected_repair = a3_product["expected_repair_cost"]
real_cost = purchase_price + expected_repair - resale_price

# 수정 후 (명확)
expected_repair_1yr = a3_product["expected_repair_cost"]  # A3 원본
expected_repair_3yr = expected_repair_1yr * 3              # A4 계산
real_cost_3yr = purchase_price + expected_repair_3yr - resale_price
```

### 수정 2: Export 스키마 정의

**필드 추가:**

```json
{
  "category": "{CATEGORY}",
  "generated_at": "ISO 8601 timestamp",

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

  "products": [
    {
      "product_id": "string",
      "product_name": "string",
      "tco": {
        "purchase_price": 329000,
        "expected_repair_cost": 28500,
        "expected_repair_cost_3yr": 85500,
        "resale_price": 160000,
        "resale_confidence": "high",
        "real_cost_3yr": 254500
      }
    }
  ]
}
```

**필드 설명:**

| 필드 | 소스 | 설명 | Part B 용도 |
|------|------|------|-----------|
| `selected_tier` | A0 pass-through | 선정된 가격 티어 | Section 0 hook, SEO 타이틀 |
| `tier_scores` | A0 pass-through | 티어별 점수 | 메타데이터 |
| `tier_product_counts` | A0 pass-through | 티어별 제품 수 | Section 1 신뢰성 |
| `expected_repair_cost` | A3 원본 | 1회 기대 수리비 (투명성) | 상세 설명: "연간 약 28,500원" |
| `expected_repair_cost_3yr` | A4 계산 | 3년 누적 (28,500 × 3) | Section 4-4 정량표, real_cost 계산 |
| `real_cost_3yr` | A4 계산 | 최종 3년 실비용 | Section 0, 3, 4, 5 |

**수정 대상: `src/part_a/tco_engine/exporter.py`**

```python
# A0 데이터 로드 후 export에 추가
export["selected_tier"] = a0_data.get("selected_tier", "")
export["tier_scores"] = a0_data.get("tier_scores", {})
export["tier_product_counts"] = a0_data.get("tier_product_counts", {})

# 각 제품 TCO 객체에 필드 추가
for product in export["products"]:
    product["tco"]["expected_repair_cost"] = a3_value
    product["tco"]["expected_repair_cost_3yr"] = a3_value * 3
    product["tco"]["real_cost_3yr"] = purchase_price + (a3_value * 3) - resale_price
```

### 수정 3: Part B 출력 규칙

**Section 별 필드 사용:**

| Section | 사용 필드 | 표현 예시 |
|---------|----------|---------|
| Section 0 (hook) | `selected_tier` | "프리미엄 가습기 3개를 비교했습니다" |
| Section 0 (요약) | `real_cost_3yr` | "3년 실비용: 254,500원" |
| Section 1 (신뢰성) | `tier_scores`, `tier_product_counts` | "20개 제품 중 프리미엄 가격대 7개를 심층 분석" |
| Section 3 (추천표) | `real_cost_3yr` | 정렬 기준, CTA 위치 |
| Section 4-4 (정량표) | `expected_repair_cost_3yr`, `resale_price` | 3년 누적 비용 표시 |
| Section 4 (상세) | `expected_repair_cost` | "연간 기대 수리비 약 28,500원 (3년 누적 85,500원)" |
| SEO 타이틀 | `selected_tier` | "프리미엄 가습기 추천 TOP3" |

---

## 검증 체크리스트

A4 코드 수정 완료 후 아래를 검증한다:

```
[ ] calculator.py에서 expected_repair_cost_3yr = expected_repair_cost × 3 계산
[ ] exporter.py에서 selected_tier, tier_scores, tier_product_counts pass-through
[ ] 각 제품: expected_repair_cost_3yr == expected_repair_cost × 3 일치
[ ] 각 제품: real_cost_3yr == purchase_price + expected_repair_cost_3yr - resale_price 일치
[ ] Export JSON에 모든 필드 포함 (누락 필드 없음)
[ ] Part B ContentWriter가 export JSON 읽을 때 TypeError 없음
```

---

## 영향도

| 모듈 | 변경 | 영향 |
|-----|------|------|
| `calculator.py` | 기간 정의 명확화 | TCO 계산 정확성 향상 |
| `exporter.py` | 필드 pass-through | A0 메타데이터 보존 |
| `Part B ContentWriter` | 필드 활용 | Section 생성 품질 향상 |
| 테스트 | 기댓값 업데이트 | test_calculator.py, test_exporter.py 수정 필요 |

---

## 타임라인

1. **A4 코드 수정** (PartA 담당)
2. **Part B ContentWriter 수정** (PartB 담당)
3. **Integration test** (Lead 담당)
4. **E2E 테스트** (가습기 카테고리 재실행)

---

*Document version: 1.0*
*Created: 2026-02-09*
*Status: Pending Implementation*
