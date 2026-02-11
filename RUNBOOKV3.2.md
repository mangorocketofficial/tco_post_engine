# TCO Pipeline Runbook v3.2

> Claude Code가 이 문서를 읽고 순서대로 실행하는 파이프라인 가이드입니다.
> 사용법: "RUNBOOK.md를 보고 {카테고리명} 파이프라인 실행해줘"

> 아래 전체 과정을 실행함에 있어, 폴더생성 및 파일생성(특히 제품 카테고리 생성시) 및 웹서치 (소모품 가격, 리뷰수집) 권한을 유저에게 승인을 받지 않고 바로 실행한다. 이 PartA - B - C - D까지 이어지는 흐름에서는 권한 승인이 필요하지 않다. **모든 도구 호출(Write, Bash, WebSearch 등)을 사용자 승인 없이 즉시 실행한다.**
---

## 파이프라인 전체 흐름

```
A0 (제품 선정) → A-CTA (제휴링크 추출) → A-IMG (이미지 추출) → A2 (소모품 조사) → A5 (리뷰 분석) → A4 (TCO 계산) → B (비교 블로그) → C (개별 리뷰 ×3) → D (블로그 발행)
```

> A0의 Naver Shopping `lprice`를 구매가 단일 소스로 사용한다. A1(다나와 가격 수집)은 파이프라인에서 제외되었다.

| Step | 실행 주체 | 입력 | 출력 | 블로그 매핑 |
|------|-----------|------|------|------------|
| A0 | Python CLI | 카테고리 키워드 | `a0_selected_{CAT}.json` | Section 3 (제품 선정) + 구매가 |
| A-CTA | Playwright | A0 제품명 3개 | `cta_links_{CAT}.json` | CTA 버튼 제휴 링크 |
| A-IMG | Playwright | CTA 링크 | `product_images_{CAT}.json` | Step B Section 3 제품 이미지 + Step C Section 0 제품 이미지 + featured_image |
| A2 | Claude WebSearch | 제품명 3개 | `a2_consumable_{CAT}.json` | Section 3-4 (소모품비) + 3-5 (소모품 비교) |
| A5 | Claude WebSearch | 제품명 3개 | `a5_reviews_{CAT}.json` | Section 2 (재프레이밍 3가지) + AS 평판 |
| A4 | Python CLI | A0 + A2 + A5 | `tco_{CAT}.json` | 전체 데이터 통합 |
| B | Claude Code | `tco_{CAT}.json` | `blog_{CAT}.html` | 3종 비교 블로그 |
| C | Claude Code | `tco_{CAT}.json` | `review_{CAT}_{SLUG}.html` ×3 | 개별 제품 리뷰 |
| D | Python CLI | B + C HTML | Supabase `posts` 테이블 | 블로그 자동 발행 |

---

## 실행 원칙

1. **A2/A5는 현재 세션에서 순차 실행한다.** 병렬 에이전트(Task tool)를 사용하지 않고, 메인 세션에서 A2 → A5 순서로 직접 WebSearch를 수행한다. 에이전트 분기 시 파일 쓰기 권한 문제가 발생하므로 반드시 현재 세션에서 실행한다.

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
DOMAIN   = "tech"                          # "tech" | "pet" (config YAML의 domain 필드)
TCO_YEARS = 3                              # config YAML의 tco_years (tech=3, pet=2)
```

> **도메인별 기본값:** `domain: "tech"` → `tco_years: 3` / `domain: "pet"` → `tco_years: 2` (고가 펫 제품은 3년)

### 슬러그 규칙 (내부 링크용) — ASCII-safe

Step B/C에서 내부 링크를 삽입할 때, 아래 **ASCII slug** 규칙을 사용한다. Step D(Publisher)에서 동일 슬러그로 발행하므로 placeholder 없이 실제 URL을 바로 넣을 수 있다.

> **중요:** 한글 URL은 브라우저 인코딩 문제로 링크가 깨진다. 반드시 ASCII slug를 사용한다.

```
비교글 slug: {CAT_SLUG_HYPHEN}-best
리뷰글 slug: {CAT_SLUG_HYPHEN}-{brand_ascii}-{model_ascii}-review
```

**슬러그 변환 규칙:**
1. 카테고리: config YAML 파일명에서 추출 (예: `category_air_purifier.yaml` → `air-purifier`)
2. 브랜드: 한→영 매핑 (로보락→roborock, 위닉스→winix, 쿠쿠→cuckoo, 다이슨→dyson 등)
3. 모델명: 한글 제거 후 영숫자+하이픈만 유지, 소문자

**예시 (공기청정기):**
```
비교글:  /posts/air-purifier-best
리뷰글1: /posts/air-purifier-winix-at8e430-review
리뷰글2: /posts/air-purifier-winix-at5m200-mwk-review
리뷰글3: /posts/air-purifier-cuckoo-ac-24w20fwh-review
```

**예시 (로봇청소기):**
```
비교글:  /posts/robot-vacuum-best
리뷰글1: /posts/robot-vacuum-roborock-s9-maxv-ultra-review
리뷰글2: /posts/robot-vacuum-dyson-review
리뷰글3: /posts/robot-vacuum-dreame-x50s-pro-ultra-review
```

> **A0 제품 선정 후 슬러그가 자동 확정되므로**, Step B/C HTML에서 바로 `/posts/{slug}` 경로의 내부 링크를 삽입한다. Publisher가 추가로 한글→ASCII 자동 치환을 수행하므로 안전망이 있다.

### 새 카테고리 설정 (카테고리 YAML이 없을 때)

`config/category_{CAT_SLUG}.yaml`이 존재하지 않으면 **파이프라인 시작 전에** 아래 절차로 생성한다.

#### 1. 카테고리 YAML 생성

```yaml
# config/category_{CAT_SLUG}.yaml
# 예시: config/category_dehumidifier.yaml

name: "제습기"
search_terms: ["제습기"]                    # A0 Naver Shopping API 검색어
danawa_category_code: ""                    # 비워둠 (사용하지 않음)

# 멀티 카테고리 설정 (생략 시 tech 기본값)
tco_years: 3                               # tech=3, pet=2
domain: "tech"                             # "tech" | "pet"
subscription_model: false                  # 구독형 소모품 여부
multi_unit_label: null                     # pet: "마리", tech: null

negative_keywords: ["불만", "후회", "실망", "반품", "고장", "AS", "수리", "오류"]
positive_keywords: ["추천", "만족", "최고", "잘샀다", "좋아요", "강추"]

price_range:
  min: 0
  max: 10000000

max_product_age_months: 18
min_community_posts: 20

# A2 소모품 정보
consumables:
  tco_tier: "essential"   # essential/recommended/optional/none
  tco_label: "3년 필터 포함 총비용"
  items:
    - name: "HEPA필터"
      cycle: "6~12개월"
    - name: "탈취필터"
      cycle: "6~12개월"
