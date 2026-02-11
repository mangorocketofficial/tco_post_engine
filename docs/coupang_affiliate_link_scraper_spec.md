# 쿠팡 파트너스 제휴 링크 자동 스크래퍼 — 구현 명세서

> **목적:** 쿠팡 파트너스 API 없이 대시보드 UI 자동화로 제휴 마케팅 URL을 추출하는 로직의 완전한 구현 가이드.
> 이 문서를 보고 다른 프로젝트에서 동일한 기능을 그대로 재구현할 수 있다.

---

## 1. 핵심 개요

### 왜 스크래퍼인가

쿠팡 파트너스는 제휴 링크 생성 API를 제공하지만 **승인까지 시간이 걸린다**. 승인 전에도 대시보드(`partners.coupang.com`)에서 수동으로 링크를 만들 수 있으므로, 이 UI 조작을 Playwright로 자동화한다.

### 전체 흐름 (한 문장)

```
제품명 리스트 → Playwright로 쿠팡 파트너스 대시보드 로그인 → 제품 검색 → "링크 생성" 클릭 → 생성된 link.coupang.com URL 추출 → JSON 저장
```

### 입출력

| | 형식 | 예시 |
|---|---|---|
| **입력** | A0 제품 선정 JSON | `a0_selected_로봇청소기.json` (`final_products[]` 배열) |
| **출력** | CTA 링크 JSON | `cta_links_로봇청소기.json` (제품당 `base_url` 포함) |

---

## 2. 기술 스택 & 환경

### 필수 의존성

```
playwright          # 브라우저 자동화
python-dotenv       # .env 환경변수 로드
```

### 설치

```bash
pip install playwright python-dotenv
python -m playwright install chromium
```

### 환경변수 (.env)

```env
# 쿠팡 파트너스 대시보드 로그인 정보
COUPANG_ID=your-email@example.com
COUPANG_PASSWORD=your-password
```

---

## 3. 아키텍처 결정 — 왜 이렇게 만들었는가

### 3-1. 실제 Chrome 사용 (channel="chrome")

```python
self._context = await self._playwright.chromium.launch_persistent_context(
    user_data_dir=user_data_dir,
    channel="chrome",          # <-- Playwright 번들 Chromium이 아닌 시스템 Chrome
    headless=self.headless,
    ...
)
```

**이유:** 쿠팡은 **Akamai CDN 봇 탐지**를 사용한다. Playwright 기본 Chromium은 봇으로 탐지되어 차단(`errors.edgesuite.net` 리다이렉트)된다. 실제 시스템 Chrome(`channel="chrome"`)은 정상적인 브라우저 핑거프린트를 가지고 있어 탐지를 회피한다.

### 3-2. Persistent Context (영구 프로필)

```python
PROFILE_DIR = Path("data/.browser_profile/coupang_partners")

self._context = await self._playwright.chromium.launch_persistent_context(
    user_data_dir=str(PROFILE_DIR.resolve()),
    ...
)
```

**이유:**
- 쿠팡 파트너스 로그인 세션(쿠키, localStorage)이 프로필에 저장된다
- **최초 1회만** 수동 로그인하면, 이후 실행 시 자동으로 로그인된 상태로 시작
- 프로필 디렉토리: `data/.browser_profile/coupang_partners/`

### 3-3. 봇 탐지 우회 설정

```python
args=[
    "--disable-blink-features=AutomationControlled",  # navigator.webdriver 플래그 제거
    "--disable-session-crashed-bubble",                # "복원하시겠습니까?" 팝업 억제
    "--hide-crash-restore-bubble",
],
slow_mo=300,           # 사람처럼 천천히 동작
permissions=["clipboard-read", "clipboard-write"],  # URL 복사용 클립보드 권한
viewport={"width": 1280, "height": 900},            # 일반적인 화면 크기
```

---

## 4. 인증(로그인) 로직

### 4-1. 전략

로그인 페이지로 직접 가지 않고, **목표 페이지(링크 생성 페이지)로 바로 이동**한다.
- 이미 로그인됨 → 바로 링크 생성 가능
- 미로그인 → 쿠팡이 자동으로 로그인 페이지로 리다이렉트

