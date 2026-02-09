# TCO Pipeline Runbook v3

> Claude Code가 이 문서를 읽고 순서대로 실행하는 파이프라인 가이드입니다.
> 사용법: "RUNBOOK.md를 보고 {카테고리명} 파이프라인 실행해줘"

---

## 파이프라인 전체 흐름

```
A0 (제품 선정) → A2 (중고 시세) → A3 (수리/AS) → A5 (리뷰 분석) → A4 (TCO 계산) → B (블로그 생성)
```

> A0의 Naver Shopping `lprice`를 구매가 단일 소스로 사용한다. A1(다나와 가격 수집)은 파이프라인에서 제외되었다.

| Step | 실행 주체 | 입력 | 출력 | 블로그 매핑 |
|------|-----------|------|------|------------|
| A0 | Python CLI | 카테고리 키워드 | `a0_selected_{CAT}.json` | Section 3 (제품 선정) + 구매가 |
| A2 | Claude WebSearch | 제품명 3개 | `a2_resale_{CAT}.json` | Section 4-4 (중고 환급액) |
| A3 | Claude WebSearch | 제품명 3개 | `a3_repair_{CAT}.json` | Section 4-4 (수리비) + 4-5 (AS일수, 자동화율) |
| A5 | Claude WebSearch | 제품명 3개 | `a5_reviews_{CAT}.json` | Section 2 (재프레이밍 3가지) |
| A4 | Python CLI | A0 + A2~A5 | `tco_{CAT}.json` | 전체 데이터 통합 |
| B | Python CLI | `tco_{CAT}.json` | 블로그 포스트 | 최종 콘텐츠 |

---

## 사전 조건

```bash
pip install -r requirements.txt
```

- `.env` 파일에 필요한 API 키 설정 완료
- `config/` 디렉토리에 카테고리 YAML 설정 존재 (없으면 Step 0에서 생성)

---

## Step 0: 변수 설정 및 카테고리 설정

파이프라인 시작 전, 아래 변수를 카테고리에 맞게 설정한다.

```
CATEGORY = "로봇청소기"                    # 카테고리 한글명
KEYWORD  = "로봇청소기"                    # 검색 키워드
CAT_SLUG = "robot_vacuum"                 # 카테고리 영문 슬러그 (파일명용)
CONFIG   = "config/category_{CAT_SLUG}.yaml"  # 카테고리 설정 파일
```

### 새 카테고리 설정 (카테고리 YAML이 없을 때)

`config/category_{CAT_SLUG}.yaml`이 존재하지 않으면 **파이프라인 시작 전에** 아래 절차로 생성한다.

#### 1. 카테고리 YAML 생성

```yaml
# config/category_{CAT_SLUG}.yaml
# 예시: config/category_dehumidifier.yaml

name: "제습기"
search_terms: ["제습기"]                    # A0 Naver Shopping API 검색어
danawa_category_code: ""                    # 비워둠 (사용하지 않음)

negative_keywords: ["불만", "후회", "실망", "반품", "고장", "AS", "수리", "오류"]
positive_keywords: ["추천", "만족", "최고", "잘샀다", "좋아요", "강추"]

price_range:
  min: 0
  max: 10000000

max_product_age_months: 18
min_community_posts: 20

# A3 수리/AS 검색 키워드
repair_keywords:
  repair: ["수리", "AS", "고장", "서비스센터", "교체", "부품"]
  failure_types: []                         # ← 카테고리에 맞게 채운다 (아래 참조)

# A3 유지관리 체크리스트
maintenance_checklist: []                   # ← 카테고리에 맞게 채운다 (아래 참조)
```

#### 2. failure_types 및 maintenance_checklist 채우기

**Claude가 WebSearch로 해당 카테고리의 일반적인 고장 유형과 유지관리 항목을 조사한다:**

```
검색어: "{CATEGORY} 고장 유형 종류"
검색어: "{CATEGORY} 유지관리 관리법 체크리스트"
검색어: "{CATEGORY} AS 수리 부품"
```