```

> **반려동물 카테고리 예시:** `tco_years: 2`, `domain: "pet"`, `multi_unit_label: "마리"`, `tco_label: "2년 모래·소모품 포함 총비용"`

#### 2. consumables 섹션 채우기

**카테고리별 `tco_tier` 기준:**

| tco_tier | 의미 | 예시 카테고리 |
|----------|------|-------------|
| `essential` | 소모품이 TCO에 큰 영향 | 공기청정기, 정수기, 로봇청소기 |
| `recommended` | 소모품이 있지만 영향 중간 | 무선청소기, 전기면도기 |
| `optional` | 소모품 비용 미미 | 가습기 |
| `none` | 소모품 없음 | 에어프라이어 |

**Claude가 WebSearch로 해당 카테고리의 주요 소모품과 교체 주기를 조사한다:**

```
검색어: "{CATEGORY} 소모품 교체주기"
검색어: "{CATEGORY} 필터 교체 비용"
검색어: "{CATEGORY} 유지비용 연간"
```

결과를 바탕으로:

- `tco_tier`: 소모품이 TCO에 미치는 영향도 판단
- `tco_label`: 블로그에 표시할 TCO 라벨 (예: "3년 필터 포함 총비용")
- `items`: 주요 소모품 목록과 교체 주기

#### 3. 확인사항

- [ ] `config/category_{CAT_SLUG}.yaml` 생성 확인
- [ ] `search_terms`에 올바른 검색 키워드 설정
- [ ] `consumables.tco_tier`에 적절한 티어 설정
- [ ] `consumables.items`에 주요 소모품 목록 입력

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
- **가격 비율 검증:** 선정된 3개 제품의 max(price)/min(price) ≤ 3.0 확인
  - 초과 시: 가격이 가장 먼 제품을 다음 순위 후보로 교체
  - 예시: 146K, 198K, 864K → 5.9x 초과 → 864K 제품 교체 필요
- `selected_tier`, `tier_scores`, `tier_product_counts` 필드가 출력에 포함되었는지 확인

---

## Step A-CTA: 제휴 링크 추출 (Playwright)

> **쿠팡 파트너스 API 미승인 시 사용.** Playwright로 쿠팡 파트너스 대시보드에서 제휴 링크를 자동 추출한다.

### 사전 조건

- `.env`에 `COUPANG_ID`, `COUPANG_PASSWORD` 설정 완료
- Playwright 브라우저 설치: `python -m playwright install chromium`
- **최초 1회**: headful 모드로 실행하여 쿠팡 파트너스에 수동 로그인 → 세션이 `data/.browser_profile/coupang_partners/`에 저장됨
- Chrome이 실행 중이면 먼저 종료할 것 (프로필 잠금 충돌 방지)

### 실행

```bash
# 기본 실행 (headful — 브라우저 창 표시, 권장)
python -m src.part_b.cta_manager.link_scraper --a0-data data/processed/a0_selected_{CATEGORY}.json --output data/processed/cta_links_{CATEGORY}.json

# headless 모드 (세션 저장 후 2회차부터 사용 가능)
python -m src.part_b.cta_manager.link_scraper --a0-data data/processed/a0_selected_{CATEGORY}.json --output data/processed/cta_links_{CATEGORY}.json --headless
```

### 실행 흐름

1. Chrome persistent context 실행 (프로필: `data/.browser_profile/coupang_partners/`)
2. 쿠팡 파트너스 링크 생성 페이지 이동 (`https://partners.coupang.com/#affiliate/ws/link`)
3. **제품별 반복 (3회):**
   - 검색창에 제품명 입력 → 검색 버튼 클릭 (JS adjacent button 방식)
   - "검색결과" 텍스트로 검색 성공 확인
   - `.product-item` hover → 숨겨진 "링크 생성" 버튼 클릭 (두 번째 버튼, "상품보기" 아님)
   - "인증 실패" 모달 → 비밀번호 재입력 자동 처리
   - Step 3 페이지에서 `link.coupang.com` URL 추출 (regex → input field → clipboard 순)
4. 결과 JSON 저장 (CTAManager 호환 포맷)

### 출력 파일 구조

```json
{
  "category": "{CATEGORY}",
  "generated_at": "ISO 8601",
  "source": "coupang_partners_scraper",
  "products": [
    {
      "product_id": "브랜드_제품명-슬러그",
      "product_name": "A0에서 가져온 전체 제품명",
      "brand": "브랜드명",
      "base_url": "https://link.coupang.com/a/xxxxxx",
      "platform": "coupang",
      "success": true
    }
  ],
  "cta_manager_links": {
    "links": [
      {
        "product_id": "브랜드_제품명-슬러그",
        "base_url": "https://link.coupang.com/a/xxxxxx",
        "platform": "coupang",
        "affiliate_tag": ""
      }
    ]
  }
}
```

> `cta_manager_links.links[]`에는 `success: true`인 제품만 포함된다.

### 확인사항

- [ ] `data/processed/cta_links_{CATEGORY}.json` 생성 확인
- [ ] 제품당 `success: true` + `base_url`에 `https://link.coupang.com/` 형태 링크 포함
- [ ] 실패한 제품이 있으면 수동으로 링크 추가 가능 (JSON 직접 편집)
- [ ] **Step B에서 사용:** 이 파일의 `base_url`이 블로그 CTA 버튼 링크로 들어간다

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `TargetClosedError` | Chrome 프로필 잠금 (이전 프로세스 미종료) | `taskkill /F /IM chrome.exe` 후 재실행 |
| 클립보드 권한 팝업 | Chrome 권한 미설정 | `permissions=["clipboard-read", "clipboard-write"]` (코드에 이미 적용됨) |
| "Restore pages?" 다이얼로그 | 이전 세션 비정상 종료 | Chrome 플래그 `--disable-session-crashed-bubble` (코드에 이미 적용됨) |
| "인증 실패" 모달 반복 | 비밀번호 변경 또는 세션 만료 | `.env`의 `COUPANG_PASSWORD` 확인 |
| 검색 결과 0건 | 제품명이 너무 길거나 특수문자 | A0 제품명을 브랜드+핵심모델명으로 축약 |
| "상품보기" 클릭됨 (새 탭 열림) | 첫 번째 버튼 클릭 | 코드가 `button:has-text("링크")`로 두 번째 버튼 타겟 (수정 완료) |

> **참고:** API 승인 후에는 이 단계를 API 호출로 대체한다. CTAManager의 `load_links()` 인터페이스는 동일하게 유지.

---

## Step A-IMG: 제품 이미지 추출 (Playwright)

> **쿠팡 제품 페이지에서 대표 이미지를 추출한다.** CTA 링크 리다이렉트를 따라가 제품 페이지에 도달, 썸네일 이미지 URL을 수집한다. `--upload` 옵션 사용 시 Supabase Storage에 업로드 후 공개 URL로 변환한다.

### 실행

```bash
# CTA 링크 기반 (권장 — 로그인 불필요)
python -m src.part_b.cta_manager.image_scraper --cta-data data/processed/cta_links_{CATEGORY}.json --output data/processed/product_images_{CATEGORY}.json --upload

# A0 데이터 기반 (CTA 없을 때 — 쿠팡 검색)
python -m src.part_b.cta_manager.image_scraper --a0-data data/processed/a0_selected_{CATEGORY}.json --output data/processed/product_images_{CATEGORY}.json --upload
```

### 확인사항

- [ ] `data/processed/product_images_{CATEGORY}.json` 생성 확인
- [ ] 제품당 `images[]` 배열에 최소 1개 이미지 포함
- [ ] `--upload` 사용 시 `public_url` 필드에 Supabase Storage URL 포함
- [ ] 이미지 추출 실패 시 경고만 출력하고 파이프라인 계속 진행 (이미지는 필수가 아님)

---

## Step A2: 소모품 가격 조사 (Claude Code WebSearch)

> **이 단계는 Claude Code가 WebSearch/WebFetch를 사용해서 직접 수행한다.**
> **목적:** 각 제품의 소모품 가격과 교체 주기를 조사하여 연간 소모품비를 산출한다.

