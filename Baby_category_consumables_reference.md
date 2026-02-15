# 육아용품 카테고리별 소모품 & TCO 레퍼런스

> 이 문서는 블로그 자동 생성 시스템에서 육아용품 카테고리별 TCO(총소유비용) 분석 여부와 소모품 정보를 빠르게 조회하기 위한 레퍼런스입니다.
> 전자기기 레퍼런스(`category_consumables_reference.md`) 및 반려동물 레퍼런스(`Pet_category_consumables_reference.md`)와 동일한 구조를 따릅니다.

---

## 1. 사용법

- `tco_tier`로 해당 카테고리의 TCO 글 작성 필요성을 판단
- `consumable_name`을 활용해 "N년 {consumable_name} 포함 총비용" 형태로 TCO 표기
- `tco_formula`를 기반으로 비용 산출 구조 설정
- `tco_tier: none`인 카테고리는 TCO 프레이밍 없이 구매가+성능+AS 비교로 글 작성
- **육아용품 특이사항**: 사용 기간이 짧은 제품(분유제조기, 기저귀처리기 등)이 많아 `usage_period` 필드로 실사용 기간 표기. 일부 카테고리는 전용 소모품 락인 구조(`lock_in: true`)

---

## 2. TCO 등급 정의

| tier | 의미 | 글 전략 |
|------|------|---------|
| `essential` | 소모품비가 구매가 대비 50%+ 또는 연 5만원+ | **TCO 비교 필수**. "N년 {소모품} 포함 총비용" 프레이밍 |
| `recommended` | 소모품비가 의미 있는 수준 (연 2~5만원) | **TCO 비교 권장**. 소모품비를 부가 비교 항목으로 |
| `optional` | 소모품비 소액 또는 일부 모델만 해당 | TCO 선택적. 해당되는 경우만 언급 |
| `none` | 소모품 없음 | TCO 프레이밍 불필요. 구매가+성능+AS 중심 |

> **전자기기·반려동물 대비 차이점**: 육아용품은 사용 기간이 짧아(6개월~2년) "총비용" 개념이 기기 수명보다 **아이 성장 기간**에 맞춰짐. `essential` 기준은 연 5만원+ 또는 구매가 대비 50%+로 설정.

---

## 3. 카테고리 데이터