결과를 바탕으로:

- `failure_types`: 해당 카테고리에서 발생하는 주요 고장 유형 5~7개
- `maintenance_checklist`: 해당 카테고리의 공통 유지관리 항목 5~7개 (각 항목에 `auto/manual` 판단용)

**예시 — 제습기:**

```yaml
repair_keywords:
  repair: ["수리", "AS", "고장", "서비스센터", "교체", "부품"]
  failure_types: ["컴프레서", "팬모터", "센서", "배수", "냉매", "소음", "기판"]

maintenance_checklist:
  - "필터 청소"
  - "물통 비우기"
  - "배수호스 점검"
  - "외부 청소"
  - "코일/열교환기 청소"
  - "습도센서 점검"
```

#### 3. 확인사항

- [ ] `config/category_{CAT_SLUG}.yaml` 생성 확인
- [ ] `search_terms`에 올바른 검색 키워드 설정
- [ ] `failure_types`에 카테고리별 고장 유형 5~7개 입력
- [ ] `maintenance_checklist`에 유지관리 항목 5~7개 입력

> **기존 카테고리 설정 파일이 이미 있으면 이 단계를 건너뛴다.**

---

## Step A0: 제품 선정 (Python)

3개 제품을 자동 선정한다. output JSON에서 제품명을 기록해둔다.

```bash
python -m src.part_a.product_selector.main --mode final --keyword "{KEYWORD}" --output data/processed/a0_selected_{CATEGORY}.json
```

### 티어 지정 옵션 (`--tier`)

기본 동작은 가장 높은 점수의 티어를 자동 선정하지만, `--tier` 옵션으로 특정 가격대 티어를 지정할 수 있다.

```bash
# 자동 (기본값) — 점수가 가장 높은 티어에서 TOP 3 선정
python -m src.part_a.product_selector.main --category "{KEYWORD}" --output ...

# 프리미엄 티어 강제 지정
python -m src.part_a.product_selector.main --category "{KEYWORD}" --tier premium --output ...

# 중간 가격대 티어 강제 지정
python -m src.part_a.product_selector.main --category "{KEYWORD}" --tier mid --output ...

# 저가 티어 강제 지정
python -m src.part_a.product_selector.main --category "{KEYWORD}" --tier budget --output ...
```

| 값 | 설명 |
|---|------|
| *(생략)* | 자동 — 티어별 TOP-3 합산 점수가 가장 높은 티어에서 선정 |
| `premium` | 고가 제품군에서 TOP 3 선정 |
| `mid` | 중간 가격대 제품군에서 TOP 3 선정 |
| `budget` | 저가 제품군에서 TOP 3 선정 |

> 지정 티어에 3개 미만 후보가 있으면 인접 티어에서 자동 보충한다.

### 확인사항
- `data/processed/a0_selected_{CATEGORY}.json` 생성 확인
- 선정된 3개 제품명 기록:
  - PRODUCT_1 = ""
  - PRODUCT_2 = ""
  - PRODUCT_3 = ""

---

## Step A2: 중고 시세 조사 (Claude Code WebSearch)

> **이 단계는 Claude Code가 WebSearch/WebFetch를 사용해서 직접 수행한다.**

### ⚠️ 데이터 수집 원칙 (필수)

1. **추정/계산 금지** — "신품가의 X%", "일반적으로 중고가는..." 같은 공식 기반 추정값을 절대 사용하지 않는다.
2. **실제 매물만 수집** — 당근마켓/번개장터/중고나라에서 실제로 게시된 매물의 가격만 collected_prices에 기록한다.
3. **출처 명시** — 가능하면 매물 URL 또는 "당근마켓 2026-02-08 게시" 같은 구체적 출처를 notes에 기록한다.
4. **못 찾으면 0으로 처리** — 실제 매물을 3건 이상 찾지 못하면:
   - confidence: "none"
   - resale_price: 0
   - filter_note: "실제 매물 부족 — 중고 환급액 0으로 처리"
   - TCO에서 중고 환급 없이 계산 (보수적 추정)
