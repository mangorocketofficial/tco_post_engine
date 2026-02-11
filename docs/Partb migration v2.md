# Part B 업데이트 요청서: 7→6 섹션 마이그레이션 + 생성 방식 전환

> **성격:** 1회성 시스템 변경 요청. RUNBOOK(반복 실행 절차)과 분리된 아키텍처 변경 문서.
> **적용 대상:** `src/part_b/` 전체, 블로그 생성 파이프라인
> **요청일:** 2026-02-09

---

## 1. 변경 배경

### 1-1. 7→6 섹션 구조 변경 근거

가습기 카테고리 파일럿 결과, 기존 7섹션 구조에서 3가지 문제를 확인했다:

| 문제 | 해당 섹션 | 증상 |
|------|----------|------|
| Section 0 ↔ Section 3 메시지 중복 | 둘 다 "상황별 추천" | 같은 말을 두 번 읽는 느낌 |
| Section 1 (신뢰성)이 읽기 흐름을 끊음 | 결론 → 신뢰성 → 기준 | 결론 직후 "왜?"를 알고 싶은데 자기PR이 끼어듦 |
| Section 5 (행동유도) 데이터 근거 없음 | "가격 변동성" 언급 | A1(다나와) 제거로 가격 추이 데이터 미수집 |

### 1-2. 생성 방식 전환 근거

| 현재 | 변경 | 사유 |
|------|------|------|
| GPT API 호출 → Python ContentWriter → Jinja2 렌더링 → Markdown | Claude Code 직접 생성 → HTML | 외부 API 의존성 제거. Claude Code 세션에서 TCO JSON을 읽고 바로 HTML 생성이 더 빠르고 유연함 |
| Jinja2 템플릿 7개 (`section_0_hook` ~ `section_6_faq`) | 섹션 구조를 RUNBOOK에 명세, Claude Code가 직접 해석 | 템플릿 유지보수 비용 제거. 카테고리별 유연한 서술 가능 |
| Markdown 출력 → 별도 HTML 변환 | HTML 단일 파일 직접 출력 | 브라우저에서 바로 확인. 네이버/티스토리 붙여넣기 호환 |

---

## 2. 섹션 매핑: 7 Sections → 6 Sections

### 2-1. Before / After 매핑

| v3.1 (7 Sections) | v3.2 (6 Sections) | 변경 내용 |
|---|---|---|
| **Section 0:** 결론 먼저 | **Section 0:** 결론 먼저 **+ 신뢰 1줄** | Section 1 흡수 |
| **Section 1:** 신뢰성 확보 | *(삭제)* | Section 0 하단 1줄로 통합 |
| **Section 2:** 기준 3가지 (2-1, 2-2, 2-3) | **Section 1:** 기준 3가지 (1-1, 1-2, 1-3) | 번호만 변경 |
| **Section 3:** 추천 요약표 + CTA | **Section 2:** 추천 요약표 + CTA | Section 1 직후 배치로 전환 동선 단축 |
| **Section 4:** TCO 심층 분석 (4-1~4-5) | **Section 3:** TCO 심층 분석 (3-1~3-5) | 번호 변경 + 3-5 정성 비교표 형식 변경 |
| **Section 5:** 행동 유도 (가격 변동성 + CTA) | **Section 4:** 구매 전 체크리스트 + CTA | 완전 교체 |
| **Section 6:** FAQ | **Section 5:** FAQ | 번호 변경 + FAQ 소스 확대 |

### 2-2. 상세 변경 사항

#### Section 1 (신뢰성) → Section 0에 1줄 통합

**Before (독립 섹션):**
```
## 분석 데이터
이 글은 국내 주요 커뮤니티 리뷰 142건을 자체 분석한...
- 커뮤니티 리뷰 데이터: 142건
- 중고 실거래 데이터: 6건
- 수리/AS 후기: 12건
```

**After (Section 0 마지막 1줄):**
```
국내 주요 커뮤니티 리뷰 142건과 중고 시세를 자체 분석한 결과입니다.
```

#### Section 5 (행동유도) → Section 4 (체크리스트) 완전 교체

**Before:**
```
## 지금 확인해야 하는 이유
가습기 가격은 시즌/이벤트에 따라 급변합니다.
지금 당장 구매하지 않더라도, 현재 조건을 확인해두면...
```
- 문제: 가격 추이 데이터 없음 (A1 제거됨). 근거 없는 urgency.