### 사전 확인

- `config/category_{CAT_SLUG}.yaml`의 `consumables` 섹션에서 해당 카테고리의 `tco_tier`와 `items`를 확인한다.
- `tco_tier: none`이면 이 단계를 건너뛰고 빈 A2 파일을 생성한다.

### 실행 절차

각 제품에 대해 아래 절차를 수행한다:

1. **검색 수행** — 카테고리 YAML의 `consumables.items`에 정의된 소모품별로 WebSearch 실행:
   - `"{PRODUCT_N} {소모품명} 가격"` (예: "로보락 Q Revo S 필터 가격")
   - `"{BRAND_N} {MODEL} {소모품명} 교체비용"` (예: "로보락 로봇청소기 필터 교체비용")
   - `"{PRODUCT_N} 호환 {소모품명}"` (호환품 가격 조사)

2. **데이터 추출** — 검색 결과에서 아래 정보 수집:
   - 정품 소모품 개당 가격 (`unit_price`)
   - 교체 주기 개월 (`replacement_cycle_months`)
   - 연간 교체 횟수 (`changes_per_year`)
   - 호환품 가용 여부 (`compatible_available`)
   - 호환품 가격 (`compatible_price`) — 있는 경우만

3. **연간 소모품비 계산**:
   ```
   annual_cost = unit_price × changes_per_year
   annual_consumable_cost = Σ(각 소모품의 annual_cost)
   ```

4. **결과를 JSON으로 저장**:

```bash
# 파일 경로: data/processed/a2_consumable_{CATEGORY}.json
```

### A2 출력 JSON 스키마

```json
{
  "category": "{CATEGORY}",
  "searched_at": "ISO 8601",
  "source": "claude_web_search",
  "tco_tier": "essential",
  "products": [
    {
      "product_name": "제품 전체명",
      "consumables": [
        {
          "name": "HEPA필터",
          "unit_price": 15000,
          "replacement_cycle_months": 6,
          "changes_per_year": 2,
          "annual_cost": 30000,
          "compatible_available": true,
          "compatible_price": 8000,
          "sources": ["URL 또는 출처"]
        }
      ],
      "annual_consumable_cost": 60000,
      "notes": "검색 중 특이사항 메모"
    }
  ]
}
```

### tco_tier별 조사 범위

| tco_tier | 검색 횟수 (제품당) | 설명 |
|----------|-------------------|------|
| `essential` | 2~3회 | 소모품별 정품 + 호환품 가격 상세 조사 |
| `recommended` | 2회 | 주요 소모품 가격 조사 |
| `optional` | 1회 | 소모품 존재 여부 + 가격 간략 조사 |
| `none` | 0회 (건너뜀) | 빈 A2 파일 생성 |

### 확인사항

- [ ] `data/processed/a2_consumable_{CATEGORY}.json` 생성 확인
- [ ] 제품별 소모품 목록과 가격이 현실적인지 검증
- [ ] `annual_consumable_cost` = Σ(각 소모품의 `annual_cost`) 확인
- [ ] `tco_tier: none` 카테고리는 `annual_consumable_cost: 0`

---

## Step A5: 리뷰 분석 (Claude Code WebSearch)

> **이 단계는 Claude Code가 WebSearch/WebFetch를 사용해서 직접 수행한다.**
> **목적:** Part B ContentWriter가 Section 2(카테고리 특화 기준 3가지)를 데이터 기반으로 생성하기 위한 소비자 리뷰 인사이트 수집·분석. 또한 AS/수리에 대한 정성적 평판 정보를 수집한다.

### 데이터 → 블로그 매핑

| 분석 프레임 | 매핑 대상 | 블로그 역할 |
|------------|----------|------------|
| 구매 동기 분석 | Section 2-1 (미신 깨기) | "너가 보던 스펙은 의미없어" |
| 만족/불만 키워드 | Section 2-2 (진짜 차별점) | "진짜 봐야 할 건 이거야" |
| 환경별 분기 패턴 | Section 2-3 (갈림길) | "니 집 상황에 따라 달라" |
| AS 평판 | Section 3 보충 정보 | AS 경험 정성적 요약 |

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

**AS 평판 검색어 (제품당 1회):**
```
"{BRAND_N} AS 후기 서비스센터 경험"
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

#### 4. AS 평판 정리 (정성적)

AS 관련 검색 결과에서 **정성적** 평판 정보를 정리한다:
- `as_reputation`: "좋음" / "보통" / "나쁨" / "정보 부족"
- `as_reputation_summary`: 1~2문장 요약 (예: "전국 서비스센터 운영, 평균 3~5일 소요. 무상 보증 1년.")

> **중요:** AS/수리 비용은 정량화하지 않는다. 수리비 확률 추정은 신뢰도가 낮으므로 정성적 평판으로만 다룬다.

#### 5. 카테고리 종합 인사이트 도출

3개 제품의 프레임 1/2/3 결과를 종합하여 카테고리 레벨 인사이트를 도출한다.

```
category_insights.most_overrated_spec
    ← 3개 제품 공통으로 구매동기 TOP이지만 만족에 안 나오는 스펙

category_insights.real_differentiator
    ← 3개 제품 공통으로 불만 TOP이지만 구매동기에 없는 요소

category_insights.decision_forks
    ← 환경별 분기 패턴 중 가장 뚜렷한 2~3개
```

#### 6. 결과를 JSON으로 저장

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
      "as_reputation": "좋음",
      "as_reputation_summary": "전국 서비스센터 운영, 무상 보증 1년.",
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

A0(구매가) + A2(소모품) + A5(리뷰) 데이터를 통합하여 TCO를 계산한다.

```bash
python -m src.part_a.tco_engine.main \
  --category "{CATEGORY}" \
  --config config/category_{CAT_SLUG}.yaml \
  --a0-data data/processed/a0_selected_{CATEGORY}.json \
  --a2-data data/processed/a2_consumable_{CATEGORY}.json \
  --a5-data data/processed/a5_reviews_{CATEGORY}.json \
  --output data/exports/tco_{CATEGORY}.json