### 4-2. 흐름

```
1. partners.coupang.com/#affiliate/ws/link 이동
2. 5초 대기 (SPA 로딩)
3. _is_logged_in() 체크
   ├─ True → 바로 진행
   └─ False → 로그인 시도
       ├─ 자동 로그인: input[type="email"] 찾기 → ID/PW 입력 → 로그인 버튼 클릭
       │   ├─ 성공 → 진행
       │   └─ 실패 → 수동 로그인 대기 (120초)
       └─ 120초 초과 → RuntimeError
```

### 4-3. 로그인 상태 판별 (_is_logged_in)

```python
async def _is_logged_in(self) -> bool:
    # 1단계: URL에 "login" 포함 → 미로그인
    # 2단계: errors.edgesuite.net → 봇 차단됨 (미로그인)
    # 3단계: 대시보드 고유 텍스트 검색 ("링크 생성", "내 실적", "로그아웃")
    #         하나라도 있으면 → 로그인 확인
    # 4단계: URL에 "#affiliate" + 대시보드 CSS 클래스 존재 확인
```

**핵심:** 쿠팡 파트너스는 **SPA(Single Page Application)** 이므로 URL만으로 판별이 어렵다. DOM 내 대시보드 고유 텍스트("링크 생성", "내 실적", "로그아웃")를 직접 확인해야 한다.

### 4-4. 자동 로그인 — 셀렉터

```python
# 이메일 입력 (여러 사이트 호환용 다중 셀렉터)
email_input = page.locator(
    'input[type="email"], input[name="email"], '
    'input[placeholder*="이메일"], input[placeholder*="아이디"], '
    'input[type="text"][name*="id"], input[type="text"][name*="login"]'
).first

# 비밀번호 입력
pw_input = page.locator(
    'input[type="password"], input[name="password"]'
).first

# 로그인 버튼
login_btn = page.locator(
    'button[type="submit"], button:has-text("로그인"), '
    'input[type="submit"], a:has-text("로그인")'
).first
```

---

## 5. 링크 생성 — 핵심 로직

### 5-0. 전체 시퀀스 (제품 1개당)

```
navigate_to_link_page()  →  링크 생성 페이지 이동
         ↓
_scroll_down_by(300, 2)  →  검색 영역으로 스크롤
         ↓
_execute_search(제품명)   →  검색창 입력 + 검색 실행 (4단계 전략)
         ↓
_scroll_down_by(400, 2)  →  검색 결과 영역으로 스크롤
         ↓
_select_product_and_generate()  →  첫 번째 상품 선택 + "링크 생성" 클릭
         ↓
_try_extract_after_linkgen()    →  생성된 URL 추출 (3단계 전략)
         ↓
return "https://link.coupang.com/a/xxxxx"
```

### 5-1. 검색 실행 (_execute_search) — 4단계 전략

쿠팡 파트너스 검색은 일반적인 `<form>` submit이 아닌 **Ant Design SPA 컴포넌트**를 사용하므로, 단순 Enter로 작동하지 않는 경우가 많다. 4가지 전략을 순차 시도한다.

```
전략 1: JS로 인접 버튼 클릭
   → input 요소의 부모/형제에서 <button> 탐색 → click()
   → 쿠팡 파트너스 검색창 옆의 파란색 돋보기 버튼

전략 2: 키보드 Enter
   → input.focus() → page.keyboard.press("Enter")
   → 네이티브 키보드 이벤트

전략 3: JS Enter 이벤트 디스패치
   → keydown/keypress/keyup 이벤트 수동 발생
   → React/Ant Design이 keydown만 리스닝할 수 있으므로 3개 모두 발생
   → form.submit()도 병행 시도

전략 4: 페이지 내 모든 버튼 클릭 시도
   → button:has(svg), button:has(i), [role="button"] 등
   → y좌표 300 이상 (네비게이션 바 아래, 검색 영역)인 버튼만 대상
```