```json
[
  {
    "category": "기저귀처리기",
    "group": "위생·배변",
    "tco_tier": "essential",
    "consumables": [
      {"name": "전용 리필 봉투/카트리지", "cycle": "2~4주", "annual_cost_krw": "60000~150000"}
    ],
    "consumable_name": "리필",
    "annual_cost_range": "60000~150000",
    "tco_label": "N년 리필 포함 총비용",
    "tco_formula": "구매가 + (리필단가 × 교체횟수) × N년",
    "lock_in": true,
    "usage_period": "0~30개월(기저귀 졸업까지)",
    "notes": "매직캔, 이지캔 등 전용 리필 강제. 본체 2~5만원 대비 리필 연 6~15만원으로 대표적 역전 구조. 호환 리필 사용 시 30~50% 절감 가능하나 냄새차단력 차이. 신생아기 교체 빈도 가장 높음(일 8~12회 기저귀)"
  },
  {
    "category": "분유제조기",
    "group": "수유·이유",
    "tco_tier": "essential",
    "consumables": [
      {"name": "깔때기/노즐 세트(여분)", "cycle": "3~6개월", "annual_cost_krw": "10000~30000"},
      {"name": "정수필터(일부 모델)", "cycle": "2~3개월", "annual_cost_krw": "20000~50000"},
      {"name": "세척솔/세정제", "cycle": "1~2개월", "annual_cost_krw": "10000~20000"}
    ],
    "consumable_name": "필터+부품",
    "annual_cost_range": "40000~100000",
    "tco_label": "N년 필터·부품 포함 총비용",
    "tco_formula": "구매가 + (필터비 + 부품비 + 세정비) × N년",
    "lock_in": true,
    "usage_period": "0~12개월(분유 수유 기간)",
    "notes": "베이비브레짜, 브라비, 눈누, 버들맘마 등. 본체 15~35만원. 깔때기·노즐은 브랜드별 전용 부품(1~3만원). 정수필터 탑재 모델은 필터 교체 추가. 분유 세팅 번호·호환 분유 수 비교 포인트. 실사용 기간 6~12개월로 짧아 TCO 임팩트 상대적으로 큼"
  },
  {
    "category": "젖병소독기",
    "group": "수유·이유",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "UV램프(램프형만)", "cycle": "6~12개월", "annual_cost_krw": "7000~15000"},
      {"name": "HEPA필터(일부 모델)", "cycle": "6~12개월", "annual_cost_krw": "10000~20000"}
    ],
    "consumable_name": "램프",
    "annual_cost_range": "7000~35000",
    "tco_label": "N년 램프 포함 총비용",
    "tco_formula": "구매가 + (램프비 + 필터비) × N년",
    "lock_in": false,
    "usage_period": "0~24개월+",
    "notes": "UV램프형(유팡, 레이퀸, 스펙트라): 6개월마다 램프 교체 권장, 개당 3,500~8,000원. UV LED형: 반영구 교체 불필요하나 본체가 비쌈(20만원 후반~30만원). 램프형이 LED형 대비 저렴하지만 유지비 발생. 건조방식(열풍/자연)도 비교 포인트"
  },
  {
    "category": "콧물흡입기",
    "group": "건강·위생",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "실리콘 노즐팁", "cycle": "2~3개월", "annual_cost_krw": "10000~25000"},
      {"name": "필터(일부 모델)", "cycle": "1~2개월", "annual_cost_krw": "5000~15000"}
    ],
    "consumable_name": "노즐",
    "annual_cost_range": "15000~40000",
    "tco_label": "N년 노즐 포함 총비용",
    "tco_formula": "구매가 + (노즐팁 + 필터) × N년",
    "lock_in": true,
    "usage_period": "0~6세",
    "notes": "노시부 프로(유선, 10~13만원), 노시부 고(무선, 7~9만원) 등. 실리콘 팁·석션팁은 브랜드별 전용(개당 3~5천원). 위생상 2~3개월 교체 권장. 형제 사용 시 개인별 팁 필요. 사용 기간이 길어(0~6세) TCO 누적"
  },
  {
    "category": "아기 모니터(베이비캠)",
    "group": "안전·모니터링",
    "tco_tier": "essential",
    "consumables": [
      {"name": "클라우드 저장 구독료", "cycle": "매월", "annual_cost_krw": "0~120000"}
    ],
    "consumable_name": "구독료",
    "annual_cost_range": "0~120000",
    "tco_label": "N년 구독료 포함 총비용",
    "tco_formula": "구매가 + 클라우드 구독료 × N년",
    "lock_in": true,
    "usage_period": "0~4세",
    "notes": "오웰, 큐캠 등 전용 앱 연동형은 클라우드 저장 구독(월 5천~1만원). 실시간 스트리밍은 무료이나 녹화·AI 알림 등 프리미엄 기능은 구독 필요. 와이파이 없는 DECT 방식(안데스 등)은 구독 없음. 구독형 vs 비구독형 TCO 비교가 핵심 콘텐츠"
  },
  {
    "category": "이유식제조기",
    "group": "수유·이유",
    "tco_tier": "optional",
    "consumables": [
      {"name": "칼날(마모 교체)", "cycle": "6~12개월", "annual_cost_krw": "10000~20000"},
      {"name": "실리콘 패킹", "cycle": "6~12개월", "annual_cost_krw": "5000~10000"}
    ],
    "consumable_name": "칼날",
    "annual_cost_range": "10000~30000",
    "tco_label": "N년 칼날 포함 총비용",
    "tco_formula": "구매가 + (칼날 + 패킹) × N년",
    "lock_in": false,
    "usage_period": "6~18개월",
    "notes": "베이비무브, 베아바 등. 본체 10~30만원. 칼날 마모 시 교체(1~2만원). 스팀+블렌딩 일체형 vs 단순 블렌더형. 사용 기간 6~12개월로 매우 짧아 TCO보다 구매가 자체가 비교 핵심"
  },
  {
    "category": "유아 전동칫솔",
    "group": "건강·위생",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "교체 브러시헤드", "cycle": "2~3개월", "annual_cost_krw": "20000~40000"}
    ],
    "consumable_name": "브러시",
    "annual_cost_range": "20000~40000",
    "tco_label": "N년 브러시 포함 총비용",
    "tco_formula": "구매가 + (브러시헤드 × 교체횟수) × N년",
    "lock_in": true,
    "usage_period": "2~12세",
    "notes": "필립스 소닉케어 키즈, 오랄비 키즈 등. 본체 3~7만원. 교체 브러시 2~3개월 주기(개당 5천~1만원). 호환 브러시 유통 여부가 TCO 핵심. 성인용 대비 브러시 단가 유사하나 본체가 저렴해 비율상 높음"
  },
  {
    "category": "유아 가습기",
    "group": "환경·공기질",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "항균필터/카트리지", "cycle": "1~3개월", "annual_cost_krw": "20000~50000"},
      {"name": "세척제(구연산 등)", "cycle": "2~4주", "annual_cost_krw": "5000~10000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "25000~60000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터비 + 세척제) × N년",
    "lock_in": true,
    "usage_period": "0~5세(겨울 시즌 집중)",
    "notes": "유아 전용 모델(오큐러스, 미로, 보나르떼 등)은 항균 카트리지 교체 필수. 자연기화식: 필터 교체(2~5만원/연). 초음파식: 필터 없으나 세균 관리 필수. 아기방 위생 민감도 높아 교체 주기 짧게 운용하는 경향"
  },
  {
    "category": "유아 체온계",
    "group": "건강·위생",
    "tco_tier": "optional",
    "consumables": [
      {"name": "프로브커버(귀적외선형)", "cycle": "사용시마다", "annual_cost_krw": "10000~25000"},
      {"name": "배터리", "cycle": "6~12개월", "annual_cost_krw": "3000~5000"}
    ],
    "consumable_name": "프로브커버",
    "annual_cost_range": "10000~30000",
    "tco_label": "N년 프로브커버 포함 총비용",
    "tco_formula": "구매가 + (프로브커버 + 배터리) × N년",
    "lock_in": true,
    "usage_period": "0~6세+",
    "notes": "브라운 써모스캔: 프로브커버 필수 소모품(200개 1.5~2만원). 비접촉식 체온계는 소모품 없음. 귀적외선 vs 비접촉식 TCO 비교가 콘텐츠 훅. 감기 시즌 사용량 급증"
  },
  {
    "category": "아기띠·힙시트",
    "group": "외출·이동",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "lock_in": false,
    "usage_period": "3~36개월",
    "notes": "소모품 없음. 에르고베이비, 코니, 포그내 등. 구매가+안전인증+편의성 비교 중심. 인서트(신생아패드) 별매이나 1회성 구매"
  },
  {
    "category": "유모차",
    "group": "외출·이동",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "lock_in": false,
    "usage_period": "0~48개월",
    "notes": "소모품 없음. 악세사리(레인커버, 모기장, 컵홀더) 별매이나 소모품 아님. 구매가+안전+접이편의+무게 비교 중심. 디럭스/절충형/휴대형 카테고리 분화"
  },
  {
    "category": "카시트",
    "group": "외출·이동",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "lock_in": false,
    "usage_period": "0~12세(단계별 교체)",
    "notes": "소모품 없음. 신생아용→컨버터블→주니어 단계별 교체가 실질 비용이나 '소모품'이 아닌 '기기 교체'. 안전인증(KC, ECE R44/R129)이 핵심 비교 포인트"
  },
  {
    "category": "바운서·스윙",
    "group": "실내육아",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "lock_in": false,
    "usage_period": "0~12개월",
    "notes": "소모품 없음. 배터리 구동형은 건전지 비용 소액. 베이비뵨, 마마루 등. 사용 기간 매우 짧아 중고거래 활발"
  },
  {
    "category": "전동 유축기",
    "group": "수유·이유",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "깔때기/밸브/멤브레인 세트", "cycle": "1~3개월", "annual_cost_krw": "20000~50000"},
      {"name": "모유저장팩", "cycle": "상시", "annual_cost_krw": "20000~50000"}
    ],
    "consumable_name": "부품+저장팩",
    "annual_cost_range": "40000~100000",
    "tco_label": "N년 부품 포함 총비용",
    "tco_formula": "구매가 + (교체부품 + 저장팩) × N년",
    "lock_in": true,
    "usage_period": "0~12개월(모유수유 기간)",
    "notes": "스펙트라, 메델라, 코코 등. 본체 5~30만원. 깔때기·밸브·멤브레인은 브랜드별 전용 부품(세트 1~2.5만원). 모유저장팩은 범용이나 대량 소모(월 2~5만원). 위생상 1~3개월 교체 권장. 사용 기간 짧아 TCO 밀도 높음"
  },
  {
    "category": "아기 물티슈워머",
    "group": "위생·배변",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "lock_in": false,
    "usage_period": "0~24개월(겨울 시즌)",
    "notes": "소모품 없음. 물티슈 자체는 소모품이나 워머와 무관. 전기료만 유지비. 사용 기간 짧고 제품 단가 낮아(1~3만원) TCO 무의미"
  },
  {
    "category": "유아 공기청정기",
    "group": "환경·공기질",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "HEPA필터", "cycle": "6~12개월", "annual_cost_krw": "15000~40000"},
      {"name": "탈취필터", "cycle": "6~12개월", "annual_cost_krw": "10000~20000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "25000~60000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터세트 × 교체횟수) × N년",
    "lock_in": false,
    "usage_period": "0~6세+",
    "notes": "일반 공기청정기와 구조 동일. 유아 전용 모델(위닉스 베이비, 코웨이 베이비 등)은 저소음·센서 특화. 일반 가전 레퍼런스와 중복 가능 — 아기방 전용 소형 모델만 다룸"
  },
  {
    "category": "아기 침대·범퍼",
    "group": "실내육아",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "lock_in": false,
    "usage_period": "0~24개월",
    "notes": "소모품 없음. 매트리스 커버 별매이나 소모품 아님. 안전인증(KC)·통기성·높이조절이 비교 포인트"
  },
  {
    "category": "유아식기세척기(젖병세척기)",
    "group": "수유·이유",
    "tco_tier": "optional",
    "consumables": [
      {"name": "전용 세제", "cycle": "1~2개월", "annual_cost_krw": "15000~30000"},
      {"name": "필터(일부 모델)", "cycle": "6개월", "annual_cost_krw": "10000~20000"}
    ],
    "consumable_name": "세제",
    "annual_cost_range": "20000~50000",
    "tco_label": "N년 세제 포함 총비용",
    "tco_formula": "구매가 + (세제비 + 필터비) × N년",
    "lock_in": false,
    "usage_period": "0~24개월",
    "notes": "젖병 전용 소형 식기세척기(핌핀, 하이헬스 등). 본체 20~40만원. 전용 세제 권장이나 일반 유아 세제 사용 가능. 일반 식기세척기 대비 소형·저렴"
  },
  {
    "category": "보행기·점퍼루",
    "group": "실내육아",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "lock_in": false,
    "usage_period": "6~15개월",
    "notes": "소모품 없음. 졸리점퍼, 피셔프라이스 등. 사용 기간 매우 짧아(3~6개월) 중고거래율 높음"
  },
  {
    "category": "아기 식탁의자(하이체어)",
    "group": "수유·이유",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "lock_in": false,
    "usage_period": "6~36개월+",
    "notes": "소모품 없음. 트레이·안전벨트는 본체 포함. 스토케 트립트랩, 이케아 안틸로프 등. 성장형 vs 고정형 비교"
  },
  {
    "category": "아기 세탁세제·섬유유연제",
    "group": "위생·배변",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "lock_in": false,
    "usage_period": "0~36개월",
    "notes": "세제 자체가 소비재이지 기기 소모품이 아님. TCO 대상 아님. 성분 안전성·EWG 등급 비교 중심"
  }
]
```