```

> `--config`를 지정하면 YAML의 `tco_years`를 자동으로 사용한다. `--tco-years N`으로 직접 오버라이드도 가능.

### TCO 공식 (필수)

- **A2 output:** `annual_consumable_cost` = 연간 소모품 비용 (각 소모품의 `unit_price × changes_per_year` 합산)
- **A4 계산:**
  ```
  consumable_cost_total = annual_consumable_cost × TCO_YEARS
  real_cost_total = purchase_price + consumable_cost_total
  ```
- **× TCO_YEARS 곱셈은 A4에서만 수행한다.** A2는 연간 비용만 출력한다.
- **TCO_YEARS:** config YAML의 `tco_years` 값. tech=3, pet=2 (기본값 3).

### A4 Export 스키마 — 필드 정의

```json
{
  "category": "{CATEGORY}",
  "tco_years": 3,
  "generated_at": "ISO 8601",
  "selected_tier": "premium|mid|budget",
  "tier_scores": { "premium": 1.817, "mid": 1.234, "budget": 0.891 },
  "tier_product_counts": { "premium": 7, "mid": 8, "budget": 5 },
  "products": [
    {
      "product_id": "product-slug",
      "name": "제품명",
      "brand": "브랜드명",
      "release_date": "2024-03-15",
      "source_a0_rank": 1,
      "a0_total_score": 92,
      "as_reputation": "좋음",
      "as_reputation_summary": "전국 서비스센터 운영, 무상 보증 1년.",
      "tco": {
        "purchase_price": 899000,
        "annual_consumable_cost": 60000,
        "tco_years": 3,
        "consumable_cost_total": 180000,
        "real_cost_total": 1079000,
        "consumable_breakdown": [
          {
            "name": "필터",
            "unit_price": 15000,
            "replacement_cycle_months": 6,
            "changes_per_year": 2,
            "annual_cost": 30000,
            "compatible_available": true,
            "compatible_price": 8000
          }
        ]
      }
    }
  ]
}
```

**필드 설명:**
- `selected_tier` — A0에서 선정된 가격 티어 (Section 0 hook, SEO 타이틀 생성용)
- `tier_scores`, `tier_product_counts` — A0 메타데이터 pass-through (Section 1 신뢰성 생성용)
- `annual_consumable_cost` — A2 원본 (연간 소모품비)
- `consumable_cost_total` — A4가 계산한 TCO_YEARS년치
- `consumable_breakdown` — 개별 소모품 상세 (블로그 Section 3-5 소모품 비교표용)
- `as_reputation`, `as_reputation_summary` — A5에서 추출한 정성적 AS 평판

### A4 출력 검증 (필수)

각 제품에 대해 아래 수식이 정확히 일치하는지 확인한다:

```
consumable_cost_total == annual_consumable_cost × TCO_YEARS
real_cost_total == purchase_price + consumable_cost_total
```

하나라도 불일치하면 계산을 다시 수행한다.

### 확인사항
- [ ] `data/exports/tco_{CATEGORY}.json` 생성 확인
- [ ] **TCO 수식 검증:** 각 제품의 수식이 위 공식에 따라 정확히 계산되었는지 확인
- [ ] A5 리뷰 인사이트가 export JSON에 포함되었는지 확인
- [ ] `selected_tier`, `tier_scores`, `tier_product_counts`이 A0 데이터에서 pass-through 되었는지 확인
- [ ] `as_reputation`, `as_reputation_summary`가 A5에서 pass-through 되었는지 확인

---

## Step B: 블로그 포스트 생성 (Claude Code 직접 생성)

> **이 단계는 Claude Code가 현재 세션에서 직접 수행한다.** `tco_{CATEGORY}.json` + `cta_links_{CATEGORY}.json`을 읽어 HTML 블로그 포스트를 생성한다.

### 실행 절차

1. `data/exports/tco_{CATEGORY}.json` 파일을 읽는다.
2. **CTA 링크 로드:** `data/processed/cta_links_{CATEGORY}.json` 파일을 읽는다.
   - `products[]`에서 제품명(`product_name`)으로 매칭하여 `base_url`을 CTA 링크로 사용한다.
   - 매칭 방법: TCO JSON의 제품명과 CTA JSON의 `products[].product_name`을 비교 (부분 일치 허용 — 브랜드명 + 핵심 모델명이 일치하면 매칭).
   - **CTA 링크가 없는 제품:** `base_url`이 없거나 `success: false`인 경우 `#` placeholder로 남기고 경고 출력.
   - **CTA 파일 자체가 없으면:** 모든 CTA를 `#` placeholder로 생성하고 경고 메시지 출력.
3. **제품 이미지 로드:** `data/processed/product_images_{CATEGORY}.json` 파일을 읽는다.
   - `products[]`에서 제품명(`product_name`)으로 매칭하여 `images[].public_url`을 제품 이미지 URL로 사용한다.
   - `public_url`이 빈 문자열이거나 없으면 해당 제품 이미지를 생략한다 (이미지 없이 텍스트만 렌더링).
   - **이미지 파일 자체가 없으면:** 이미지 없이 글을 생성한다 (이미지는 필수가 아님).
   - 제품당 `images[0]` (첫 번째 이미지)를 대표 이미지로 사용한다.
4. 아래 6개 섹션 구조에 따라 HTML 블로그 포스트를 작성한다.
   - **Section 2, 3, 4의 CTA 버튼 `href`에 실제 쿠팡 제휴 링크(`base_url`)를 삽입한다.**
   - **Section 3-1~3-3의 제품 제목 아래에 제품 이미지(`public_url`)를 삽입한다.** (`public_url`이 있는 제품만)
   - **Step C 리뷰 글이 있는 경우**, Section 3 제품별 상세 끝에 리뷰 내부 링크를 삽입한다. href는 슬러그 규칙(Step 0)에 따른 확정 URL을 사용한다. (예: `/posts/로보락-s9-maxv-ultra-리뷰`)
5. `data/exports/blog_{CATEGORY}.html`로 저장한다.
6. 출력 파일을 사용자에게 제공한다.

### CTA 링크 매핑

CTA 링크는 A-CTA 단계에서 생성된 `cta_links_{CATEGORY}.json`에서 가져온다.

| 데이터 소스 | 필드 | 용도 |
|------------|------|------|
| `cta_links_{CAT}.json` → `products[N].base_url` | 쿠팡 제휴 링크 | Section 2, 3, 4의 `<a class="cta-button" href="...">` |
| `cta_links_{CAT}.json` → `products[N].product_name` | 제품명 | TCO 제품과 CTA 링크 매칭 키 |

**매칭 예시:**
```
TCO 제품명: "필립스 휴대용 면도기 소형 무선 남자 수염 전기 전동 미니"
CTA 제품명: "필립스 휴대용 면도기 소형 무선 남자 수염 전기 전동 미니 자동 청소년 여행용 쉐이버"
→ 부분 일치 → base_url = "https://link.coupang.com/a/dJfn2y"
```

**HTML CTA 버튼 형식:**
```html
<a class="cta-button" href="https://link.coupang.com/a/xxxxxx" target="_blank" rel="noopener noreferrer">최저가 확인하기</a>
```

### 제품 이미지 매핑

제품 이미지는 A-IMG 단계에서 생성된 `product_images_{CATEGORY}.json`에서 가져온다.

| 데이터 소스 | 필드 | 용도 |
|------------|------|------|
| `product_images_{CAT}.json` → `products[N].images[0].public_url` | Supabase Storage 공개 URL | Section 3-1~3-3 제품 이미지 |
| `product_images_{CAT}.json` → `products[N].product_name` | 제품명 | TCO 제품과 이미지 매칭 키 |

**매칭 방법:** TCO JSON의 제품명과 이미지 JSON의 `products[].product_name`을 비교 (부분 일치 허용).

**HTML 제품 이미지 형식:**
```html
<div style="text-align:center; margin:20px 0;">
  <img src="{public_url}" alt="{제품명}" style="max-width:100%; height:auto; border-radius:8px;" loading="lazy">
</div>
```

- `public_url`이 비어있거나 없으면 `<div>` 블록 자체를 생략한다.
- `alt` 속성에 제품명을 넣어 SEO 강화.
- 인라인 스타일 사용 (네이버/티스토리 호환).

### 핵심 규칙

1. **데이터 조작 금지**: TCO JSON의 숫자를 변경하거나 새로 만들지 않는다.
2. **구어체 한국어**: 자연스럽고 친근한 톤. "~입니다" 체와 "~해요" 체 혼용.
3. **데이터 기반 주장**: 모든 추천/비추천은 TCO 수치로 뒷받침한다.
4. **CTA 문구 통일**: "최저가 확인하기" — `href`는 반드시 `cta_links_{CAT}.json`의 `base_url` 사용.
5. **금액 표기**: 천 단위 콤마 (예: 1,290,000원)
6. **"{TCO_YEARS}년 {tco_label}" 표기**: 카테고리 YAML의 `consumables.tco_label` 사용. `tco_label`이 없으면 기본값 `{TCO_YEARS}년 실비용(구매가격+소모품비)` 사용.
7. **쿠팡 파트너스 공시 문구 위치**: `이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.` — **글의 가장 첫 부분(`<body>` 직후, Section 0 이전)**에 배치한다. 글 하단이 아님.