**After:**
```
## 구매 전 체크리스트: 나에게 맞는 가습기는?
🏠 사용 공간
- 아기방 고정 배치 → 조지루시 또는 스텐팟
- 방 간 이동 필요 → 케어미스트
👶 가족 구성
- 기어다니는 영유아 → 케어미스트 (화상 위험 없음)
...
```
- `environment_splits` 데이터 기반. 독자 자가 진단 → 제품 매칭 → CTA.

#### Section 4-5 정성 비교표 형식 변경

**Before (automation_rate %):**
```
| 유지관리 자동화율 | 29% | 14% | 29% |
```
- 문제: "29%"가 독자에게 와닿지 않음.

**After (구체적 작업명):**
```
| 매일 할 일 | 물 교체 | 물 교체 | 물 교체 |
| 주 1회 할 일 | 물통 청소, 소독 | 물통 청소, 필터 세척, 소독 | 물통 청소, 소독 |
| 안 해도 되는 일 | 진동자·필터 (해당 없음) | 진동자 (해당 없음) | 진동자·필터 (해당 없음) |
```

---

## 3. 생성 방식 변경

### 3-1. 제거 대상 (더 이상 사용하지 않는 것)

| 제거 대상 | 파일 위치 | 사유 |
|----------|----------|------|
| GPT/Anthropic API 호출 로직 | `src/part_b/content_writer/writer.py` | Claude Code가 직접 생성 |
| Jinja2 템플릿 7개 | `src/part_b/template_engine/templates/section_*.jinja2` | 6섹션 구조를 RUNBOOK이 정의, Claude Code가 해석 |
| `blog_post.jinja2` 마스터 템플릿 | `src/part_b/template_engine/templates/` | HTML 직접 생성으로 대체 |
| `TemplateRenderer` 클래스 | `src/part_b/template_engine/renderer.py` | 불필요 |
| ContentWriter의 LLM provider 설정 | `src/part_b/content_writer/models.py` (`LLMProvider`) | 외부 LLM 미사용 |
| `build_enrichment_prompt`, `build_title_prompt` | `src/part_b/content_writer/prompts.py` | Claude Code가 RUNBOOK 명세를 직접 읽음 |

### 3-2. 유지 대상 (계속 사용하는 것)

| 유지 대상 | 사유 |
|----------|------|
| `src/part_b/cta_manager/` | CTA 링크/UTM 관리는 여전히 필요 |
| `src/part_b/stats_connector/` | 발행 후 성과 추적에 필요 |
| `src/part_b/publisher/pipeline.py` | 최종 post-processing (SEO 태그, 플랫폼별 포맷) |
| `CTASection` enum | Section 번호 변경 필요 (아래 참조) |

### 3-3. 수정 대상

#### CTA 배치 섹션 번호 변경

`src/part_b/cta_manager/models.py`:

```python
# Before
class CTASection(str, Enum):
    QUICK_PICK = "section_3"   # Section 3: Quick Pick Table
    DEEP_DIVE = "section_4"    # Section 4: TCO Deep Dive
    ACTION = "section_5"       # Section 5: Action Trigger

# After
class CTASection(str, Enum):
    QUICK_PICK = "section_2"   # Section 2: 추천 요약표
    DEEP_DIVE = "section_3"    # Section 3: TCO 심층 분석
    CHECKLIST = "section_4"    # Section 4: 구매 전 체크리스트
```

#### Stats Connector 섹션 매핑

`src/part_b/stats_connector/models.py` — CTA click tracking 섹션 번호:

```python
# Before
section_3_clicks: int = 0  # Quick Pick
section_4_clicks: int = 0  # Deep Dive
section_5_clicks: int = 0  # Action Trigger

# After
section_2_clicks: int = 0  # 추천 요약표
section_3_clicks: int = 0  # TCO 심층 분석
section_4_clicks: int = 0  # 구매 전 체크리스트
```

---

## 4. 출력 형식 변경: Markdown → HTML

### 4-1. Before

```
ContentWriter → Jinja2 렌더링 → Markdown 파일 → PostProcessor → HTML/Markdown 변환 → 플랫폼 발행
```

### 4-2. After

```
Claude Code → RUNBOOK 명세 해석 → HTML 파일 직접 생성 → (optional) PostProcessor → 플랫폼 발행
```

### 4-3. HTML 요구사항

| 항목 | 요구사항 |
|------|---------|
| 인코딩 | `<!DOCTYPE html>` + `<meta charset="UTF-8">` |
| 반응형 | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| CSS | 인라인 스타일 (외부 의존성 없음, 네이버/티스토리 호환) |
| 섹션 구분 | `<section>` 태그 |
| 표 | `<table>` + `overflow-x: auto` wrapper |
| CTA | `<a class="cta-button">` — 눈에 띄는 색상, 충분한 패딩 |
| FAQ | `<details><summary>` 접기/펼치기 |
| 공시문구 | Section 4 하단 또는 `<footer>` |