5. **균일 간격 자기 검증** — collected_prices의 간격이 비정상적으로 균일하면 (모든 간격이 동일) 실제 매물인지 재확인한다.

### 사전 입력 — A0 가격 읽기 (필수)

A0 출력 파일을 읽는다: `data/processed/a0_selected_{CATEGORY}.json`

각 제품의 `price`를 기록한다:
  - PRODUCT_1_PRICE = a0_output.selected_products[0].price
  - PRODUCT_2_PRICE = a0_output.selected_products[1].price
  - PRODUCT_3_PRICE = a0_output.selected_products[2].price

이 가격이 중고 환급 예상액 산출의 기준(base price)이 된다.

### 실행 절차

1. **검색 수행** — 제품별로 아래 검색어로 WebSearch 실행 (연도 구분 없이 전체 중고가 수집):
   - `"{PRODUCT_N} 중고" 당근마켓`
   - `"{PRODUCT_N} 중고" 번개장터`
   - `"{PRODUCT_N} 중고 가격 중고나라"`

2. **가격 수집** — 검색 결과와 WebFetch로 해당 제품의 **모든 중고 매물 가격**을 수집한다.
   - 연도/사용기간 구분 없이 찾을 수 있는 모든 가격을 리스트로 모은다.
   - 부품 단품, 케이스만 판매, 교환 글 등은 제외한다.

3. **Median ±10% 필터링** — 수집된 가격 리스트에서 중고 환급 예상액을 산출한다:

   ```
   (1) 수집된 모든 가격의 중간값(median) 계산
   (2) median × 0.9 ~ median × 1.1 범위 안의 가격만 유효 처리
   (3) 유효 가격의 평균 = resale_price (중고 환급 예상액)
   ```

   **예시 (브라운 310BT):**
   ```
   수집: [15000, 18000, 20000, 22000, 23000, 24000, 25000, 28000, 45000]
   Median: 23,000원
   ±10% 범위: 20,700 ~ 25,300원
   유효 가격: [22000, 23000, 24000, 25000]
   resale_price = 23,500원
   ```

   **엣지 케이스 처리:**

   | 상황 | 처리 |
   |------|------|
   | 수집 가격 3개 미만 | median 그대로 사용, `confidence: "low"` 설정 |
   | ±10% 범위 내 가격 2개 미만 | 범위를 ±20%로 확대, `filter_note`에 "Widened to ±20%" 기록 |
   | 검색 결과 0건 | `resale_price: 0`, `confidence: "none"`, notes에 "No resale data found" |

4. **교차 검증** — A0 가격 대비 중고 환급 예상액의 비율을 확인한다:
   - `resale_price / PRODUCT_N_PRICE` 가 0.1~0.8 범위 → 정상
   - 0.8 초과 → notes에 "중고가가 신품가에 근접 — 검증 필요" 기록
   - 0.1 미만 → notes에 "중고가가 비정상적으로 낮음 — 검증 필요" 기록

5. **결과를 JSON으로 저장**:

```bash
# 파일 경로: data/processed/a2_resale_{CATEGORY}.json
```

### A2 출력 JSON 스키마

```json
{
  "category": "{CATEGORY}",
  "searched_at": "ISO 8601",
  "source": "claude_web_search",
  "products": [
    {
      "product_name": "제품 전체명",
      "purchase_price": 0,
      "purchase_price_source": "a0",
      "resale": {
        "resale_price": 0,
        "median_raw": 0,
        "filter_range_pct": 10,
        "sample_count": 0,
        "sample_count_after_filter": 0,
        "confidence": "high | medium | low | none",
        "sources": ["당근마켓", "번개장터"],
        "collected_prices": [0, 0, 0],
        "filter_note": ""
      },
      "notes": "검색 중 특이사항 메모"
    }
  ]
}
```

