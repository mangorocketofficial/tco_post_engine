# Module A-0: Product Selector

## 네이버 키워드 메트릭 기반 자동 제품 선정 엔진

---

## Overview

TCO 비교 파이프라인의 **첫 번째 단계**로, "어떤 3개 제품을 비교할 것인가?"를 자동으로 결정한다.

네이버 쇼핑 API에서 후보군을 수집하고, 네이버 검색광고 API의 키워드 메트릭(검색량, 클릭수, CPC, 경쟁도)으로 스코어링하여 **제조사 다양성이 보장된 TOP 3**를 선정한다.

### 파이프라인 내 위치

```
[A-0: Product Selector]  ← 이 모듈
        ↓
  3개 제품 선정 (JSON)
        ↓
[A-1~4: TCO Data Engine]
        ↓
[B: Content Engine]
```

---

## 실행 방법

```bash
# 카테고리 이름으로 바로 실행 (기본 설정 자동 생성)
python -m src.part_a.product_selector.main --category "드럼세탁기"

# YAML 설정 파일 사용 (다나와 카테고리 코드 등 세부 설정)
python -m src.part_a.product_selector.main --config config/category_robot_vacuum.yaml

# 결과를 JSON 파일로 저장
python -m src.part_a.product_selector.main --category "로봇청소기" --output result.json

# DB 저장
python -m src.part_a.product_selector.main --category "로봇청소기" --save-db

# A-0.1: 블로그 추천 모드
python -m src.part_a.product_selector.main --mode recommend --keyword "드럼세탁기" --top-n 3
```

---

## 4단계 파이프라인

```
Step 1: 네이버 쇼핑 API → 후보 제품 20개 수집
Step 2: 네이버 검색광고 API → 키워드 메트릭 조회
Step 3: 스코어링 → TOP 3 선정 (제조사 다양성 적용)
Step 4: 검증 (brand_diversity, keyword_data)
```

### Step 1: 후보 수집 (Naver Shopping API)

네이버 쇼핑 검색 API(`openapi.naver.com/v1/search/shop.json`)로 카테고리 키워드 검색 → 상위 20개 제품 수집.

```
입력: "드럼세탁기"
출력: 20개 CandidateProduct (이름, 브랜드, 가격, 제품코드, 순위)
```

| 필드 | 출처 | 설명 |
|------|------|------|
| `product_name` | API `title` (HTML 태그 제거) | 전체 제품명 |
| `brand` | API `brand` | **제품 라인명** (트롬, 그랑데, 비스포크AI콤보 등) |
| `price` | API `lprice` | 최저가 |
| `product_code` | API `productId` | 네이버 제품 코드 |
| `rank` | 결과 순서 (1-based) | 네이버 쇼핑 노출 순위 |

> **중요:** 네이버 쇼핑 API의 `brand` 필드는 제조사(삼성, LG)가 아니라 **제품 라인명**(트롬, 그랑데, 비스포크AI콤보)을 반환한다. 일부 제품은 `brand="삼성"` 처럼 제조사명과 동일한 값이 반환되기도 한다.

### Step 2: 키워드 메트릭 조회 (Naver Search Ad API)

각 제품의 `제조사 + 제품라인명` 조합으로 키워드를 생성하고, 검색광고 API에서 메트릭을 조회한다.

#### 키워드 빌드 로직 (`_build_product_keyword`)

```
제품명에서 제조사 추출 + brand 필드 조합 → API 키워드

("삼성전자 그랑데 WF19T6000KW 화이트", brand="그랑데")  → "삼성그랑데"
("LG전자 트롬 오브제 FX25ESR", brand="트롬")            → "LG트롬"
("삼성전자 비스포크AI콤보 25/18kg", brand="비스포크AI콤보") → "삼성비스포크AI콤보"
("삼성전자 삼성 WF21DG6650B", brand="삼성")             → "" (스킵 — 너무 포괄적)
```