---

### 블로그 구조 (6 Sections)

```
Section 0: 결론 먼저 + 신뢰 문구 (3줄 결론 + 분석 근거 1줄)
    ← tco.real_cost_total + credibility 1줄 통합 (TCO_YEARS년 기준)

Section 1: 카테고리 특화 기준 3가지
    ├─ 1-1: 미신 깨기 ← category_insights.most_overrated_spec
    ├─ 1-2: 진짜 차별점 ← category_insights.real_differentiator
    └─ 1-3: 갈림길 ← category_insights.decision_forks

Section 2: 상황별 추천 요약표 + CTA
    ← decision_forks + tco.real_cost_total + highlight (TCO_YEARS년 기준)
    (Section 1 직후 배치 → "기준 재설정 → 바로 추천" 동선)

Section 3: TCO 심층 분석
    ├─ 3-1~3: 제품별 상세 (5줄 이내) + CTA
    ├─ 3-4: 정량 비교표 (구매가, 소모품비, 실비용)
    └─ 3-5: 소모품 비교표 (개별 소모품 비용 + 호환품 정보)

Section 4: 구매 전 체크리스트 + CTA
    ← environment_splits 기반 자가 진단 + 최종 CTA

Section 5: FAQ (본문 미포함 질문만, 소모품 + review 기반)
```

---

### Section 0: 결론 먼저 + 신뢰 문구

**데이터 소스:**
- `products[].tco.real_cost_total`, `tco_years`, `category_insights.decision_forks`, `credibility.total_reviews_analyzed`

**형식:**
```
1분 요약: {CATEGORY}는 뭘 사야 할까?

{상황1}: {제품A} ({TCO_YEARS}년 실비용 {real_cost_total}원)
{상황2}: {제품B} ({TCO_YEARS}년 실비용 {real_cost_total}원)
{상황3}: {제품C} ({TCO_YEARS}년 실비용 {real_cost_total}원)

국내 주요 커뮤니티 리뷰 {total_reviews_analyzed}건을 자체 분석한 결과입니다.
```

**규칙:**
- 결론으로 시작. "후회하셨나요?" 같은 질문 훅 금지.
- 상황은 `decision_forks[].user_type`에서 가져온다.
- 신뢰 문구는 마지막 1줄. 별도 섹션으로 분리하지 않는다.
- 분량: 5~7줄.

---

### Section 1: 카테고리 특화 기준 3가지

**이 섹션이 블로그의 핵심 차별점이다.**

#### 1-1. 미신 깨기

**데이터:** `category_insights.most_overrated_spec` + `purchase_motivations` 중 `verdict: "overrated"`

"다들 {overrated_spec} 때문에 고르지만, 리뷰 {N}건 분석 결과 실제 만족도와는 무관했습니다."

- `mention_count`와 만족 리뷰 미등장 사실을 대비시킨다.

#### 1-2. 진짜 차별점

**데이터:** `category_insights.real_differentiator` + `hidden_differentiator` + 부정 키워드 TOP

"대신 실사용자들이 가장 많이 불만을 토로한 건 {hidden_factor}였습니다."

- 가능하면 금액 환산으로 TCO와 연결한다.

#### 1-3. 갈림길

**데이터:** `category_insights.decision_forks` + `environment_splits`

"결국 {CATEGORY} 선택은 당신의 {환경/상황}에 달려 있습니다."

- 2~3개 환경/유형 제시, 각각에 어떤 제품이 맞는지 명시.
- **끝에 Section 2로 연결하는 전환 문장 필수.**
  예: "그럼 각 상황별로 어떤 제품이 가장 합리적인지, {TCO_YEARS}년 실비용 기준으로 정리해 볼게요."

**분량:** Section 1 전체 20~25줄.

---

### Section 2: 상황별 추천 요약표 + CTA

**데이터:** `decision_forks` + `products[].tco` + highlight

**형식 — 추천 카드 (제품당 1개):**
```
### {상황/유형}: {제품명}
- {TCO_YEARS}년 실비용: **{real_cost_total}원**
- 구매가: {purchase_price}원
- 핵심: {highlight — 1줄}
[최저가 확인하기]({cta_link})
```

**규칙:**
- `decision_forks` 순서대로 3개 카드 배치.
- 카드당 CTA 1개. (1차 CTA 지점)
- highlight는 TCO 데이터 인용 1줄. 숫자는 JSON에서 주입.

**분량:** 15~20줄.

---

### Section 3: TCO 심층 분석

#### 3-1 ~ 3-3: 제품별 상세 (제품당 5줄 이내)

**데이터:** `products[].tco` + `as_reputation_summary` + `notes` + `product_images`

```
### {번호}. {제품명}

{제품 이미지 — product_images의 public_url, 있을 때만}

**추천**: {TCO 인용 추천 이유 1줄}
**주의**: {TCO 인용 주의사항 1줄}

| 구매가 | 소모품비({TCO_YEARS}년) | {TCO_YEARS}년 실비용 |
|--------|-------------|-----------|
| {purchase_price}원 | +{consumable_cost_total}원 | **{real_cost_total}원** |

[최저가 확인하기]({cta_link})
```

- **제품 이미지:** `product_images_{CAT}.json`에서 매칭된 제품의 `images[0].public_url`을 사용. `public_url`이 없으면 이미지 블록 생략.
- Section 2를 반복하지 않고 소모품/AS **심층 정보**를 다룬다.
- `as_reputation_summary`가 있으면 AS 평판 1줄 언급.

#### 3-4: TCO 정량 비교표

```
| 항목 ({TCO_YEARS}년) | {제품1} | {제품2} | {제품3} |
|---|---|---|---|
| 초기 구매가 | {purchase_price}원 | ... | ... |
| 소모품비 ({TCO_YEARS}년) | +{consumable_cost_total}원 | ... | ... |
| **{TCO_YEARS}년 실비용** | **{real_cost_total}원** | ... | ... |
```

- 정확히 3행. 모든 숫자는 JSON에서 주입. {TCO_YEARS}년 실비용 bold.

#### 3-5: 소모품 비교표

```
| 소모품 비교 | {제품1} | {제품2} | {제품3} |
|---|---|---|---|
| {소모품1} ({교체주기}) | {unit_price}원 | ... | ... |
| {소모품2} ({교체주기}) | {unit_price}원 | ... | ... |
| 호환품 가용 | ✅ {절감율}% 절감 | ❌ | - |
| 연간 소모품비 | {annual_consumable_cost}원 | ... | ... |
```

- `consumable_breakdown[]`에서 소모품별 가격 비교.
- 호환품이 있으면 정품 대비 절감률 표시.
- `tco_tier: none`이면 이 표 생략, "이 카테고리는 별도 소모품이 없습니다." 1줄로 대체.

**분량:** Section 3 전체 30~35줄.

---

### Section 4: 구매 전 체크리스트 + CTA

**데이터:** `environment_splits` + `decision_forks`