**필드 설명:**

| 필드 | 설명 |
|------|------|
| `resale_price` | 최종 중고 환급 예상액 (median ±10% 유효 가격의 평균) |
| `median_raw` | 필터링 전 원본 중간값 (감사용) |
| `filter_range_pct` | 적용된 필터 범위 (기본 10, 확대 시 20) |
| `sample_count` | 필터링 전 수집된 총 가격 수 |
| `sample_count_after_filter` | ±10% 필터 통과한 가격 수 |
| `confidence` | `"high"` (5+건), `"medium"` (3~4건), `"low"` (1~2건), `"none"` (0건) |
| `collected_prices` | 수집된 원본 가격 리스트 (감사용) |
| `filter_note` | 정상 시 빈 문자열. "Widened to ±20%" 등 엣지 케이스 기록 |

---

## Step A3: 수리비 및 AS 비용 조사 (Claude Code WebSearch)

> **이 단계는 Claude Code가 WebSearch/WebFetch를 사용해서 직접 수행한다.**

각 제품에 대해 아래 절차를 수행한다:

### 실행 절차

1. **검색 수행** — 제품별로 아래 검색어로 WebSearch 실행:
   - `"{PRODUCT_N} 수리비 AS 비용"`
   - `"{PRODUCT_N} 고장 수리 후기 서비스센터"`
   - `"{PRODUCT_N} 부품 교체 비용"`
   - `"{BRAND_N} {CATEGORY} AS 기간 보증"`
   - `"{PRODUCT_N} 스펙 사양 공식"` ← 유지관리 자동화율 산출용

2. **데이터 추출** — 검색 결과에서 아래 정보 수집:
   - 고장 유형별 수리 비용 (모터, 센서, 배터리 등)
   - AS 평균 소요 기간 (일)
   - 무상 보증 기간
   - 유상 수리 비용 범위

3. **유지관리 자동화율 산출**:
   - `config/category_{CAT_SLUG}.yaml`의 `maintenance_checklist`를 기준 항목으로 사용
   - 공식 스펙/제품 페이지에서 해당 제품이 각 항목을 자동 지원하는지 확인
   - 각 항목을 `자동(auto)` 또는 `수동(manual)`으로 이진 분류
   - `automation_rate = (auto 항목 수 / 전체 항목 수) × 100`

   > 카테고리 설정 파일에 `maintenance_checklist`가 없으면 Step 0에서 먼저 생성한다.

4. **기대 수리비 계산**:
   - 고장 유형별 `avg_cost × probability` 합산
   - probability는 커뮤니티 언급 빈도 기반 추정

5. **결과를 JSON으로 저장**:

```bash
# 파일 경로: data/processed/a3_repair_{CATEGORY}.json
```

### A3 출력 JSON 스키마

```json
{
  "category": "{CATEGORY}",
  "searched_at": "ISO 8601",
  "source": "claude_web_search",
  "products": [
    {
      "product_name": "제품 전체명",
      "warranty_months": 12,
      "failure_types": [
        {
          "type": "고장유형 (예: sensor, motor, battery)",
          "avg_cost": 0,
          "probability": 0.0,
          "description": "고장 상세 설명",
          "sources": ["URL 또는 출처"]
        }
      ],
      "expected_repair_cost": 0,
      "avg_as_days": 0.0,
      "maintenance_tasks": [
        {"task": "유지관리 항목명", "automated": true}
      ],
      "automation_rate": 0,
      "notes": "검색 중 특이사항 메모"
    }
  ]
}
```

---

## Step A5: 리뷰 분석 (Claude Code WebSearch)

> **이 단계는 Claude Code가 WebSearch/WebFetch를 사용해서 직접 수행한다.**
> **목적:** Part B ContentWriter가 Section 2(카테고리 특화 기준 3가지)를 데이터 기반으로 생성하기 위한 소비자 리뷰 인사이트 수집·분석