| 조건 | 결과 | 이유 |
|------|------|------|
| `brand`가 특정 제품라인명 | `제조사 + brand` | 적절한 제품라인 키워드 |
| `brand == 제조사` (예: brand="삼성") | `""` (스킵) | "삼성" 전체 브랜드 검색량이 매칭되어 부풀림 |
| `brand` 없음 | `""` (스킵) | 제조사명만으로는 너무 포괄적 |

#### 제조사 추출 (`extract_manufacturer`)

제품명 prefix에서 제조사를 정규화:

| Prefix | 추출 결과 |
|--------|----------|
| `LG전자 ...` | `LG` |
| `삼성전자 ...` | `삼성` |
| `대우전자 ...` | `대우` |
| `위니아딤채 ...` / `위니아 ...` | `위니아` |
| `LG ...` (전자 없이) | `LG` |
| 기타 | `""` (brand로 fallback) |

#### 키워드 그룹핑

동일 키워드를 공유하는 제품끼리 그룹핑 → API 호출 최소화.

```
20개 제품 → 6~7개 고유 키워드 → API 2회 호출 (배치당 5개)
```

같은 키워드 그룹의 제품들은 동일한 메트릭을 공유 (`dataclasses.replace()`로 `product_name`만 변경).

#### API 인증

```
HMAC-SHA256 서명: "{timestamp}.{method}.{uri}"
헤더: X-Timestamp, X-API-KEY, X-Customer, X-Signature
```

| 환경변수 | 설명 |
|---------|------|
| `NAVER_AD_CUSTOMER_ID` | 광고주 ID |
| `NAVER_AD_API_KEY` | API 키 |
| `NAVER_AD_SECRET_KEY` | Secret 키 (HMAC용) |

#### API 응답 매칭

1. 정규화된 exact match (대소문자 무시, 공백 제거)
2. Substring match (fallback)
3. 중복 매칭 방지 (`matched_keywords` set)

### Step 3: 스코어링 & TOP 3 선정

#### 스코어 계산 (`ProductScorer`)

4개 차원, min-max 정규화 (0.0~1.0):

| 차원 | 가중치 | 데이터 소스 | 의미 |
|------|--------|-----------|------|
| **Monthly Clicks** | 40% | `keyword_metrics.monthly_clicks` | 실제 사용자 참여도 |
| **Average CPC** | 30% | `keyword_metrics.avg_cpc` | 상업적 가치 (광고 경쟁) |
| **Search Volume** | 20% | `keyword_metrics.monthly_search_volume` | 소비자 인지도 |
| **Competition** | 10% | `keyword_metrics.competition` | 시장 검증도 |

```python
total_score = clicks × 0.4 + cpc × 0.3 + search_volume × 0.2 + competition × 0.1
```

#### TOP 3 선정 (`TopSelector`)

1. 전체 후보를 `total_score` 내림차순 정렬
2. **제조사 다양성 우선**: 이미 선정된 제조사의 제품은 스킵
3. 다양성으로 3개를 못 채우면 **제약 완화**하여 나머지 충원 (사유에 `(brand diversity relaxed)` 표시)

```
예시: 삼성 1.000 → LG 0.619 → [LG 스킵] → 위니아 0.508
      제조사 다양성 OK: 삼성, LG, 위니아
```

### Step 4: 검증

| 검증 항목 | 조건 | 설명 |
|----------|------|------|
| `brand_diversity` | 선정 3개 제품의 제조사가 모두 다른가 | `c.manufacturer` 기준 (제품라인명이 아닌 실제 제조사) |
| `keyword_data` | 최소 1개 이상 키워드 메트릭이 있는가 | clicks > 0인 제품 수 확인 |

---

## 파일 구조

### 핵심 파일 (현재 파이프라인)

