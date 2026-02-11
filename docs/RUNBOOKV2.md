# TCO Pipeline Runbook v2

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
| A2 | Claude WebSearch | 제품명 3개 | `a2_resale_{CAT}.json` | Section 4-4 (중고가) |
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

### 사전 입력 — A0 가격 읽기 (필수)

A0 출력 파일을 읽는다: `data/processed/a0_selected_{CATEGORY}.json`

각 제품의 `price`를 기록한다:
  - PRODUCT_1_PRICE = a0_output.selected_products[0].price
  - PRODUCT_2_PRICE = a0_output.selected_products[1].price
  - PRODUCT_3_PRICE = a0_output.selected_products[2].price

이 가격이 A2 전체에서 잔존율 계산의 기준(base price)이 된다.

### 실행 절차

1. **검색 수행** — 제품별로 아래 검색어로 WebSearch 실행:
   - `"{PRODUCT_N} 중고 시세 당근마켓 번개장터"`
   - `"{PRODUCT_N} 중고 가격 중고나라"`
   - `"{PRODUCT_N} 중고 매매 만원"`

2. **가격 추출** — 검색 결과와 WebFetch로 아래 정보 수집:
   - 1년 미만 사용 중고가 (복수 매물의 중앙값)
   - 2년 사용 중고가 (복수 매물의 중앙값)
   - 3년 이상 사용 중고가 (복수 매물의 중앙값)
   - 가격 출처 (URL 또는 플랫폼명)

3. **신품가 대비 잔존율 계산** — A0 가격을 기준으로 계산:
   - `retention_1yr = resale_1yr / PRODUCT_N_PRICE`    ← A0 가격 사용
   - `retention_2yr = resale_2yr / PRODUCT_N_PRICE`    ← A0 가격 사용
   - `retention_3yr = resale_3yr / PRODUCT_N_PRICE`    ← A0 가격 사용

### 교차 검증 (Cross-Check)

A0 가격과 A2에서 검색 중 발견한 신품 시세를 비교한다:
  - 차이 20% 이내 → `status: "ok"`, A0 가격 사용
  - 차이 20~50% → `status: "warning"`, notes에 "A0 가격과 시세 차이 존재" 기록, A0 가격 사용
  - 차이 50% 초과 → `status: "alert"`, notes에 경고 기록, A0 가격 사용하되 A4에서 재검증 필요 플래그