### 4-4. 파일 경로 변경

```
# Before
data/exports/blog_{CATEGORY}.md

# After
data/exports/blog_{CATEGORY}.html
```

---

## 5. 데이터 모델 영향

### 5-1. `src/part_b/template_engine/models.py` — BlogPostData

7섹션 기준으로 설계된 `BlogPostData` dataclass를 더 이상 사용하지 않는다. Claude Code가 TCO JSON을 직접 읽으므로, Part A의 export 스키마(`tco_{CATEGORY}.json`)가 유일한 입력 포맷이 된다.

**유지:** `src/common/models.py`의 Part A 모델들 (TCOCategoryExport 등)
**사용 중단:** `src/part_b/template_engine/models.py`의 Blog rendering 모델들

### 5-2. TCO JSON → HTML 매핑 (Claude Code가 직접 수행)

| TCO JSON 필드 | HTML 섹션 | 용도 |
|---|---|---|
| `category_insights.decision_forks` | Section 0, 1-3, 2, 4 | 상황별 추천 |
| `category_insights.most_overrated_spec` | Section 1-1 | 미신 깨기 |
| `category_insights.real_differentiator` | Section 1-2 | 진짜 차별점 |
| `products[].tco.*` | Section 0, 2, 3 | 모든 비용 숫자 |
| `products[].repair_stats.*` | Section 3, 5 | 고장 유형/확률/비용 |
| `products[].maintenance.tasks` | Section 3-5 | 체감 비교표 |
| `products[].review_insights.*` | Section 1, 4, 5 | 리뷰 기반 콘텐츠 |
| `credibility.*` | Section 0 | 신뢰 문구 1줄 |

---

## 6. 마이그레이션 체크리스트

### 코드 변경

```
[ ] CTASection enum 섹션 번호 업데이트 (3/4/5 → 2/3/4)
[ ] Stats connector 섹션 매핑 업데이트
[ ] publisher/pipeline.py — 출력 형식 .md → .html 경로 변경
[ ] (선택) template_engine/ 하위 Jinja2 템플릿 아카이브 또는 삭제
[ ] (선택) content_writer/ GPT 호출 로직 아카이브 또는 삭제
```

### 문서 변경

```
[ ] RUNBOOKV3.md → RUNBOOKV3.2.md 교체 (Step B 부분)
[ ] PartB_update.md → 본 문서(PartB_migration_v2.md)로 교체
[ ] CLAUDE.md — "7 section templates" 언급 → "6 sections" 으로 수정
[ ] .prompts/part-b.md — GPT writer 언급 제거, Claude Code 직접 생성으로 수정
```

### 검증

```
[ ] 가습기 TCO JSON → HTML 생성 테스트
[ ] 브라우저 렌더링 확인 (PC + 모바일)
[ ] CTA placeholder 링크 동작 확인
[ ] FAQ <details> 접기/펼치기 동작 확인
[ ] 숫자 검증: HTML 내 모든 금액이 tco_가습기.json과 일치
```

---

## 7. v3.1 → v3.2 변경 요약

| 항목 | v3.1 | v3.2 | 사유 |
|------|------|------|------|
| 블로그 섹션 수 | 7개 (Section 0~6) | 6개 (Section 0~5) | Section 0+1 통합, Section 5→4 교체 |
| Section 1 (신뢰성) | 독립 섹션 (6~8줄) | Section 0에 1줄 통합 | 읽기 흐름 방해 |
| Section 5 (행동유도) | 가격 변동성 + CTA | 구매 전 체크리스트 + CTA | A1 제거로 가격 데이터 없음 |
| 정성 비교표 | automation_rate % | 매일/주1회/안해도됨 | 독자 체감 직관성 |
| 블로그 생성 | GPT API → Jinja2 → Markdown | Claude Code → HTML 직접 | 외부 API 제거, 즉시 생성 |
| 출력 형식 | Markdown | HTML (인라인 CSS) | 브라우저 직접 확인, 블로그 플랫폼 호환 |
| 제품별 상세 | 분량 제한 없음 | 5줄 이내 | Section 3 비대화 방지 |
| FAQ 소스 | repair + review | + environment_splits negative | 다양성 확보 |

---

*문서 버전: 2.0*
*작성일: 2026-02-09*
*적용 대상: RUNBOOK v3.2*