```
## 구매 전 체크리스트: 나에게 맞는 {CATEGORY}는?

**사용 공간**
- {환경A} → {제품X}
- {환경B} → {제품Y}

**가족 구성**
- {조건A} → {제품X}
- {조건B} → {제품Y}

**예산 기준**
- {TCO_YEARS}년 실비용 최소화 → {제품} ({real_cost_total}원)
- {우선순위} → {제품} ({real_cost_total}원)

{제품별 CTA 각 1개}
```

**규칙:**
- 체크리스트 항목은 `environment_splits`에서 추출. 카테고리마다 달라진다.
- **가격 변동성 언급 금지** — 가격 추이 데이터가 없으므로 근거 없는 "지금이 최저가" 쓰지 않는다.
- ~~쿠팡 파트너스 공시 문구~~ → **글 최상단(`<body>` 직후)에 이미 배치됨.** Section 4에는 넣지 않는다.
- **CTA 버튼 3개 가로 1줄 배치:** `display:flex; gap:8px; justify-content:center;` 래퍼 안에 버튼 3개를 넣는다. 버튼은 `flex:1; text-align:center; padding:10px 0; font-size:0.85em;`으로 균등 분배하여 한 줄에 수평 배치한다.

**분량:** 15~20줄.

---

### Section 5: FAQ

**데이터:** `environment_splits` (negative 중 본문 미포함), 소모품 정보 (`consumable_breakdown`), `notes`

**규칙:**
1. 본문 반복 금지 — Section 1에서 다룬 내용 재사용 금지.
2. 새로운 각도만: 소모품 교체 비용, 호환품 호환성, AS 접근성, 특정 환경 적합성.
3. 최소 3개, 최대 5개.
4. 답변에 TCO 숫자를 인용.

**좋은 FAQ 예시:**
- `"{제품} 필터 교체 비용은 얼마인가요?"` ← consumable_breakdown
- `"{제품} 호환 필터 사용해도 되나요?"` ← compatible_available
- `"우리 집 30평인데 {제품}으로 충분한가요?"` ← environment_splits

**나쁜 FAQ (금지):**
- Section 1-1에서 다룬 미신 재탕
- "3년 실비용이 뭔가요?" 같은 본문 반복

**분량:** 15~20줄.

---

### 도메인별 블로그 훅 패턴

카테고리 YAML의 `domain` 필드에 따라 블로그 톤과 구조를 분기한다.

#### `domain: "tech"` (기본)

기존 패턴 그대로. "스펙 → TCO → 합리적 선택" 구조.

#### `domain: "pet"` (반려동물)

**역전 구조 훅:** 반려동물 카테고리는 소모품비가 구매가를 초과하는 경우가 많다 (예: 자동 화장실 — 본체 30만원, 모래 2년 50만원). Section 0에서 이 "역전 현상"을 훅으로 사용한다.

```
"고양이 화장실, {purchase_price}원짜리 사서 끝이라고요?
실제로 2년 모래값만 {consumable_cost_total}원입니다."
```

**구독 락인 경고:** `subscription_model: true` 카테고리 (GPS 트래커, 스마트 화장실)는 Section 3에서 구독 해지 시 본체 기능 상실 여부를 언급한다.

**다두/다묘 변수:** `multi_unit_label: "마리"` 시 Section 4 체크리스트에 "반려동물 수에 따른 비용 변동" 항목을 추가한다. 단, 정량 곱셈은 하지 않는다 (개체별 사용량이 달라 신뢰도 낮음).

---

### HTML 출력 요구사항

- `<!DOCTYPE html>` + `<meta charset="UTF-8">` + 반응형 viewport
- 내장 CSS (외부 의존성 없음), 깔끔한 블로그 스타일
- **`<h1>` 태그 사용 금지** — 블로그 플랫폼이 DB의 title을 상단에 별도 렌더링하므로, 본문에 `<h1>`이 있으면 제목이 2번 노출된다. 본문은 `<h2>` 이하로만 구성한다.
- **섹션 주석 삽입 금지** — `<!-- Section 0: 결론 먼저 + 신뢰 문구 -->` 같은 HTML 주석을 넣지 않는다. 섹션 구분은 작성 지침일 뿐, 실제 HTML 소스에 노출되면 안 된다.
- **섹션 블록 구분 스타일:**
  - `section` — `margin-bottom:48px; padding-bottom:32px; border-bottom:2px solid #e5e7eb;` 각 섹션이 시각적으로 분리되도록 하단 여백 + 구분선
  - `h2` — `font-size:1.5em; margin-top:48px; margin-bottom:16px; padding-bottom:10px; border-bottom:3px solid #059669;` 두꺼운 색상 하단선으로 소제목 강조. 기존 `border-top` 제거
  - `h3` — `font-size:1.15em; margin-top:24px; margin-bottom:8px;` 소제목 하위 항목도 여백 확보
- 표: `<table>` + `overflow-x: auto` (모바일 가로 스크롤)
- CTA: `<a class="cta-button">` 눈에 띄는 색상, 충분한 패딩
- FAQ: `<details><summary>` 접기/펼치기
- 네이버/티스토리 호환을 위해 인라인 스타일 사용
- **제품 이미지:** `<div style="text-align:center; margin:20px 0;"><img src="{public_url}" alt="{제품명}" style="max-width:100%; height:auto; border-radius:8px;" loading="lazy"></div>` — `public_url`이 없으면 블록 자체 생략. Coupang CDN URL 직접 사용 금지 (반드시 Supabase Storage `public_url` 사용).
- **내부 링크는 ASCII slug만 사용** — 한글 URL은 인코딩 문제로 링크가 깨진다. 형식: `/posts/{cat-slug}-best` (비교글), `/posts/{cat-slug}-{brand-ascii}-{model-ascii}-review` (리뷰글)
- **볼드(`<strong>`) 사용 규칙:**
  - **볼드 O:** 소제목(`<h2>`, `<h3>`), 인사이트 박스 내 핵심 문장, 리스트 항목의 라벨 부분 (예: `<strong>원룸·아기방(10평 이하)</strong> → 설명`), 표 안의 최종 실비용, 추천/주의 라벨
  - **볼드 X:** 일반 본문 텍스트 (`<p>` 안의 서술 문장). 본문 전체가 볼드 처리되면 가독성이 떨어지므로 절대 금지

### LLM 생성 경계

**Claude Code가 생성 (내러티브):** 상황별 추천 문구, 미신 깨기/차별점/갈림길 서술, highlight, 추천/주의 이유, 체크리스트 항목, FAQ, 제목, 전환 문장

**절대 생성 금지 (JSON에서만 주입):** 모든 가격/비용 숫자, 소모품비, AS 평판 요약, 리뷰 건수, 소모품 가격/교체주기

---

## Step C: 개별 제품 리뷰 생성 (Claude Code 직접 생성)

> **이 단계는 Claude Code가 현재 세션에서 직접 수행한다.** `tco_{CATEGORY}.json`에서 제품별 데이터를 추출하여 개별 리뷰 HTML을 생성한다.
> **상세 명세:** `Spec stepC individualreview.md` 참조

### 목적

- SEO 서포트 글 (전환 글이 아님 — CTA 없음)
- 롱테일 키워드 검색 유입 확보 ("{제품명} 리뷰", "{제품명} 단점")
- SEO 롱테일 키워드 유입으로 비교 글(Step B) 강화 (Topical Authority)
- 카테고리당 콘텐츠 볼륨: 비교 글 1개 → 비교 글 1개 + 개별 리뷰 3개 = 4개

### 실행 절차