**검색 성공 판별:** 페이지에 `"검색결과"` 텍스트가 나타나면 성공.

```python
async def _has_search_results(self) -> bool:
    result_text = page.locator(':text("검색결과")')
    return await result_text.count() > 0
```

### 5-1-A. 검색 전 모달 처리

검색 전에 인증 모달이나 알림 팝업이 뜰 수 있다. 검색 실행 전에 먼저 닫는다.

```python
modal = page.locator('.ant-modal-wrap, [class*="modal"]')
if await modal.count() > 0:
    close_btn = page.locator(
        '.ant-modal button:has-text("취소"), '
        '.ant-modal .ant-modal-close, '
        '[class*="modal"] button:has-text("취소")'
    ).first
    try:
        await close_btn.click(timeout=3000)
    except Exception:
        await page.keyboard.press("Escape")
```

### 5-2. 상품 선택 & "링크 생성" 버튼 클릭

#### DOM 구조 (쿠팡 파트너스 검색 결과)

```
DIV.product-list
  DIV.product-row
    DIV.product-item          ← 각 상품 카드
      [hover 시 노출되는 버튼 2개]
        Button[0]: "상품보기"  ← 쿠팡 상품 페이지 열기 (클릭하면 안 됨!)
        Button[1]: "링크 생성" ← 제휴 링크 생성 (이것을 클릭)
```

#### 버튼 선택 전략 (3단계)

```python
# 전략 1: 텍스트로 찾기 — "링크" 포함 버튼
linkgen_btn = first_item.locator('button:has-text("링크")').first

# 전략 2: 인덱스로 찾기 — 두 번째 버튼 (index 1)
linkgen_btn = first_item.locator('button').nth(1)

# 전략 3: 소거법 — "상품"/"보기" 텍스트가 아닌 버튼
for btn in buttons:
    text = await btn.text_content()
    if "상품" not in text and "보기" not in text:
        linkgen_btn = btn
```

#### 중요: hover로 숨겨진 버튼 노출

```python
# 상품 카드에 hover해야 버튼이 나타남
await first_item.hover()
await page.wait_for_timeout(1000)  # 애니메이션 완료 대기
```

#### 클릭 실패 시 JS 폴백

```python
# Playwright click 실패 시 — 오버레이 등으로 클릭 차단될 수 있음
await page.evaluate("""() => {
    const item = document.querySelector('.product-item');
    const buttons = item.querySelectorAll('button');
    const btn = buttons[buttons.length - 1];  // 마지막 버튼 = "링크 생성"
    if (btn) {
        btn.style.display = 'inline-block';
        btn.style.visibility = 'visible';
        btn.style.opacity = '1';
        btn.click();
    }
}""")
```

### 5-3. 인증 모달 처리 (_handle_auth_modal)

"링크 생성" 클릭 후 **비밀번호 재인증 모달**이 뜰 수 있다 (세션 타임아웃).

```
[인증 실패 모달]
┌─────────────────────────┐
│  비밀번호를 입력해주세요  │
│  [__________________]   │
│       [취소] [확인]     │
└─────────────────────────┘
```

```python
# 모달 감지
modal = page.locator('.ant-modal-wrap.auth-modal, [class*="auth-modal"]')

# 비밀번호 입력
pw_input = page.locator('.ant-modal input[type="password"]').first
await pw_input.fill(self.coupang_pw)

# 확인 버튼 클릭
confirm_btn = page.locator('.ant-modal button:has-text("확인")').first
await confirm_btn.click()
```

### 5-4. URL 추출 (_try_extract_after_linkgen) — 3단계 전략

"링크 생성" 성공 후 페이지에 **단축 URL**이 표시된다. 추출 전략:

```
전략 1: "URL 복사" 버튼 클릭 → 클립보드에서 읽기
   button:has-text("URL 복사") → click → navigator.clipboard.readText()

전략 2: 페이지 HTML에서 regex로 직접 추출 (가장 안정적)
   regex: https://link\.coupang\.com/[^\s"'<>]+

전략 3: input/textarea 필드 값 읽기
   input[readonly], input[value*="link.coupang"], input.ant-input 등
```