### 데이터 → 블로그 매핑

| 분석 프레임 | 매핑 대상 | 블로그 역할 |
|------------|----------|------------|
| 구매 동기 분석 | Section 2-1 (미신 깨기) | "너가 보던 스펙은 의미없어" |
| 만족/불만 키워드 | Section 2-2 (진짜 차별점) | "진짜 봐야 할 건 이거야" |
| 환경별 분기 패턴 | Section 2-3 (갈림길) | "니 집 상황에 따라 달라" |

### 실행 절차

#### 1. 리뷰 수집

제품별로 아래 검색어로 WebSearch를 실행한다. 쿠팡과 네이버 쇼핑 리뷰를 우선 타겟한다.

**필수 검색어 (제품당 4회):**
```
"{PRODUCT_N} 리뷰 쿠팡"
"{PRODUCT_N} 사용 후기 네이버쇼핑"
"{PRODUCT_N} 솔직 후기 장단점"
"{PRODUCT_N} 몇개월 사용 후기"
```

**보충 검색어 (리뷰 부족 시 추가):**
```
"{PRODUCT_N} 장점 단점 정리"
"{PRODUCT_N} 1년 사용기"
"{PRODUCT_N} 후회 추천"
```

#### 2. WebFetch로 리뷰 텍스트 수집

검색 결과 상위 링크에서 리뷰 텍스트를 수집한다.

**수집 규칙:**
- 제품당 최소 30건 이상 리뷰 텍스트 확보 목표
- 1줄 리뷰 제외: "좋아요", "배송 빠름", "추천합니다" 등 3문장 미만 리뷰는 분석 대상에서 제외
- 별점 정보가 있으면 함께 기록
- 리뷰 작성일이 확인 가능하면 함께 기록
- 수집한 리뷰 원문은 저장하지 않음 — 분석 결과만 JSON으로 출력

#### 3. 3가지 프레임으로 분석

수집된 리뷰를 아래 3가지 범용 프레임으로 분석한다. **카테고리 특화 용어를 하드코딩하지 않는다.** LLM이 리뷰에서 자연스럽게 해당 카테고리의 핵심 스펙/기준을 도출하도록 한다.

**프레임 1: 구매 동기 분석 → Section 2-1 (미신 깨기) 용**

- 리뷰에서 `~때문에 샀다`, `~보고 골랐다`, `~때문에 선택`, `~이/가 좋아서` 패턴 탐색
- 구매 동기로 언급되는 스펙/기준을 빈도순으로 TOP 3 집계
- 각 스펙이 실제 만족/불만 리뷰에서도 언급되는지 교차 확인
- 판단 기준:
  - 구매 동기 TOP이지만 만족/불만에서 거의 안 나옴 → `overrated` (미신)
  - 구매 동기에 없지만 불만 TOP → `underrated` (숨은 차별점)

**프레임 2: 만족/불만 키워드 → Section 2-2 (진짜 차별점) 용**

- 긍정 리뷰(별점 4~5 또는 긍정 톤)에서 반복 키워드 TOP 5
- 부정 리뷰(별점 1~2 또는 부정 톤)에서 반복 키워드 TOP 5
- 핵심 도출: 프레임1 구매동기에는 없는데 불만 TOP인 항목 = `hidden_differentiator`

**프레임 3: 환경별 분기 패턴 → Section 2-3 (갈림길) 용**

- 부정 리뷰에서 사용환경 언급 추출 (공간, 가족, 사용패턴, 설치환경)
- 긍정 리뷰에서도 동일 환경 키워드 탐색
- 동일 환경 키워드가 긍정/부정에서 다르게 나타나는 패턴 식별

#### 4. 카테고리 종합 인사이트 도출

3개 제품의 프레임 1/2/3 결과를 종합하여 카테고리 레벨 인사이트를 도출한다.