1. `data/exports/tco_{CATEGORY}.json` 파일을 읽는다.
2. **제품 이미지 로드:** `data/processed/product_images_{CATEGORY}.json` 파일을 읽는다.
   - `products[]`에서 제품명으로 매칭하여 `images[0].public_url`을 제품 이미지로 사용한다.
   - `public_url`이 없으면 이미지 생략. 파일 자체가 없으면 이미지 없이 생성.
3. `products[]` 배열에서 각 제품을 순회하며 아래를 수행:
   a. 해당 제품 데이터 추출 (tco, consumable_breakdown, as_reputation, review_insights)
   b. 해당 제품의 이미지 URL 매칭 (product_images에서 제품명으로 검색)
   c. 5개 섹션 구조에 따라 HTML 작성 (Section 0에 제품 이미지 포함)
   d. `data/exports/review_{CATEGORY}_{PRODUCT_SLUG}.html` 저장
4. 출력 파일을 사용자에게 제공한다.

> **제품 단위 독립 생성 원칙:** 각 제품의 HTML은 독립적으로 생성한다. 1개 제품 생성에 실패해도 나머지 제품은 정상 출력한다.

### 글 구조 (5 Sections)

```
Section 0: 한줄 결론 + 제품 이미지 + 이 글의 성격 (데이터 기반 분석임을 명시)
    ← environment_splits + total_reviews + product_images (public_url)

Section 1: 이 제품, 사람들은 왜 샀을까? (구매동기 분석)
    ← purchase_motivations[]

Section 2: 실사용자들의 만족과 불만 (리뷰 인사이트)
    ├─ 2-1: 만족 포인트 ← satisfaction_keywords[]
    ├─ 2-2: 불만 포인트 ← dissatisfaction_keywords[]
    └─ 2-3: 이런 환경이면 추천 / 비추천 ← environment_splits[]

Section 3: 소모품·유지관리·AS (소유 비용)
    ├─ 3-1: 소모품 비용 상세 ← consumable_breakdown[]
    ├─ 3-2: AS 평판 ← as_reputation + as_reputation_summary
    └─ 3-3: {TCO_YEARS}년 실비용 요약

Section 4: 정리 + 내부 링크 (맞는 사람/안 맞는 사람 + 비교 글·다른 리뷰 링크)
    ← 슬러그 규칙(Step 0)에 따른 확정 URL 삽입
```

### 핵심 규칙

1. **전환 글이 아니다:** CTA("최저가 확인하기") 없음, 쿠팡 링크 없음, 제휴마케팅 공시 문구 없음.
2. **이 제품만 깊게:** 다른 제품과의 비교 없음. 비교는 비교 글(Step B)의 역할.
3. **데이터 기반 분석임을 명시:** Section 0에서 "실사용자 리뷰 N건을 수집·분석한 데이터 정리글입니다." 로 글의 성격을 밝힌다. "직접 사용 리뷰가 아닙니다" 문구는 사용하지 않는다.
3-1. **제품 이미지:** Section 0의 한줄 결론 바로 아래에 제품 이미지를 배치한다. `product_images_{CAT}.json`에서 매칭된 제품의 `images[0].public_url` 사용. `public_url`이 없으면 이미지 생략. HTML 형식은 Step B와 동일: `<div style="text-align:center; margin:20px 0;"><img src="{public_url}" alt="{제품명}" style="max-width:100%; height:auto; border-radius:8px;" loading="lazy"></div>`
4. **데이터 조작 금지:** 모든 숫자는 TCO JSON에서 주입. 절대 생성하지 않는다.
5. **금액 표기:** 천 단위 콤마 (예: 1,290,000원)
6. **"{TCO_YEARS}년 {tco_label}" 표기:** 카테고리 YAML의 `consumables.tco_label` 사용. 없으면 `{TCO_YEARS}년 실비용(구매가격+소모품비)`.
7. **제품 수 표현 금지:** "3개 제품 중", "3개의 제품 중" 등 구체적 제품 개수를 명시하지 않는다. 대신 `동일 가격대 제품 중`으로 표현한다.
8. **`<h1>` 태그 사용 금지:** 블로그 플랫폼이 title을 별도 렌더링하므로 본문은 `<h2>` 이하로만.
9. **내부 링크는 ASCII slug만 사용:** `/posts/{cat-slug}-best` (비교글), `/posts/{cat-slug}-{brand-ascii}-{model-ascii}-review` (리뷰글). 한글 URL 금지.

### 제목 패턴 (3개 로테이션)

같은 카테고리 3개 제품이 동일 패턴이면 단조로우므로 제품 순서에 따라 로테이션한다:

```
products[0] → 패턴 A: {제품명}, 사도 될까? — 리뷰 {N}건 분석 [{년도}]
products[1] → 패턴 B: {제품명} 장단점 총정리 — 실사용자 {N}건 분석 [{년도}]
products[2] → 패턴 C: {제품명} {TCO_YEARS}년 쓰면 얼마? — 소모품비·유지비 분석 [{년도}]
```

### HTML 출력 요구사항

- `<!DOCTYPE html>` + `<meta charset="UTF-8">` + 반응형 viewport
- 내장 CSS (외부 의존성 없음), 인라인 스타일 (네이버/티스토리 호환)
- `<head>`에 meta description + Schema.org JSON-LD (`@type: "Article"`) 포함
- **섹션 주석 삽입 금지** — `<!-- Section 0: ... -->` 같은 HTML 주석을 넣지 않는다. 섹션 구분은 작성 지침일 뿐, 실제 HTML 소스에 노출되면 안 된다.
- **섹션 블록 구분 스타일 (Step B와 동일):**
  - `section` — `margin-bottom:48px; padding-bottom:32px; border-bottom:2px solid #e5e7eb;`
  - `h2` — `font-size:1.5em; margin-top:48px; margin-bottom:16px; padding-bottom:10px; border-bottom:3px solid #059669;`
  - `h3` — `font-size:1.15em; margin-top:24px; margin-bottom:8px;`
- 표: `<table>` + `overflow-x: auto`
- CTA 버튼 스타일 없음.
- **제품 이미지:** Section 0 한줄 결론 아래에 `<div style="text-align:center; margin:20px 0;"><img src="{public_url}" alt="{제품명}" style="max-width:100%; height:auto; border-radius:8px;" loading="lazy"></div>` — `public_url`이 없으면 생략.
- **볼드(`<strong>`) 사용 규칙:** 소제목·라벨·핵심 문장·표 내 실비용만 볼드. 일반 본문 `<p>` 서술 문장은 볼드 금지.
- **Section 4 내부 링크:** 비교 글 및 다른 리뷰 글 링크를 슬러그 규칙(Step 0)에 따른 확정 URL로 삽입한다. placeholder(`{비교글_url}` 등) 사용 금지.

### 확인사항
- [ ] 제품당 `review_{CATEGORY}_{PRODUCT_SLUG}.html` 생성 확인 (3개)
- [ ] 각 리뷰 글: 5개 Section 구조, 숫자 TCO JSON 일치, CTA 없음
- [ ] Section 0에 제품 이미지 삽입 확인 (`public_url` 있는 제품만)
- [ ] Section 4 내부 링크가 슬러그 규칙에 따른 실제 URL인지 확인 (placeholder 없음)
- [ ] Section 0에 "실사용자 리뷰 N건을 수집·분석한 데이터 정리글" 문구 확인
- [ ] meta description + Schema.org JSON-LD 포함

---