**가장 안정적인 방법은 전략 2 (regex)**이다. 페이지 HTML 전체에서 `link.coupang.com` URL을 정규식으로 추출한다.

```python
html = await page.content()
matches = re.findall(r'https://link\.coupang\.com/[^\s"\'<>]+', html)
if matches:
    return matches[0].strip()
```

---

## 6. 배치 처리

### process_products — 제품 리스트 순회

```python
async def process_products(self, products: list[dict]) -> list[dict]:
    results = []
    for i, product in enumerate(products):
        name = product["name"]
        brand = product.get("brand", "")

        url = await self.generate_link(name)           # 위 5번 전체 흐름
        product_id = _make_product_id(name, brand)     # 슬러그 생성

        results.append({
            "product_id": product_id,
            "product_name": name,
            "brand": brand,
            "base_url": url or "",
            "platform": "coupang",
            "success": url is not None,
        })

        if i < len(products) - 1:
            await self._page.wait_for_timeout(2000)    # 제품 간 2초 딜레이
    return results
```

### product_id 생성 규칙

```python
def _make_product_id(name: str, brand: str) -> str:
    brand_slug = brand.strip().lower().replace(" ", "-")
    words = [w for w in name.split() if len(w) > 1][:3]  # 이름에서 2글자 이상 단어 3개
    name_slug = "-".join(words).lower()
    return f"{brand_slug}_{name_slug}"  # 예: "로보락_로보락-s9-maxv"
```

---

## 7. 출력 JSON 포맷

### 전체 구조

```json
{
  "category": "로봇청소기",
  "generated_at": "2026-02-10T14:09:18.377341",
  "source": "coupang_partners_scraper",
  "products": [
    {
      "product_id": "로보락_로보락-s9-maxv",
      "product_name": "로보락 S9 MaxV Ultra (S90VER+EWFD32HRR) 화이트, 단품",
      "brand": "로보락",
      "base_url": "https://link.coupang.com/a/dJIx2H",
      "platform": "coupang",
      "success": true
    },
    {
      "product_id": "다이슨_다이슨-스팟앤스크럽-ai",
      "product_name": "다이슨 스팟앤스크럽 Ai 로봇 청소기",
      "brand": "다이슨",
      "base_url": "https://link.coupang.com/a/dJIy7g",
      "platform": "coupang",
      "success": true
    }
  ],
  "cta_manager_links": {
    "links": [
      {
        "product_id": "로보락_로보락-s9-maxv",
        "base_url": "https://link.coupang.com/a/dJIx2H",
        "platform": "coupang",
        "affiliate_tag": ""
      }
    ]
  }
}
```

### 필드 설명

| 필드 | 설명 |
|------|------|
| `products[]` | 전체 결과 (성공/실패 모두 포함) |
| `products[].success` | 링크 생성 성공 여부 |
| `products[].base_url` | 생성된 제휴 URL. 실패 시 빈 문자열 `""` |
| `cta_manager_links.links[]` | `success: true`인 제품만 포함. 다운스트림(블로그 CTA) 삽입용 |

---

## 8. CLI 인터페이스

```bash
python -m src.part_b.cta_manager.link_scraper \
    --a0-data data/processed/a0_selected_{CATEGORY}.json \
    --output data/processed/cta_links_{CATEGORY}.json \
    [--headless]
```

| 옵션 | 필수 | 설명 |
|------|------|------|
| `--a0-data` | O | A0 제품 선정 결과 JSON 경로 |
| `--output` | O | 출력 CTA 링크 JSON 경로 |
| `--headless` | X | headless 모드 실행 (세션 저장 후 2회차부터 가능) |

### 입력 JSON 구조 (A0 output)

```json
{
  "category": "로봇청소기",
  "final_products": [
    {"rank": 1, "name": "로보락 S9 MaxV Ultra ...", "brand": "로보락", "price": 1290000},
    {"rank": 2, "name": "다이슨 스팟앤스크럽 Ai ...", "brand": "다이슨", "price": 1490000},
    {"rank": 3, "name": "드리미 X50s Pro Ultra ...", "brand": "드리미", "price": 899000}
  ]
}
```