| 파일 | 역할 |
|------|------|
| `pipeline.py` | 4단계 파이프라인 오케스트레이터 |
| `models.py` | 데이터 모델 (`CandidateProduct`, `KeywordMetrics`, `ProductScores`, `SelectedProduct`, `SelectionResult` 등) |
| `naver_ad_client.py` | 네이버 검색광고 API 클라이언트 (HMAC 인증, 키워드 메트릭 조회) |
| `scorer.py` | 키워드 메트릭 기반 스코어링 (min-max 정규화, 가중 합산) |
| `slot_selector.py` | TOP 3 선정 (제조사 다양성 적용) |
| `sales_ranking_scraper.py` | 네이버 쇼핑 / 다나와 / 쿠팡 랭킹 수집 |
| `category_config.py` | 카테고리 설정 (YAML 로드/저장) |
| `main.py` | CLI 진입점 (`--category`, `--config`, `--mode`) |

### 보조 파일

| 파일 | 역할 |
|------|------|
| `danawa_category_resolver.py` | 다나와 검색 페이지에서 카테고리 코드 자동 추출 |
| `price_classifier.py` | 가격 티어 분류 (premium / mid / budget) |
| `resale_quick_checker.py` | 당근마켓 리세일 비율 간이 조회 |
| `search_interest_scraper.py` | 네이버 데이터랩 검색 관심도 |
| `sentiment_scraper.py` | 뽐뿌/클리앙/네이버카페 커뮤니티 감성 |
| `candidate_aggregator.py` | 다중 플랫폼 후보 교차 검증 (레거시) |
| `validator.py` | 확장 검증 로직 (레거시) |

### A-0.1: 블로그 추천 파이프라인

| 파일 | 역할 |
|------|------|
| `recommendation_pipeline.py` | 블로그 검색 → 제품 추출 → 빈도 집계 오케스트레이터 |
| `blog_recommendation_scraper.py` | 네이버 블로그 + Google SerpAPI 검색 |
| `product_name_extractor.py` | DeepSeek LLM으로 블로그 제목/본문에서 제품명 추출 |

---

## 데이터 모델

### CandidateProduct

```python
@dataclass
class CandidateProduct:
    name: str                           # "삼성전자 비스포크 그랑데 드럼 세탁기 AI 24kg ..."
    brand: str                          # "비스포크" (제품 라인명, 네이버 쇼핑 API)
    category: str                       # "드럼세탁기"
    product_code: str = ""              # 네이버 제품 ID
    price: int = 0                      # 최저가 (KRW)
    naver_rank: int = 0                 # 네이버 쇼핑 노출 순위
    keyword_metrics: KeywordMetrics | None = None  # Step 2에서 채워짐

    @property
    def manufacturer(self) -> str:      # "삼성" (제품명에서 추출, brand로 fallback)
```

### KeywordMetrics

```python
@dataclass
class KeywordMetrics:
    product_name: str
    monthly_search_volume: int = 0      # PC + Mobile 월간 검색량
    monthly_clicks: int = 0             # PC + Mobile 월간 클릭수
    avg_cpc: int = 0                    # 평균 클릭 단가 (KRW)
    competition: str = "low"            # "high" | "medium" | "low"
```

### ProductScores

```python
@dataclass
class ProductScores:
    product_name: str
    clicks_score: float = 0.0           # 0.0~1.0 정규화
    cpc_score: float = 0.0
    search_volume_score: float = 0.0
    competition_score: float = 0.0

    @property
    def total_score(self) -> float:     # 가중 합산
        # clicks×0.4 + cpc×0.3 + search_volume×0.2 + competition×0.1
```

---

## 출력 형식