```
category_insights.most_overrated_spec
    ← 3개 제품 공통으로 구매동기 TOP이지만 만족에 안 나오는 스펙

category_insights.real_differentiator
    ← 3개 제품 공통으로 불만 TOP이지만 구매동기에 없는 요소

category_insights.decision_forks
    ← 환경별 분기 패턴 중 가장 뚜렷한 2~3개
```

#### 5. 결과를 JSON으로 저장

```bash
# 파일 경로: data/processed/a5_reviews_{CATEGORY}.json
```

### 데이터 품질 기준

| 기준 | 최소 요건 | 미달 시 조치 |
|------|----------|-------------|
| 제품당 수집 리뷰 수 | 30건 이상 | 보충 검색어로 추가 수집 |
| 3문장 이상 리뷰 비율 | 50% 이상 | 1줄 리뷰 필터링 강화 |
| 구매동기 추출 건수 | TOP 3 이상 | 검색어에 "~때문에 샀다" 추가 |
| 환경 분기 도출 수 | 2개 이상 | 장기 사용기 검색 추가 |
| 제품 간 비교 가능성 | 공통 키워드 3개+ | 동일 키워드 프레임으로 재분석 |

### A5 출력 JSON 스키마

```json
{
  "category": "{CATEGORY}",
  "searched_at": "ISO 8601",
  "source": "claude_web_search",
  "total_reviews_analyzed": 0,
  "review_sources": ["쿠팡", "네이버쇼핑"],
  "products": [
    {
      "product_name": "제품 전체명",
      "reviews_collected": 0,
      "purchase_motivations": [
        {
          "spec_or_criteria": "리뷰에서 도출한 스펙/기준명",
          "mention_count": 0,
          "appears_in_satisfaction": true,
          "appears_in_complaints": false,
          "verdict": "overrated | justified | underrated"
        }
      ],
      "sentiment_keywords": {
        "positive": [
          {"keyword": "", "count": 0}
        ],
        "negative": [
          {"keyword": "", "count": 0}
        ]
      },
      "hidden_differentiator": "구매동기엔 없지만 불만 TOP인 항목",
      "environment_splits": [
        {
          "environment": "사용환경",
          "key_issue": "핵심 이슈",
          "sentiment": "positive | negative",
          "typical_comment": "대표 리뷰 요약 1문장"
        }
      ]
    }
  ],
  "category_insights": {
    "most_overrated_spec": "카테고리 전체에서 가장 과대평가되는 스펙",
    "real_differentiator": "카테고리 전체에서 실제 만족도를 가르는 핵심 요소",
    "decision_forks": [
      {
        "user_type": "사용자 유형/환경",
        "priority": "이 유형에게 가장 중요한 기준",
        "recommended_product": "해당 유형에 맞는 제품명"
      }
    ]
  }
}
```

---

## Step A4: TCO 계산 및 최종 Export (Python)

A0(구매가) + A2(JSON) + A3(JSON) + A5(JSON) 데이터를 통합하여 TCO를 계산한다.

```bash
python -m src.part_a.tco_engine.main \
  --category "{CATEGORY}" \
  --a0-data data/processed/a0_selected_{CATEGORY}.json \
  --a2-data data/processed/a2_resale_{CATEGORY}.json \
  --a3-data data/processed/a3_repair_{CATEGORY}.json \
  --a5-data data/processed/a5_reviews_{CATEGORY}.json \
  --output data/exports/tco_{CATEGORY}.json
```

### 기간 정의 (필수)

- **A3 output:** `expected_repair_cost` = 1회 기대 수리비 (고장유형별 `avg_cost × probability` 합산)
- **A4 계산:**
  ```
  expected_repair_cost_3yr = expected_repair_cost × 3  (3년간 매년 동일 확률 가정)
  real_cost_3yr = purchase_price + expected_repair_cost_3yr - resale_price
  ```
- **× 3 곱셈은 A4에서만 수행한다.** A3는 1회 기대값만 출력한다.