핵심 필드: `final_products[].name` (검색어), `final_products[].brand` (product_id 생성용)

---

## 9. 다운스트림 연동 — CTAManager

스크래퍼가 생성한 JSON은 **CTAManager**가 소비한다.

### CTAManager 로드

```python
from src.part_b.cta_manager.manager import CTAManager

# cta_links JSON에서 cta_manager_links 부분을 추출하여 로드
manager = CTAManager(links_path=Path("cta_links_로봇청소기.json"))
```

또는 직접 등록:

```python
manager = CTAManager()
manager.register_link("로보락_로보락-s9-maxv", "https://link.coupang.com/a/dJIx2H")
```

### UTM 추적 URL 생성

```python
url = manager.build_tracked_url(
    product_id="로보락_로보락-s9-maxv",
    section=CTASection.QUICK_PICK,       # section_2
    campaign="robot_vacuum_2026",
)
# 결과: https://link.coupang.com/a/dJIx2H?utm_source=tco_blog&utm_medium=affiliate&utm_campaign=robot_vacuum_2026&utm_content=section_2_cta
```

### CTA 배치 규칙

블로그 포스트에서 CTA 버튼이 들어가는 위치 (제품당 정확히 1개씩):

| 섹션 | CTASection enum | 목적 |
|------|-----------------|------|
| Section 2: 추천 요약표 | `QUICK_PICK` | 1차 전환 포인트 |
| Section 3: TCO 심층 분석 | `DEEP_DIVE` | 상세 분석 후 전환 |
| Section 4: 체크리스트 | `CHECKLIST` | 최종 결정 후 전환 |

---

## 10. 생성되는 URL 형태

| 단계 | URL 예시 |
|------|----------|
| 쿠팡 대시보드에서 추출 | `https://link.coupang.com/a/dJIx2H` |
| CTAManager UTM 추가 후 | `https://link.coupang.com/a/dJIx2H?utm_source=tco_blog&utm_medium=affiliate&utm_campaign=robot_vacuum_2026&utm_content=section_2_cta` |
| affiliate_tag 있을 때 | `https://link.coupang.com/re/AFFSDP?lptag=AF1234567&tag=mangorocket&utm_source=tco_blog&...` |

---

## 11. 타임아웃 & 딜레이 상수

```python
NAV_TIMEOUT = 60_000      # 페이지 이동 타임아웃 (60초)
ACTION_TIMEOUT = 15_000   # 개별 요소 조작 타임아웃 (15초)
SETTLE_DELAY = 2_000      # 제품 간 딜레이 (2초)
slow_mo = 300             # Playwright 전역 딜레이 (300ms)
```

---

## 12. 디버깅 & 트러블슈팅

### 스크린샷 자동 저장

모든 주요 단계에서 스크린샷을 `data/debug_screenshots/`에 저장한다:

| 스크린샷 라벨 | 시점 |
|---|---|
| `initial_page` | 최초 페이지 로드 |
| `after_search` | 검색 실행 후 |
| `search_results` | 검색 결과 스크롤 후 |
| `after_hover` | 상품 카드 hover 후 (버튼 노출) |
| `after_linkgen_click` | "링크 생성" 버튼 클릭 후 |
| `after_linkgen_check` | URL 추출 시도 후 |
| `search_fail` | 검색 실패 시 |
| `no_product_items` | 검색 결과 없을 시 |

### DOM 덤프 (_dump_product_dom)

검색 결과 DOM 구조를 로깅하는 디버그 헬퍼:

```python
dom_info = await self._dump_product_dom()
# product_cards[]: class, children, text, has_button 등
# buttons[]: text, class, visible, y좌표
# links[]: "링크" 관련 텍스트
```