```json
{
  "category": "드럼세탁기",
  "selection_date": "2026-02-08",
  "data_sources": {
    "candidates": "naver_shopping_api",
    "scoring": "naver_searchad_api"
  },
  "candidate_pool_size": 20,
  "selected_products": [
    {
      "rank": 1,
      "name": "삼성전자 비스포크 그랑데 드럼 세탁기 AI 24kg ...",
      "brand": "비스포크",
      "price": 1299000,
      "selection_reasons": [
        "Monthly clicks: 57",
        "Avg CPC: 10원",
        "Monthly searches: 8,230",
        "Competition: high",
        "Total score: 1.000"
      ],
      "scores": {
        "clicks_score": 1.0,
        "cpc_score": 1.0,
        "search_volume_score": 1.0,
        "competition_score": 1.0,
        "total_score": 1.0
      }
    }
  ],
  "validation": {
    "brand_diversity": "FAIL — 2 unique manufacturers: LG, 삼성",
    "keyword_data": "PASS — 3/3 products have keyword metrics"
  }
}
```

---

## 카테고리 설정

### 방법 1: 카테고리 이름으로 즉시 실행

```bash
python -m src.part_a.product_selector.main --category "벽걸이TV"
```

`CategoryConfig.from_category_name("벽걸이TV")` → 기본 설정으로 자동 생성.

### 방법 2: YAML 설정 파일

```yaml
# config/category_drum_washer.yaml
name: "드럼세탁기"
search_terms: ["드럼세탁기"]
danawa_category_code: "10248425"
negative_keywords: ["불만", "후회", "실망", "반품", "고장", "AS", "수리", "오류"]
positive_keywords: ["추천", "만족", "최고", "잘샀다", "좋아요", "강추"]
price_range:
  min: 300000
  max: 3000000
max_product_age_months: 18
min_community_posts: 20
```

`danawa_category_code`가 없으면 `DanawaCategoryResolver`가 검색 페이지에서 자동 추출을 시도한다.

---

## 필요 환경변수

```env
# 네이버 쇼핑 검색 API (Step 1)
NAVER_DATALAB_CLIENT_ID=...
NAVER_DATALAB_CLIENT_SECRET=...

# 네이버 검색광고 API (Step 2)
NAVER_AD_CUSTOMER_ID=...
NAVER_AD_API_KEY=...
NAVER_AD_SECRET_KEY=...
```

---

## 테스트

```bash
# 전체 프로젝트 테스트
pytest tests/

# Product Selector 테스트만 (122 tests)
pytest tests/part_a/test_product_selector.py -v

# A-0.1 추천 파이프라인 테스트만 (55 tests)
pytest tests/part_a/test_recommendation.py -v
```

### 테스트 커버리지

| 테스트 클래스 | 항목 수 | 대상 |
|-------------|--------|------|
| TestExtractManufacturer | 5 | 제조사 추출 로직 |
| TestManufacturerProperty | 3 | CandidateProduct.manufacturer fallback |
| TestBuildProductKeyword | 8 | 키워드 빌드 + 포괄적 키워드 스킵 |
| TestCleanKeyword | 14 | 키워드 클리닝 (레거시, 참조용) |
| TestNaverAdClient | 6 | API 파싱, 대소문자, 중복 방지 |
| TestNaverAdClientHelpers | 6 | `_safe_int`, `_map_competition` |
| TestProductScorer | 3 | 스코어링 정규화 |
| TestTopSelector | 5 | TOP 3 선정, 다양성, relaxation |
| 기타 모델/스크래퍼 | 72+ | 데이터 모델, HTML 파싱 등 |

---

## 해결된 기술 이슈

### 1. HMAC 서명 오류 (403)

**문제:** `{timestamp}.{uri}` 형식 → 403 Forbidden
**해결:** `{timestamp}.{method}.{uri}` 형식으로 수정 (`GET` 포함 필수)

### 2. 키워드 400 에러

**문제:** 제품명에 공백 포함 → API 400 에러
**해결:** `_build_product_keyword()`에서 `.replace(" ", "")` 처리

### 3. 브랜드 수준 검색량 부풀림

**문제:** 키워드 "LG트롬" → 월간검색 98,100 (브랜드 전체 수치가 개별 제품에 배정)
**해결:** 제품명 클리닝 → 제조사+제품라인 기반 키워드로 전환. 동일 키워드 그룹은 메트릭 공유.