### A4 Export 스키마 — 필드 정의

```json
{
  "category": "{CATEGORY}",
  "generated_at": "ISO 8601",
  "selected_tier": "premium|mid|budget",
  "tier_scores": { "premium": 1.817, "mid": 1.234, "budget": 0.891 },
  "tier_product_counts": { "premium": 7, "mid": 8, "budget": 5 },
  "products": [
    {
      "tco": {
        "purchase_price": 329000,
        "expected_repair_cost": 28500,
        "expected_repair_cost_3yr": 85500,
        "resale_price": 160000,
        "resale_confidence": "high|medium|low|none",
        "real_cost_3yr": 254500
      }
    }
  ]
}
```

**필드 설명:**
- `selected_tier` — A0에서 선정된 가격 티어 (Section 0 hook, SEO 타이틀 생성용)
- `tier_scores`, `tier_product_counts` — A0 메타데이터 pass-through (Section 1 신뢰성 생성용)
- `expected_repair_cost` — A3 원본 (1회 기대값, 투명성 유지)
- `expected_repair_cost_3yr` — A4가 계산한 3년치 (real_cost_3yr 계산에 실제 사용된 값)

### A4 출력 검증 (필수)

각 제품에 대해 아래 수식이 정확히 일치하는지 확인한다:

```
expected_repair_cost_3yr == expected_repair_cost × 3
real_cost_3yr == purchase_price + expected_repair_cost_3yr - resale_price
```

하나라도 불일치하면 계산을 다시 수행한다.

### 확인사항
- [ ] `data/exports/tco_{CATEGORY}.json` 생성 확인
- [ ] **TCO 수식 검증:** 각 제품의 수식이 위 기간 정의에 따라 정확히 계산되었는지 확인
- [ ] A2의 `resale_price`가 0인 경우 `real_cost_3yr = purchase_price + expected_repair_cost_3yr`로 처리 확인
- [ ] A5 리뷰 인사이트가 export JSON에 포함되었는지 확인
- [ ] `selected_tier`, `tier_scores`, `tier_product_counts`이 A0 데이터에서 pass-through 되었는지 확인

> A4 export JSON 스키마 및 TCO 수식 상세는 `A4_schema_sync.md` 개발 요청서를 참조한다.
```

---

## Step B: 블로그 포스트 생성 (Python)

TCO 데이터로 블로그 글을 생성한다.

```bash
python -m src.part_b.content_writer.main --category "{CATEGORY}" --tco-data data/exports/tco_{CATEGORY}.json
```

### 생성되는 블로그 구조 (7 Sections)

```
Section 0: 결론 먼저 (상황별 추천 3개 + TCO 한 줄 요약)
    ← tco.real_cost_3yr

Section 1: 신뢰성 확보 ("자체 분석 N건")
    ← credibility 필드

Section 2: 카테고리 특화 기준 3가지
    ├─ 2-1: 미신 깨기 ← category_insights.most_overrated_spec
    ├─ 2-2: 진짜 차별점 ← category_insights.real_differentiator
    └─ 2-3: 갈림길 ← category_insights.decision_forks

Section 3: 상황별 추천 요약표 + CTA
    ← tco.real_cost_3yr + highlight

Section 4: TCO 심층 분석
    ├─ 4-1~3: 제품별 상세 + CTA
    ├─ 4-4: 정량 비교표 (구매가, 중고 환급 예상액, 수리비, 실비용)
    └─ 4-5: 정성 비교표 (AS 대기일수, 유지관리 자동화율)

Section 5: 행동 유도 (가격 변동성 + CTA)

