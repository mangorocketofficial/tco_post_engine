# TCO Pipeline Runbook

> Claude Code가 이 문서를 읽고 순서대로 실행하는 파이프라인 가이드입니다.
> 사용법: "RUNBOOK.md를 보고 {카테고리명} 파이프라인 실행해줘"

## 사전 조건

```bash
pip install -r requirements.txt
```

- `.env` 파일에 필요한 API 키 설정 완료
- `config/` 디렉토리에 카테고리 YAML 설정 존재

---

## Step 0: 변수 설정

파이프라인 시작 전, 아래 변수를 카테고리에 맞게 설정한다.

```
CATEGORY = "로봇청소기"                    # 카테고리 한글명
KEYWORD  = "로봇청소기"                    # 검색 키워드
CONFIG   = "config/products_robot_vacuum.yaml"  # 카테고리 설정 파일 (있는 경우)
```

---

## Step A0: 제품 선정 (Python)

3개 제품을 자동 선정한다. output JSON에서 제품명을 기록해둔다.

```bash
python -m src.part_a.product_selector.main --mode final --keyword "{KEYWORD}" --output data/processed/a0_selected_{CATEGORY}.json
```

### 확인사항
- `data/processed/a0_selected_{CATEGORY}.json` 생성 확인
- 선정된 3개 제품명 기록:
  - PRODUCT_1 = ""
  - PRODUCT_2 = ""
  - PRODUCT_3 = ""

---

## Step A1: 신품 가격 수집 (Python)

선정된 3개 제품의 다나와 가격을 수집한다. 제품당 한 번씩 실행.

```bash
python -m src.part_a.price_tracker.main --keyword "{PRODUCT_1}" --save-db --output data/processed/a1_price_{PRODUCT_1}.json
python -m src.part_a.price_tracker.main --keyword "{PRODUCT_2}" --save-db --output data/processed/a1_price_{PRODUCT_2}.json
python -m src.part_a.price_tracker.main --keyword "{PRODUCT_3}" --save-db --output data/processed/a1_price_{PRODUCT_3}.json
```

### 확인사항
- 각 제품의 `purchase_price_avg`, `purchase_price_min` 확인
- DB에 prices 테이블에 레코드 저장 확인

---

## Step A2: 중고 시세 조사 (Claude Code WebSearch)

> **이 단계는 Claude Code가 WebSearch/WebFetch를 사용해서 직접 수행한다.**

각 제품에 대해 아래 절차를 수행한다:

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

3. **신품가 대비 잔존율 계산**:
   - `retention_1yr = resale_1yr / purchase_price_avg`
   - `retention_2yr = resale_2yr / purchase_price_avg`
   - `retention_3yr = resale_3yr / purchase_price_avg`

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

2. **데이터 추출** — 검색 결과에서 아래 정보 수집:
   - 고장 유형별 수리 비용 (모터, 센서, 배터리 등)
   - AS 평균 소요 기간 (일)
   - 무상 보증 기간
   - 유상 수리 비용 범위

3. **기대 수리비 계산**:
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
      "notes": "검색 중 특이사항 메모"
    }
  ]
}
```

---

## Step A4: TCO 계산 및 최종 Export (Python)

A1(DB) + A2(JSON) + A3(JSON) 데이터를 통합하여 TCO를 계산한다.

```bash
python -m src.part_a.tco_engine.main --category "{CATEGORY}" --a2-data data/processed/a2_resale_{CATEGORY}.json --a3-data data/processed/a3_repair_{CATEGORY}.json --output data/exports/tco_{CATEGORY}.json
```

### 확인사항
- `data/exports/tco_{CATEGORY}.json` 생성 확인
- 각 제품의 TCO 수식 검증: `real_cost_3yr = purchase_avg + repair_cost - resale_2yr`
- api-contract.json 스키마와 일치하는지 확인

---

## Step B: 블로그 포스트 생성 (Python)

TCO 데이터로 블로그 글을 생성한다.

```bash
python -m src.part_b.content_writer.main --category "{CATEGORY}" --tco-data data/exports/tco_{CATEGORY}.json
```

---

## 파이프라인 요약

| Step | 실행 주체 | 입력 | 출력 |
|------|-----------|------|------|
| A0 | Python CLI | 카테고리 키워드 | `a0_selected_{CAT}.json` |
| A1 | Python CLI | 제품명 3개 | DB prices + `a1_price_*.json` |
| A2 | **Claude WebSearch** | 제품명 3개 | `a2_resale_{CAT}.json` |
| A3 | **Claude WebSearch** | 제품명 3개 | `a3_repair_{CAT}.json` |
| A4 | Python CLI | DB + A2 + A3 JSON | `tco_{CAT}.json` |
| B | Python CLI | `tco_{CAT}.json` | 블로그 포스트 |