4. **결과를 JSON으로 저장**:

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
      "purchase_price_avg": 0,
      "purchase_price_source": "a0",
      "purchase_price_cross_check": {
        "a0_price": 0,
        "market_price_observed": 0,
        "deviation_pct": 0.0,
        "status": "ok | warning | alert"
      },
      "resale_prices": {
        "1yr": {"price": 0, "sample_count": 0, "sources": ["당근마켓", "번개장터"]},
        "2yr": {"price": 0, "sample_count": 0, "sources": []},
        "3yr_plus": {"price": 0, "sample_count": 0, "sources": []}
      },
      "retention_curve": {
        "1yr": 0.0,
        "2yr": 0.0,
        "3yr_plus": 0.0
      },
      "notes": "검색 중 특이사항 메모"
    }
  ]
}
```

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

4. **결과를 JSON으로 저장**:

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

### purchase_price_avg 결정

A0의 Naver Shopping `lprice`가 구매가의 단일 소스이다:

```
purchase_price = A0 selected_products[].price
```

A0는 항상 Naver Shopping API에서 가격을 가져오므로 fallback이 필요 없다.
`price == 0`인 경우는 A4가 warning을 로깅하고 해당 제품을 TCO 계산에서 제외한다.

### 확인사항
- `data/exports/tco_{CATEGORY}.json` 생성 확인
- 각 제품의 TCO 수식 검증: `real_cost_3yr = purchase_avg + repair_cost - resale_2yr`
- **`purchase_price_source`가 모든 제품에 대해 `"a0"`인지 확인**
- A5 리뷰 인사이트가 export JSON에 포함되었는지 확인
- api-contract.json 스키마와 일치하는지 확인

### TCO Export JSON 최종 스키마

```json
{
  "category": "{CATEGORY}",
  "generated_at": "ISO 8601",
  "products": [
    {
      "product_id": "product_slug",
      "product_name": "제품 전체명",
      "brand": "브랜드명",
      "tco": {
        "purchase_price_avg": 0,
        "purchase_price_min": 0,
        "resale_value_1yr": 0,
        "resale_value_2yr": 0,
        "expected_repair_cost": 0,
        "real_cost_3yr": 0
      },
      "qualitative": {
        "as_turnaround_days": 0,
        "warranty_months": 0,
        "maintenance_tasks": [
          {"task": "유지관리 항목", "automated": true}
        ],
        "automation_rate": 0
      },
      "review_insights": {
        "reviews_collected": 0,
        "purchase_motivations": [
          {
            "spec_or_criteria": "",
            "mention_count": 0,
            "appears_in_satisfaction": true,
            "appears_in_complaints": false,
            "verdict": "overrated | justified | underrated"
          }
        ],
        "sentiment_keywords": {
          "positive": [{"keyword": "", "count": 0}],
          "negative": [{"keyword": "", "count": 0}]
        },
        "hidden_differentiator": "",
        "environment_splits": [
          {
            "environment": "",
            "key_issue": "",
            "sentiment": "positive | negative",
            "typical_comment": ""
          }
        ]
      }
    }
  ],
  "category_insights": {
    "most_overrated_spec": "",
    "real_differentiator": "",
    "decision_forks": [
      {
        "user_type": "",
        "priority": "",
        "recommended_product": "해당 유형에 맞는 제품명"
      }
    ]
  },
  "credibility": {
    "total_review_count": 0,
    "resale_sample_count": 0,
    "repair_report_count": 0,
    "collection_period": "",
    "review_sources": ["쿠팡", "네이버쇼핑"]
  }
}
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
    ├─ 4-4: 정량 비교표 (구매가, 중고가, 수리비, 3년 실비용)
    └─ 4-5: 정성 비교표 (AS 대기일수, 유지관리 자동화율)

Section 5: 행동 유도 (가격 변동성 + CTA)

Section 6: FAQ (본문 미포함 질문만, repair_context + review_insights 기반)
```

---

## 파이프라인 체크리스트

실행 완료 후 아래 항목을 모두 확인한다.

```
[ ] Step 0: category_{CAT_SLUG}.yaml 존재 확인 (없으면 생성)
[ ] A0: a0_selected_{CAT}.json 생성, 3개 제품 선정됨
[ ] A2: a2_resale_{CAT}.json 생성, 제품당 중고가 3개 구간(1yr/2yr/3yr+), purchase_price_source = "a0"
[ ] A3: a3_repair_{CAT}.json 생성, 제품당 기대수리비 + AS 일수 + 유지관리 자동화율
[ ] A5: a5_reviews_{CAT}.json 생성, 제품당 리뷰 30건+, category_insights 포함
[ ] A4: tco_{CAT}.json 생성, TCO 수식 검증, purchase_price_source 확인
[ ] B:  블로그 포스트 생성, 7개 Section 구조 확인
```

---

## 트러블슈팅

### A2/A3/A5 WebSearch에서 결과가 부족할 때

1. 검색어를 더 일반적으로 변경 (모델명 → 브랜드명 + 카테고리)
2. 보충 검색어로 추가 검색 실행
3. 그래도 부족하면 `notes` 필드에 "데이터 부족" 명시하고 진행

### A4 TCO 수식이 안 맞을 때

```
real_cost_3yr = purchase_price_avg + expected_repair_cost - resale_value_2yr
```
- 중고가가 없으면(매물 없음) resale_value_2yr = 0으로 처리
- 수리비가 없으면(고장 사례 없음) expected_repair_cost = 0으로 처리

### A5 리뷰가 30건 미만일 때

1. 보충 검색어 실행: "장점 단점 정리", "1년 사용기", "후회 추천"
2. 그래도 부족하면 최소 15건으로 하향하고 `notes`에 "리뷰 부족 — 신뢰도 제한" 명시
3. category_insights는 수집 가능한 범위 내에서 도출

---

*Runbook version: 2.0*
*Last updated: 2026-02-08*
*Depends on: TCO Blog Structure RAG v1.0*