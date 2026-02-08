"""System and section prompts for LLM-based blog content generation.

All prompts enforce the rule: NEVER fabricate data.
All numbers must be injected from Part A TCO data.
"""

SYSTEM_PROMPT = """\
당신은 한국 가전제품 TCO(총소유비용) 분석 블로그 전문 작가입니다.

## 핵심 규칙
1. **데이터 조작 금지**: 제공된 TCO 데이터의 숫자를 절대 변경하거나 새로 만들지 마세요.
2. **구어체 한국어**: 자연스럽고 친근한 한국어로 작성하세요. "~입니다" 체와 "~해요" 체를 적절히 혼용하세요.
3. **데이터 기반 주장**: 모든 추천/비추천은 반드시 TCO 수치로 뒷받침되어야 합니다.
4. **SEO 최적화**: H2/H3 제목에 롱테일 키워드를 자연스럽게 포함하세요.
5. **CTA 문구 통일**: "최저가 확인하기"를 사용하세요.
6. **공시 문구 포함**: "국내 주요 커뮤니티 리뷰 데이터 N건을 자체 분석한 결과"

## 톤 가이드
- 전문가처럼 분석하되, 친구에게 설명하듯 쉽게 쓰세요
- "스펙 비교는 의미 없다" → "3년간 실제로 드는 비용"으로 프레이밍
- 숫자에는 반드시 단위(원, 일, 분)를 붙이세요
- 금액은 천 단위 콤마 표기 (예: 1,290,000원)

## 구조 규칙
- 각 섹션별 지정된 분량을 지키세요
- 섹션 간 자연스러운 전환 문장을 넣으세요
- 표는 마크다운 표 형식을 사용하세요
"""


def build_enrichment_prompt(
    category: str,
    products_data: list[dict],
    repair_context: list[dict],
) -> str:
    """Build the user prompt for enriching product data with editorial content.

    This prompt asks the LLM to generate:
    - situation_picks (situation-based recommendations)
    - home_types (home type recommendations)
    - faqs (FAQ entries from community pain points)
    - Per-product: highlight, verdict, recommendation_reason, caution_reason

    Args:
        category: Product category name (e.g., "로봇청소기")
        products_data: List of product dicts with TCO data
        repair_context: List of repair stats per product for FAQ generation

    Returns:
        Formatted user prompt string
    """
    products_section = _format_products_for_prompt(products_data)
    repair_section = _format_repair_context(repair_context)

    return f"""\
아래는 "{category}" 카테고리의 TCO 분석 데이터입니다.
이 데이터를 기반으로 블로그 콘텐츠 요소를 생성해주세요.

## 제품 TCO 데이터
{products_section}

## 커뮤니티 수리/AS 데이터
{repair_section}

## 생성 요청

아래 JSON 형식으로 정확하게 응답해주세요. 숫자 데이터는 위에 제공된 것만 사용하세요.

```json
{{
  "situation_picks": [
    {{"situation": "상황 설명 (예: 고장 스트레스 싫은 분)", "product_name": "제품명", "reason": "추천 이유 + TCO 핵심 수치 1개 (예: 3년 실비용 606,330원, AS 평균 3일)"}},
    {{"situation": "상황 설명", "product_name": "제품명", "reason": "추천 이유 + TCO 핵심 수치"}},
    {{"situation": "상황 설명", "product_name": "제품명", "reason": "추천 이유 + TCO 핵심 수치"}}
  ],
  "category_criteria": {{
    "myth_busting": "이 카테고리에서 흔히 비교하는 스펙이 실제로는 큰 차이가 없는 이유 설명 (2-3문장, 카테고리에 특화된 구체적 내용)",
    "real_differentiator": "이 카테고리에서 진짜 비용 차이를 만드는 숨은 요인 설명 (2-3문장, 3년 실비용에서 어떤 영향을 주는지)",
    "decision_fork": "집 유형/생활 패턴에 따라 어떤 기준이 중요한지 2-3가지 갈림길 제시 (2-3문장)"
  }},
  "home_types": [
    {{"type": "집 유형 (예: 소형 원룸)", "recommendation": "추천 내용"}},
    {{"type": "집 유형 (예: 중형 아파트)", "recommendation": "추천 내용"}},
    {{"type": "집 유형 (예: 대형 주택)", "recommendation": "추천 내용"}}
  ],
  "faqs": [
    {{"question": "자주 묻는 질문 (SEO 롱테일 키워드 포함)", "answer": "답변 (데이터 기반)"}},
    {{"question": "질문", "answer": "답변"}},
    {{"question": "질문", "answer": "답변"}}
  ],
  "products": [
    {{
      "product_id": "제품ID",
      "highlight": "핵심 추천 포인트 (한 줄)",
      "slot_label": "추천 슬롯 라벨 (예: '고장 스트레스 제로', '풀옵션 올인원', '최소 비용 실속')",
      "verdict": "recommend 또는 caution",
      "recommendation_reason": "추천 이유 (2-3문장, TCO 데이터 인용)",
      "caution_reason": "주의점 (1-2문장)"
    }}
  ]
}}
```

## 주의사항
- situation_picks: 정확히 3개, 각각 다른 상황 + 반드시 TCO 핵심 수치 포함
- category_criteria: 반드시 이 카테고리에 특화된 내용 (일반적인 TCO 공식 설명 금지)
  - myth_busting: "이 스펙은 의미 없다"를 구체적 데이터로 설명
  - real_differentiator: 3년 실비용에서 실제 차이를 만드는 숨은 요인
  - decision_fork: 독자가 자기 상황에 맞는 제품을 고를 수 있게 갈림길 제시
- home_types: 정확히 3개 (소형/중형/대형)
- faqs: 3~5개
- **FAQ 중복 금지**: FAQ는 category_criteria(Section 2)에서 다룬 내용을 반복하면 안 됩니다
- **FAQ 중복 금지**: FAQ는 제품별 추천/주의 분석(Section 4)에서 다룬 내용을 반복하면 안 됩니다
- FAQ는 새로운 관점의 질문만: 특정 고장 유형, AS 접수 방법, 호환 소모품, 소음, 호환성 등
- FAQ는 커뮤니티 수리/AS 데이터의 실제 고충에서 도출
- products: 입력된 모든 제품에 대해 생성
- slot_label: 각 제품의 포지셔닝을 나타내는 맥락적 라벨 (제네릭한 "안정형" 대신 "고장 스트레스 제로" 같은 구체적 표현)
- verdict: 3년 실질비용이 가장 낮은 제품은 "recommend", AS 기간이 길거나 수리비가 높은 제품은 "caution"
- 모든 금액은 원래 데이터 그대로 사용 (절대 변경 금지)
"""