### 4. 브랜드 다양성 오판

**문제:** 네이버 쇼핑 `brand` 필드가 제품라인명(트롬, 그랑데, 비스포크AI콤보) → 모두 다른 브랜드로 인식
**해결:** `extract_manufacturer()`로 제품명에서 실제 제조사(삼성, LG) 추출. `manufacturer` 기준 다양성 체크.

### 5. 포괄적 키워드 "삼성" 부풀림

**문제:** `brand="삼성"` (제조사명과 동일) → 키워드 "삼성" → 월간검색 246,500 배정
**해결:** `brand == manufacturer`이면 키워드 생성 스킵. 해당 제품은 `keyword_metrics=None` → 점수 낮아짐.

---

## A-0.1: 블로그 가성비 추천 Top 제품 탐색기

A-0과 별개로, **블로그 검색 기반 가성비 추천 제품**을 자동으로 찾아내는 파이프라인.

사용자가 "드럼세탁기" 같은 카테고리 키워드를 입력하면, "가성비 드럼세탁기"로 네이버/구글 블로그를 검색하여 커뮤니티에서 실제로 가장 많이 추천된 **Top 1, 2 제품**을 자동으로 선별한다.

### 실행 방법

```bash
# 기본 실행 (Top 2)
python -m src.part_a.product_selector.main --mode recommend --keyword "드럼세탁기"

# Top 3 추출
python -m src.part_a.product_selector.main --mode recommend --keyword "드럼세탁기" --top-n 3

# 결과를 JSON 파일로 저장
python -m src.part_a.product_selector.main --mode recommend --keyword "로봇청소기" --output result.json
```

### 파이프라인 흐름

```
사용자 입력: "드럼세탁기"
    ↓
Step 1: "가성비 드럼세탁기" 쿼리 생성
    ↓
Step 2: 네이버 블로그 API (50개) + Google SerpAPI (50개) = 블로그 ~100개 수집
    ↓
Step 3: DeepSeek LLM에 배치 전송 (5개씩 묶어 ~20회 호출)
    → 각 글에서 언급된 구체적 제품명(브랜드+모델명) 추출
    ↓
Step 4: 모델코드 기반 그룹핑 → 빈도 카운트 → Top N 확정
    ↓
RecommendationResult 반환
```

### Step 1-2: 블로그 검색 (`blog_recommendation_scraper.py`)

두 가지 검색 소스를 사용:

| 소스 | API | 건수 | 특징 |
|------|-----|------|------|
| **네이버** | Naver Blog Search API (`openapi.naver.com/v1/search/blog.json`) | 50개 | `X-Naver-Client-Id/Secret` 헤더 인증, `display` 최대 100, `sort=sim` |
| **구글** | SerpAPI (`google-search-results` SDK) | 50개 | 페이지당 10개, `hl=ko`, `gl=kr` |

- 검색 쿼리: `"가성비 {keyword}"` (예: "가성비 드럼세탁기")
- 네이버 API 응답의 HTML 태그(`<b>`, `</b>` 등)는 자동 제거
- API 키 미설정 시 해당 소스는 빈 리스트 반환 (graceful degradation)

### Step 3: 제품명 추출 (`product_name_extractor.py`)

**DeepSeek API**를 OpenAI SDK 호환 방식으로 호출하여 블로그 제목/스니펫에서 구체적 제품명을 추출한다.

| 항목 | 설정 |
|------|------|
| API Endpoint | `https://api.deepseek.com` (OpenAI SDK `base_url`) |
| 모델 | `deepseek-chat` |
| Temperature | `0.1` |
| 배치 크기 | 5개 snippet/호출 |
| API 키 | `os.getenv("DEEPSEEK_API_KEY")` |

#### 프롬프트 구조