---

## 4. 빠른 조회 테이블

### TCO 필수 (essential) — 3개
| 카테고리 | 소모품명 | 연간비용 | TCO 표기 | 특징 |
|----------|----------|----------|----------|------|
| 기저귀처리기 | 리필 | 6~15만원 | N년 리필 포함 총비용 | 🔥 역전 구조 대표 |
| 분유제조기 | 필터+부품 | 4~10만원 | N년 필터·부품 포함 총비용 | 💡 전용 부품 락인 |
| 아기 모니터(베이비캠) | 구독료 | 0~12만원 | N년 구독료 포함 총비용 | ⚠️ 구독형 vs 비구독형 |

### TCO 권장 (recommended) — 6개
| 카테고리 | 소모품명 | 연간비용 | TCO 표기 |
|----------|----------|----------|----------|
| 젖병소독기 | 램프 | 0.7~3.5만원 | N년 램프 포함 총비용 |
| 콧물흡입기 | 노즐 | 1.5~4만원 | N년 노즐 포함 총비용 |
| 유아 전동칫솔 | 브러시 | 2~4만원 | N년 브러시 포함 총비용 |
| 유아 가습기 | 필터 | 2.5~6만원 | N년 필터 포함 총비용 |
| 전동 유축기 | 부품+저장팩 | 4~10만원 | N년 부품 포함 총비용 |
| 유아 공기청정기 | 필터 | 2.5~6만원 | N년 필터 포함 총비용 |