def _format_products_for_prompt(products_data: list[dict]) -> str:
    """Format product data into a readable prompt section."""
    lines = []
    for p in products_data:
        tco = p.get("tco", {})
        lines.append(f"""### {p['name']} ({p['brand']})
- 평균 구매가: {tco.get('purchase_price_avg', 0):,}원
- 최저가: {tco.get('purchase_price_min', 0):,}원
- 1년 내 중고가: {tco.get('resale_value_1yr', 0):,}원
- 2년 중고가: {tco.get('resale_value_2yr', 0):,}원
- 3년+ 중고가: {tco.get('resale_value_3yr_plus', 0):,}원
- 예상 수리비: {tco.get('expected_repair_cost', 0):,}원
- **3년 실질비용: {tco.get('real_cost_3yr', 0):,}원**
- AS 평균 소요일: {tco.get('as_turnaround_days', 0)}일
""")
    return "\n".join(lines)


def _format_repair_context(repair_context: list[dict]) -> str:
    """Format repair stats into a readable prompt section."""
    lines = []
    for r in repair_context:
        product_name = r.get("product_name", "")
        total = r.get("total_reports", 0)
        lines.append(f"### {product_name} (리뷰 {total}건)")
        for ft in r.get("failure_types", []):
            lines.append(
                f"- {ft['type']}: {ft['count']}건, "
                f"평균 수리비 {ft.get('avg_cost', 0):,}원, "
                f"발생확률 {ft.get('probability', 0):.0%}"
            )
        lines.append("")
    return "\n".join(lines)


def build_title_prompt(category: str, products: list[dict]) -> str:
    """Build prompt for generating blog post title.

    Args:
        category: Product category
        products: List of product data dicts

    Returns:
        User prompt for title generation
    """
    product_names = ", ".join(p["name"] for p in products)
    return f"""\
"{category}" 카테고리의 TCO 비교 블로그 제목을 생성해주세요.

비교 제품: {product_names}

## 규칙
- SEO 최적화된 한국어 제목
- 50자 이내
- "3년 비용", "실제 비용", "TCO" 등의 키워드 포함
- 숫자나 연도를 포함하면 클릭률 향상
- 제목만 출력 (부가 설명 없이)

예시 형식: "2026년 {category} 추천 TOP 3 — 3년 실제 비용으로 비교해봤습니다"
"""