```
다음은 "{keyword}" 관련 블로그 검색 결과입니다.
각 글에서 추천하는 구체적인 제품명(브랜드 + 모델명)을 추출해주세요.

[1] 제목: ...
    내용: ...
    출처: https://...

JSON 배열로 반환: ["삼성전자 그랑데 AI WF24B9600KW", "LG 트롬 오브제컬렉션 FX25ESR", ...]
```

#### 응답 파싱

1. 직접 JSON 파싱 시도
2. 마크다운 코드 블록 (`\`\`\`json ... \`\`\``) 내부 추출
3. Fallback: 정규식으로 한글+영문+숫자 패턴 추출

### Step 4: 빈도 집계 & 랭킹 (`recommendation_pipeline.py`)

#### 모델코드 기반 그룹핑

단순 문자열 비교로는 같은 제품이 다르게 인식되는 문제를 해결하기 위해, **모델코드(alphanumeric code) 기반 그룹핑**을 사용한다.

**문제 상황:**
```
"삼성전자 그랑데 WF19T6000KW"     → 1회
"삼성 WF19T6000KW"               → 1회
"삼성전자 드럼세탁기 WF19T6000KW"  → 1회
→ 실제로는 같은 제품인데 3개로 분리됨 (합산하면 3회)
```

**해결 전략 (3-Phase):**

| Phase | 대상 | 방법 |
|-------|------|------|
| Phase 1 | 모델코드 있는 제품 | 모델코드 추출 → 동일 코드끼리 그룹핑 |
| Phase 2 | 모델코드 없는 제품 | 정규화된 이름으로 그룹핑 (fallback) |
| Phase 3 | 전체 | 통합 정렬 → Top N 추출 |

#### 모델코드 추출 (`_extract_model_code`)

- **조건:** 5자 이상, 영문자와 숫자가 모두 포함된 토큰
- **하이픈 처리:** `GR-B267CEB` → `GRB267CEB`으로 정규화
- **제외:** 순수 숫자(`12345678`), 순수 알파벳(`ABCDEF`), 4자 이하 토큰

```
"삼성전자 그랑데 WF19T6000KW"  → WF19T6000KW
"LG전자 트롬 F21VDSK"         → F21VDSK
"LG 트롬 GR-B267CEB"          → GRB267CEB
"LG 트롬 오브제컬렉션"          → "" (모델코드 없음 → Phase 2 fallback)
```

#### 정규화 (`_normalize_name`, Phase 2 fallback)

모델코드가 없는 제품명에 적용:
- NFKC 유니코드 정규화
- 소문자 변환
- 괄호/대괄호 내용 제거: `(화이트)`, `[32kg]`, `（실버）`
- 공백 정리

### 파일 구조

| 파일 | 역할 |
|------|------|
| `recommendation_pipeline.py` | 전체 흐름 오케스트레이터 (검색 → 추출 → 집계) |
| `blog_recommendation_scraper.py` | 네이버 Blog API + Google SerpAPI 검색 |
| `product_name_extractor.py` | DeepSeek LLM으로 블로그 snippet에서 제품명 추출 |

### 데이터 모델 (`models.py` 에 추가)

```python
@dataclass
class BlogSearchResult:
    title: str           # 블로그 제목
    snippet: str         # 본문 요약
    link: str            # URL
    source: str          # "naver" | "google"
    rank: int            # 검색 결과 내 순위

@dataclass
class ProductMention:
    product_name: str      # 원본 추출명 (가장 많이 등장한 형태)
    normalized_name: str   # 그룹 키 (모델코드 or 정규화명)
    mention_count: int     # 언급 횟수
    sources: list[str]     # 언급된 블로그 출처 URL

@dataclass
class RecommendationResult:
    keyword: str                          # 원본 키워드
    search_query: str                     # 실제 검색 쿼리
    total_blogs_searched: int             # 검색된 블로그 수
    total_products_extracted: int         # 추출된 제품명 총 수
    top_products: list[ProductMention]    # Top N 제품
    search_date: str                      # 실행 일시
```