### TCO 선택 (optional) — 3개
| 카테고리 | 소모품명 | 연간비용 |
|----------|----------|----------|
| 이유식제조기 | 칼날 | 1~3만원 |
| 유아 체온계 | 프로브커버 | 1~3만원 |
| 유아식기세척기 | 세제 | 2~5만원 |

### TCO 불필요 (none) — 9개
아기띠·힙시트, 유모차, 카시트, 바운서·스윙, 아기 물티슈워머, 아기 침대·범퍼, 보행기·점퍼루, 아기 식탁의자, 아기 세탁세제·섬유유연제

---

## 5. 기존 레퍼런스와의 차이점

| 비교 항목 | 전자기기 | 반려동물 용품 | 육아용품 |
|-----------|---------|-------------|---------|
| 소모품비 vs 구매가 비율 | 10~30% | 50~300% | **30~300%** (기저귀처리기 역전) |
| 전용 소모품 락인 | 일부 | 대부분 | **브랜드별 전용 부품 강제** |
| 호환품 시장 | 활발 | 카테고리별 차이 | 기저귀 리필은 활발, 부품은 제한적 |
| 구독 모델 | 거의 없음 | GPS, 자동화장실 등 | **베이비캠 클라우드 저장** |
| TCO N년 기준 | 3년 (고가 5년) | 2년 | **2년** 또는 **실사용 기간** |
| 사용자 변수 | 가구 환경 | 반려동물 수·체중 | **아이 월령·수유방식·자녀 수** |
| 사용 기간 특이사항 | 기기 수명 기준 | 기기 수명 기준 | **아이 성장 단계 기준 (졸업 개념)** |