Section 6: FAQ (본문 미포함 질문만, repair_context + review_insights 기반)
```

---

## 파이프라인 체크리스트

실행 완료 후 아래 항목을 모두 확인한다.

```
[ ] Step 0: category_{CAT_SLUG}.yaml 존재 확인 (없으면 생성)
[ ] A0: a0_selected_{CAT}.json 생성, 3개 제품 선정됨, selected_tier 확인
[ ] A2: a2_resale_{CAT}.json 생성, collected_prices 실제 매물만 포함 (추정값 금지)
[ ]     — 제품당 resale_price + confidence 확인, purchase_price_source = "a0"
[ ]     — 못 찾으면 resale_price: 0, confidence: "none" 처리 확인
[ ] A3: a3_repair_{CAT}.json 생성, expected_repair_cost = 1회 기대값 (3년 아님)
[ ]     — 제품당 기대수리비 + AS 일수 + 유지관리 자동화율 확인
[ ] A5: a5_reviews_{CAT}.json 생성, 제품당 리뷰 30건+, category_insights 포함
[ ] A4: tco_{CAT}.json 생성, selected_tier/tier_scores/tier_product_counts 포함
[ ]     — **TCO 수식 검증:** real_cost_3yr == purchase_price + (expected_repair_cost × 3) - resale_price
[ ]     — 계산 검증: expected_repair_cost_3yr == expected_repair_cost × 3
[ ] B:  블로그 포스트 생성, 7개 Section 구조 확인
```

---

## 트러블슈팅

### A2 중고 매물을 찾지 못할 때

1. 모델명을 짧게 줄여서 재검색 (예: "필립스 S5466/17" → "필립스 5000시리즈 중고")
2. 브랜드 + 카테고리로 일반화 (예: "필립스 전기면도기 중고")
3. 그래도 0건이면 `resale_price: 0`, `confidence: "none"` 으로 설정하고 진행
4. TCO에서 중고 환급은 0으로 처리됨 (보수적 계산)

### A3/A5 WebSearch에서 결과가 부족할 때

1. 검색어를 더 일반적으로 변경 (모델명 → 브랜드명 + 카테고리)
2. 보충 검색어로 추가 검색 실행
3. 그래도 부족하면 `notes` 필드에 "데이터 부족" 명시하고 진행

### A4 TCO 수식이 안 맞을 때

```
real_cost_3yr = purchase_price + expected_repair_cost - resale_price
```
- 중고가가 없으면(매물 없음) resale_price = 0으로 처리
- 수리비가 없으면(고장 사례 없음) expected_repair_cost = 0으로 처리

### A5 리뷰가 30건 미만일 때

1. 보충 검색어 실행: "장점 단점 정리", "1년 사용기", "후회 추천"
2. 그래도 부족하면 최소 15건으로 하향하고 `notes`에 "리뷰 부족 — 신뢰도 제한" 명시
3. category_insights는 수집 가능한 범위 내에서 도출

---

## v2 → v3 변경 이력

| 항목 | v2 | v3 | 사유 |
|------|----|----|------|
| A2 중고가 수집 | 1yr/2yr/3yr+ 연도별 개별 수집 | 전체 중고가 수집 → median ±10% 필터링 | 연도별 검색 시 데이터 확보 실패. 중고 플랫폼에서 사용기간 필터 불가. |
| A2 JSON 스키마 | `resale_prices.1yr/2yr/3yr_plus`, `retention_curve` | `resale.resale_price`, `median_raw`, `confidence` | 단일 중고 환급 예상액으로 단순화 |
| A4 TCO 수식 | `purchase + repair - resale_2yr` | `purchase + repair - resale_price` | 연도별 잔존율 제거, 단일 중고 환급액 사용 |
| A4 Export 스키마 | `resale_value_1yr`, `resale_value_2yr`, `purchase_price_avg`, `purchase_price_min` | `resale_price`, `resale_confidence`, `purchase_price` | 불필요 필드 제거, 단일 소스 반영 |
| 블로그 표현 | "3년 뒤 중고가" | "중고 매각 시 예상 회수액" | 예측이 아닌 현재 시세 기반 표현 |

---

*Runbook version: 3.0*
*Last updated: 2026-02-08*
*Depends on: TCO Blog Structure RAG v1.0*