### 흔한 문제와 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| `TargetClosedError` | Chrome 프로필 잠금 (이전 Chrome 미종료) | `taskkill /F /IM chrome.exe` 후 재실행 |
| `errors.edgesuite.net` 리다이렉트 | Akamai 봇 탐지 (번들 Chromium 사용) | `channel="chrome"` 확인 (실제 Chrome 필수) |
| "인증 실패" 모달 반복 | 세션 만료 또는 비밀번호 변경 | `.env`의 `COUPANG_PASSWORD` 확인 |
| 검색 결과 0건 | 제품명이 너무 길거나 특수문자 포함 | 브랜드+핵심모델명으로 축약 |
| "상품보기" 탭이 열림 | 첫 번째 버튼(상품보기) 클릭됨 | `button:has-text("링크")` 또는 index 1 사용 확인 |
| 클립보드 권한 팝업 | Chrome 권한 미설정 | `permissions=["clipboard-read", "clipboard-write"]` |
| Stale tab 누적 | 이전 시도에서 열린 탭 미정리 | 링크 생성 전 `context.pages[1:]` 닫기 |

### 최초 실행 가이드

1. `.env`에 `COUPANG_ID`, `COUPANG_PASSWORD` 설정
2. **headful 모드**로 실행: `--headless` 플래그 없이 실행
3. 브라우저 창이 열리면 쿠팡 파트너스에 **수동 로그인** (최초 1회)
4. 로그인 성공 → 세션이 `data/.browser_profile/coupang_partners/`에 저장
5. 이후 실행부터는 자동 로그인 (headless 가능)

---

## 13. 다른 프로젝트에서 재구현 시 체크리스트

### 필수 구현 항목

- [ ] Persistent Chrome context (`channel="chrome"` + `user_data_dir`)
- [ ] `--disable-blink-features=AutomationControlled` arg
- [ ] 로그인 상태 판별: DOM 텍스트 기반 (URL만으로 불충분 — SPA)
- [ ] 검색 실행: 최소 2개 이상 전략 (JS 버튼 클릭 + 키보드 Enter)
- [ ] "검색결과" 텍스트로 성공 판별
- [ ] `.product-item` hover → 숨겨진 버튼 노출
- [ ] "링크 생성" 버튼 = 두 번째 버튼 (첫 번째는 "상품보기")
- [ ] 인증 모달 자동 처리 (비밀번호 재입력)
- [ ] URL 추출: regex가 가장 안정적 (`link\.coupang\.com` 패턴)
- [ ] 스크린샷 저장 (디버깅 필수)

### 커스터마이징 포인트

| 항목 | 현재 값 | 조정 시 |
|------|---------|---------|
| 쿠팡 파트너스 URL | `partners.coupang.com/#affiliate/ws/link` | 다른 제휴 플랫폼이면 URL 변경 |
| 검색어 | A0 제품명 전체 | 너무 길면 브랜드+모델명으로 축약 |
| 상품 선택 | 첫 번째 `.product-item` | 정확도 높이려면 이름 매칭 로직 추가 |
| 프로필 디렉토리 | `data/.browser_profile/coupang_partners/` | 프로젝트별 격리 필요 시 변경 |
| slow_mo | 300ms | 봇 탐지 강화 시 500~1000ms로 증가 |
| 딜레이 | 제품 간 2초 | Rate limiting 시 증가 |

### 코드 구조 (재구현 시 파일 구성)

```
cta_manager/
├── link_scraper.py      # CoupangLinkScraper 클래스 + CLI
├── manager.py           # CTAManager — 링크 관리 + UTM 추적
├── models.py            # AffiliateLink, CTAEntry, UTMParams 등
└── __init__.py
```

---

## 14. 향후 계획

- **쿠팡 파트너스 API 승인 후:** 스크래퍼를 API 호출로 대체. `CTAManager.load_links()` 인터페이스는 동일하게 유지하여 다운스트림 코드 변경 없이 전환.
- **affiliate_tag 관리:** 현재 스크래퍼는 `affiliate_tag: ""` (쿠팡이 URL 자체에 내장). API 전환 시 명시적 태그 관리 추가.

---

*문서 버전: 1.0*
*기준 코드: `src/part_b/cta_manager/link_scraper.py` (974 lines)*
*최종 업데이트: 2026-02-10*