> **중요**: TCO 산출 시 N년 기준을 **아이 성장 기간**에 맞춰야 함.
> - 분유제조기: 분유 수유 기간 (~12개월) → 1년 TCO
> - 기저귀처리기: 기저귀 졸업까지 (~30개월) → 2년 TCO
> - 콧물흡입기/전동칫솔: 장기 사용 가능 → 3년 TCO

---

## 6. 블로그 글 생성 시 활용 규칙

1. **카테고리 입력** → JSON에서 `tco_tier` 확인
2. **`essential`** → TCO 프레이밍 필수
   - 제목: "2026년 {카테고리} N년 {consumable_name} 포함 총비용 비교"
   - 비교표: 구매가 + N년 {consumable_name}비 = N년 총비용
   - **역전 구조 강조**: "본체보다 리필이 더 비쌉니다" 훅 활용
   - **성장 기간 명시**: "기저귀 졸업(약 30개월)까지 총비용"
3. **`recommended`** → 소모품비를 부가 비교 항목으로
4. **`optional`** → 해당되는 경우만 언급
5. **N년 기준**: `usage_period` 참고하여 카테고리별 차등 적용
   - 분유제조기: 1년
   - 기저귀처리기/전동유축기: 2년
   - 콧물흡입기/전동칫솔: 3년
6. **자녀 수 변수**: "1자녀 기준" 명시, 둘째 시 기기 재활용 가능 여부 안내
7. **성장 단계 표기**: 실사용 월령 범위 명시 (예: "생후 0~12개월 사용")
8. **락인 경고**: `lock_in: true`이면 "전용 부품만 사용 가능" 경고 포함

### 육아용품 전용 블로그 훅 패턴

```
패턴 A (역전 구조): "본체 {구매가}만원, 2년 리필값 {소모품비}만원 — 진짜 비용은 {tco}만원"
패턴 B (성장 졸업): "기저귀 졸업까지 총비용 {금액}만원 — 본체값의 {배수}배"
패턴 C (둘째 재활용): "둘째까지 쓴다면? {카테고리} 3년 총비용 비교"
패턴 D (구독 경고): "매월 {금액}원 — 구독료 포함 {카테고리} 진짜 비용"
패턴 E (램프 vs LED): "교체 불필요 LED vs 저렴한 램프형 — {기간} 총비용은?"
```