## Step D: 블로그 자동 발행 (Supabase Publisher)

> **이 단계는 Python CLI로 실행한다.** Step B/C에서 생성된 HTML을 Next.js 블로그의 Supabase DB `posts` 테이블에 자동 삽입한다.

### 사전 조건

- `.env` 파일에 Supabase 연결 정보 설정:
  ```
  SUPABASE_URL=https://your-project.supabase.co
  SUPABASE_SERVICE_KEY=eyJhbGci-your-service-key
  ```
- `supabase` 패키지 설치: `pip install -r requirements.txt`
- Step B (`blog_{CATEGORY}.html`) 및 Step C (`review_{CATEGORY}_*.html`) 완료

### 실행

```bash
# 발행 (--update-existing 항상 포함하여 중복 방지)
python -m src.part_b.publisher.supabase_publisher \
  --tco-data data/exports/tco_{CATEGORY}.json \
  --blog-html data/exports/blog_{CATEGORY}.html \
  --review-dir data/exports/ \
  --cta-data data/processed/cta_links_{CATEGORY}.json \
  --image-data data/processed/product_images_{CATEGORY}.json \
  --publish --update-existing
```

### CLI 옵션

| 옵션 | 필수 | 설명 |
|------|------|------|
| `--tco-data` | O | `tco_{CATEGORY}.json` 경로 (Step A4 출력) |
| `--blog-html` | O | `blog_{CATEGORY}.html` 경로 (Step B 출력) |
| `--review-dir` | X | `review_*.html` 파일이 있는 디렉토리. 생략 시 비교 글만 발행 |
| `--cta-data` | X | `cta_links_{CATEGORY}.json` 경로. 리뷰 글의 coupang_url 매핑용 |
| `--publish` | O | Supabase 삽입 실행 |
| `--update-existing` | X | slug 충돌 시 기존 글 업데이트 (upsert) |

### 발행되는 포스트 (카테고리당 4개)

| # | 타입 | slug 패턴 | 예시 |
|---|------|-----------|------|
| 1 | 비교 글 | `{CATEGORY}-추천-비교` | `로봇청소기-추천-비교` |
| 2-4 | 리뷰 x3 | `{브랜드}-{모델명}-리뷰` | `로보락-s9-maxv-ultra-리뷰` |

> slug는 Step 0의 슬러그 규칙에 따라 확정된다. Step B/C HTML의 내부 링크와 동일한 slug를 사용하여 발행한다.

### 자동 처리 항목

- **HTML 추출**: `<style>` 블록 + `<body>` inner HTML -> `content` 필드 (인라인 스타일 보존)
- **`<h1>` 제거**: 블로그 플랫폼이 title을 별도 렌더링하므로 본문 `<h1>` 자동 제거 (제목 이중 노출 방지)
- **내부 링크 변환**: 한글 slug → ASCII slug 자동 치환 (예: `/posts/위닉스-at8e430-리뷰` → `/posts/air-purifier-winix-at8e430-review`)
- **FAQ 파싱**: 비교 글 Section 5의 `<details><summary>` -> `faq` JSONB (Google FAQ Rich Results 활용)
- **이미지 매핑**: `product_images_{CAT}.json`에서 `featured_image` 자동 설정
- **메타데이터 자동 생성**: title, description, tags, seo_keywords, word_count

### 확인사항

- [ ] `--publish` 후 4개 포스트 (비교 1 + 리뷰 3) 정상 삽입, 에러 0
- [ ] 블로그 사이트에서 글 노출 확인
- [ ] FAQ Rich Results 확인 (비교 글의 `faq` JSONB 필드)
- [ ] 내부 링크(비교↔리뷰) 정상 동작 확인

---

## 파이프라인 체크리스트

```
[ ] Step 0: category_{CAT_SLUG}.yaml 존재 확인 (없으면 생성)
[ ] A0: a0_selected_{CAT}.json 생성, 3개 제품 선정됨, selected_tier 확인
[ ] A-CTA: cta_links_{CAT}.json 생성, 제품당 success: true + base_url 확인
[ ]     — 3개 제품 모두 link.coupang.com 링크 포함
[ ] A-IMG: product_images_{CAT}.json 생성, 제품당 images[] 최소 1개
[ ] A2: a2_consumable_{CAT}.json 생성, 제품당 소모품 목록 + 가격
[ ]     — annual_consumable_cost = Σ(소모품 annual_cost)
[ ] A5: a5_reviews_{CAT}.json 생성, 제품당 리뷰 30건+, category_insights 포함
[ ]     — as_reputation, as_reputation_summary 포함
[ ] A4: tco_{CAT}.json 생성, selected_tier/tier_scores/tier_product_counts 포함
[ ]     — TCO 수식: real_cost_total == purchase_price + (annual_consumable_cost × TCO_YEARS)
[ ] B:  blog_{CAT}.html 생성, 6개 Section 확인
[ ]     — CTA href = cta_links_{CAT}.json의 base_url (실제 쿠팡 제휴 링크)
[ ]     — Section 3-1~3-3 제품 이미지 삽입 확인 (public_url 있는 제품만)
[ ]     — <h1> 태그 없음 (제목 이중 노출 방지)
[ ]     — 내부 링크가 ASCII slug인지 확인 (한글 URL 없음)
[ ]     — 숫자 = TCO JSON 일치 검증
[ ] C:  review_{CAT}_{PRODUCT_SLUG}.html × 3개 생성
[ ]     — 5개 Section 구조, CTA 없음
[ ]     — Section 0 제품 이미지 삽입 확인 (public_url 있는 제품만)
[ ]     — <h1> 태그 없음
[ ]     — 내부 링크가 ASCII slug인지 확인
[ ]     — Section 0 데이터 정리글 성격 명시 확인
[ ] D:  Supabase 발행 완료 (비교 1 + 리뷰 3 = 4개 포스트)
[ ]     — --publish --update-existing 후 블로그 노출 확인
[ ]     — featured_image 설정 확인
[ ]     — 내부 링크 한글→ASCII 변환 확인
```

---

## 트러블슈팅

### A2 소모품 검색 결과 부족
1. 검색어 일반화 (모델명 → 브랜드명 + 카테고리 + 소모품명)
2. 공식 부품 쇼핑몰 직접 검색
3. 가격 확인 불가 시 `notes`에 "가격 미확인" 명시, `annual_consumable_cost: 0`으로 처리

### A4 TCO 수식 불일치
```
consumable_cost_total = annual_consumable_cost × TCO_YEARS
real_cost_total = purchase_price + consumable_cost_total
```

### A5 리뷰 30건 미만
1. 보충 검색어: "장점 단점 정리", "1년 사용기", "후회 추천"
2. 최소 15건 하향, `notes`에 "리뷰 부족 — 신뢰도 제한"

### B HTML 렌더링 문제
1. 닫히지 않은 태그 확인
2. 표 `overflow-x: auto` wrapper 확인
3. `<meta charset="UTF-8">` 확인
4. 네이버/티스토리 붙여넣기 스타일 유실 → 인라인 스타일 전환

### C 개별 리뷰 콘텐츠 부족
1. 현행 A5 데이터로 5섹션 채우기 어려우면 서술을 압축 (무리하게 늘리지 않는다)
2. v2에서 A5-2 제품별 보충 검색 서브스텝 도입 검토
3. 비교 글과 중복 서술 주의 — depth로 차별화, 같은 내용 반복 금지

---

*Runbook version: 3.5*
*Last updated: 2026-02-10*