### 출력 예시

```json
{
  "keyword": "드럼세탁기",
  "search_query": "가성비 드럼세탁기",
  "total_blogs_searched": 96,
  "total_products_extracted": 70,
  "top_products": [
    {
      "product_name": "삼성전자 그랑데 WF19T6000KW",
      "normalized_name": "WF19T6000KW",
      "mention_count": 8,
      "sources": ["https://blog.naver.com/...", "https://example.com/..."]
    },
    {
      "product_name": "LG전자 트롬 F21VDSK",
      "normalized_name": "F21VDSK",
      "mention_count": 5,
      "sources": ["https://blog.naver.com/...", "https://example.com/..."]
    }
  ],
  "search_date": "2026-02-08T15:30:00"
}
```

### 필요 환경변수

```env
# 네이버 블로그 검색 API (네이버 소스)
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...

# SerpAPI (구글 소스)
SERPAPI_KEY=...

# DeepSeek API (제품명 추출)
DEEPSEEK_API_KEY=...
```

### 테스트

```bash
# A-0.1 추천 파이프라인 테스트 (55 tests)
pytest tests/part_a/test_recommendation.py -v
```

| 테스트 클래스 | 항목 수 | 대상 |
|-------------|--------|------|
| TestBlogSearchResult | 2 | 모델 생성, 직렬화 |
| TestProductMention | 3 | 모델 생성, 직렬화, 기본값 |
| TestRecommendationResult | 3 | 모델 생성, 직렬화, JSON |
| TestBlogRecommendationScraper | 12 | 네이버 API 파싱, 구글 페이징, graceful degradation |
| TestProductNameExtractor | 10 | 배치 처리, 프롬프트, JSON 파싱, 에러 처리 |
| TestRecommendationPipeline | 16 | 정규화, 모델코드 추출, 그룹핑, 전체 흐름, 직렬화 |

### 해결된 기술 이슈

#### 1. SerpAPI Naver 엔진 0건 반환

**문제:** SerpAPI의 `engine="naver"` + `where=post` 조합으로 네이버 블로그를 검색했으나 0건 반환
**해결:** 네이버 검색은 **Naver Blog Search API** (`openapi.naver.com/v1/search/blog.json`)를 직접 사용하도록 변경. SerpAPI는 구글 검색에만 사용.

#### 2. 제품명 중복 인식 실패 (정규화 한계)

**문제:** 68개 추출 → 62개 고유 이름. 같은 모델(WF19T6000KW)이 "삼성전자 그랑데 WF19T6000KW", "삼성 WF19T6000KW", "삼성전자 드럼세탁기 WF19T6000KW" 등으로 분산됨. 단순 lowercase + 괄호 제거로는 병합 불가.
**해결:** **모델코드 기반 그룹핑** 도입. 제품명에서 모델코드(영문+숫자 조합 5자 이상)를 추출하고, 동일 모델코드를 가진 항목을 하나로 그룹핑. 모델코드가 없는 제품은 정규화된 이름으로 fallback.

---

## 파이프라인 통합

```
[A-0: Product Selector]
  │
  │  Output: 3개 제품 + 키워드 메트릭 JSON
  ▼
[A-1: Price Tracker]           ─┐
[A-2: Resale Tracker]           │
[A-3: Repair Analyzer]          ├─ Part A (TCO 데이터 수집)
[A-4: Maintenance Calculator]  ─┘
  │
  │  Output: 제품별 TCO 데이터
  ▼
[B-1: Template Engine]         ─┐
[B-2: Content Writer]           ├─ Part B (콘텐츠 생성)
[B-3: CTA Manager]             ─┘
  │
  │  Output: 블로그 포스트
  ▼
[B-4: Stats Dashboard]
```

---

*Module version: 2.1 (A-0.1 블로그 추천 파이프라인 추가)*
*Last updated: 2026-02-08*
*Parent document: TCO-Driven Affiliate Marketing Automation System*
