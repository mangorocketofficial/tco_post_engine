# 반려동물 용품 카테고리별 소모품 & TCO 레퍼런스

> 이 문서는 블로그 자동 생성 시스템에서 반려동물 용품 카테고리별 TCO(총소유비용) 분석 여부와 소모품 정보를 빠르게 조회하기 위한 레퍼런스입니다.
> 전자기기 레퍼런스(`category_consumables_reference.md`)와 동일한 구조를 따릅니다.

---

## 1. 사용법

- `tco_tier`로 해당 카테고리의 TCO 글 작성 필요성을 판단
- `consumable_name`을 활용해 "N년 {consumable_name} 포함 총비용" 형태로 TCO 표기
- `tco_formula`를 기반으로 비용 산출 구조 설정
- `tco_tier: none`인 카테고리는 TCO 프레이밍 없이 구매가+성능+AS 비교로 글 작성
- **반려동물 용품 특이사항**: 일부 카테고리(자동 화장실, GPS 트래커)는 구독형 소모품이 있어 `subscription_model: true` 표기

---

## 2. TCO 등급 정의

| tier | 의미 | 글 전략 |
|------|------|---------|
| `essential` | 소모품비가 구매가 대비 50%+ 또는 연 5만원+ | **TCO 비교 필수**. "N년 {소모품} 포함 총비용" 프레이밍 |
| `recommended` | 소모품비가 의미 있는 수준 (연 2~5만원) | **TCO 비교 권장**. 소모품비를 부가 비교 항목으로 |
| `optional` | 소모품비 소액 또는 일부 모델만 해당 | TCO 선택적. 해당되는 경우만 언급 |
| `none` | 소모품 없음 | TCO 프레이밍 불필요. 구매가+성능+AS 중심 |

> **전자기기 대비 차이점**: 반려동물 용품은 소모품비가 본체가를 초과하는 "역전 구조"가 흔함. `essential` 기준을 연 5만원+으로 높게 설정.

---

## 3. 카테고리 데이터

```json
[
  {
    "category": "자동 고양이 화장실",
    "group": "배변·위생",
    "tco_tier": "essential",
    "consumables": [
      {"name": "고양이 모래", "cycle": "2~4주 전체교체", "annual_cost_krw": "200000~400000"},
      {"name": "라이너/봉투", "cycle": "3~7일", "annual_cost_krw": "30000~80000"},
      {"name": "탈취필터", "cycle": "1~3개월", "annual_cost_krw": "20000~60000"}
    ],
    "consumable_name": "모래+소모품",
    "annual_cost_range": "250000~540000",
    "tco_label": "N년 모래·소모품 포함 총비용",
    "tco_formula": "구매가 + (연간 모래비 + 라이너비 + 필터비) × N년",
    "subscription_model": true,
    "notes": "연 25~54만원으로 반려동물 용품 중 TCO 임팩트 최대. 전용 모래 강제 모델(페스룸 등)은 비용 더 높음. 벤토나이트/두부모래 호환 여부가 핵심 비교 포인트. 정기배송 구독 모델 활성화. 1묘 기준, 다묘 시 비례 증가"
  },
  {
    "category": "펫 정수형 급수기",
    "group": "급식·급수",
    "tco_tier": "essential",
    "consumables": [
      {"name": "활성탄 필터", "cycle": "2~4주", "annual_cost_krw": "30000~72000"},
      {"name": "펌프/모터(일부 모델)", "cycle": "12~24개월", "annual_cost_krw": "교체시 10000~20000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "30000~72000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터단가 × 교체횟수) × N년",
    "subscription_model": false,
    "notes": "본체 3~8만원인데 필터 연 3~7만원 — 1년이면 본체가 초과하는 '역전 구조'. 호환 필터 유무가 TCO 핵심. 세라믹 필터 모델은 세척 재사용 가능(소모품비 0원에 가까움)"
  },
  {
    "category": "펫 탈취기",
    "group": "배변·위생",
    "tco_tier": "essential",
    "consumables": [
      {"name": "탈취 캡슐/리필", "cycle": "1~2개월", "annual_cost_krw": "40000~100000"},
      {"name": "필터(일부 모델)", "cycle": "3~6개월", "annual_cost_krw": "10000~30000"}
    ],
    "consumable_name": "캡슐",
    "annual_cost_range": "50000~130000",
    "tco_label": "N년 캡슐 포함 총비용",
    "tco_formula": "구매가 + (캡슐비 + 필터비) × N년",
    "subscription_model": false,
    "notes": "전용 캡슐 락인 모델(에어미데이 등) vs 범용 필터형 차이 큼. 전용 캡슐형은 연 10만원+. 전해수 생성 방식은 소모품 거의 없음(소금+물만)"
  },
  {
    "category": "펫 배변패드 자동수거기",
    "group": "배변·위생",
    "tco_tier": "essential",
    "consumables": [
      {"name": "전용 리필 비닐/카트리지", "cycle": "1~2주", "annual_cost_krw": "60000~150000"}
    ],
    "consumable_name": "리필",
    "annual_cost_range": "60000~150000",
    "tco_label": "N년 리필 포함 총비용",
    "tco_formula": "구매가 + (리필단가 × 교체횟수) × N년",
    "subscription_model": false,
    "notes": "기저귀 처리기와 동일 구조. 전용 리필 카트리지 강제가 대부분. 호환 비닐 사용 가능 여부가 TCO 핵심. 본체 3~8만원 대비 리필 연 6~15만원으로 역전 구조"
  },
  {
    "category": "펫 GPS 트래커",
    "group": "외출·이동",
    "tco_tier": "essential",
    "consumables": [
      {"name": "월 통신 구독료", "cycle": "매월", "annual_cost_krw": "60000~120000"}
    ],
    "consumable_name": "구독료",
    "annual_cost_range": "60000~120000",
    "tco_label": "N년 구독료 포함 총비용",
    "tco_formula": "구매가 + (월 구독료 × 12) × N년",
    "subscription_model": true,
    "notes": "LTE/GPS 통신 필수로 월 5천~1만원 구독료 발생. 본체 5~15만원 + 연 6~12만원 구독. 3년이면 구독료가 본체의 1.5~3배. 구독 해지 시 기기 무용지물"
  },
  {
    "category": "펫 드라이룸",
    "group": "미용·위생",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "집진 필터", "cycle": "3~6개월", "annual_cost_krw": "20000~40000"},
      {"name": "아로마 캡슐(선택)", "cycle": "1~2개월", "annual_cost_krw": "10000~30000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "20000~70000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터비 + 아로마비) × N년",
    "subscription_model": false,
    "notes": "본체 30~90만원 고가. 집진필터는 필수 교체, 아로마 캡슐은 선택. 쿠쿠 넬로, 아베크 등 브랜드별 전용 필터. 대형견용은 본체가 더 비쌈"
  },
  {
    "category": "펫 공기청정기",
    "group": "실내환경",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "펫 전용 프리필터", "cycle": "3~6개월", "annual_cost_krw": "10000~20000"},
      {"name": "HEPA필터", "cycle": "6~12개월", "annual_cost_krw": "20000~40000"},
      {"name": "탈취필터", "cycle": "6~12개월", "annual_cost_krw": "10000~20000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "40000~80000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터세트 × 교체횟수) × N년",
    "subscription_model": false,
    "notes": "일반 공기청정기와 구조 동일하나 펫 전용 프리필터(털 집진) 추가. 위닉스 펫, 삼성 비스포크 펫 등. 일반 공기청정기 카테고리와 중복 가능 — 펫 특화 모델만 다룸"
  },
  {
    "category": "전동 펫 클리퍼(바리깡)",
    "group": "미용·위생",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "교체 칼날", "cycle": "6~12개월", "annual_cost_krw": "15000~40000"},
      {"name": "윤활유", "cycle": "2~3개월", "annual_cost_krw": "5000~10000"}
    ],
    "consumable_name": "칼날",
    "annual_cost_range": "20000~50000",
    "tco_label": "N년 칼날 포함 총비용",
    "tco_formula": "구매가 + (칼날세트 × 교체횟수) × N년",
    "subscription_model": false,
    "notes": "가정용 3~10만원대. 전문가용(안디스, 월 등)은 칼날 단가 높음(3~5만원). 배터리 교체 불가 모델은 배터리 수명=제품 수명. 다견가정은 칼날 마모 빠름"
  },
  {
    "category": "펫 구강관리기",
    "group": "미용·위생",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "브러시헤드/노즐팁", "cycle": "2~3개월", "annual_cost_krw": "15000~30000"}
    ],
    "consumable_name": "브러시",
    "annual_cost_range": "15000~30000",
    "tco_label": "N년 브러시 포함 총비용",
    "tco_formula": "구매가 + (브러시헤드 × 교체횟수) × N년",
    "subscription_model": false,
    "notes": "전동 칫솔형, 초음파 스케일러형 등. 브러시헤드 호환 여부 확인. 다두 가정은 개체별 브러시 필요(위생). 인간용 전동칫솔과 구조 유사"
  },
  {
    "category": "자동 급식기",
    "group": "급식·급수",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "건조제팩", "cycle": "1~2개월", "annual_cost_krw": "10000~20000"},
      {"name": "필터(습식 대응 모델)", "cycle": "3~6개월", "annual_cost_krw": "10000~20000"},
      {"name": "배터리(비상용)", "cycle": "6~12개월", "annual_cost_krw": "5000~10000"}
    ],
    "consumable_name": "소모품",
    "annual_cost_range": "15000~50000",
    "tco_label": "N년 소모품 포함 총비용",
    "tco_formula": "구매가 + (건조제 + 필터 + 배터리) × N년",
    "subscription_model": false,
    "notes": "건식 전용은 건조제만(소액). 습식 대응·카메라 내장 모델은 소모품 더 다양. 페페, 신일 퍼비, PETKIT 등. 사료 자체는 TCO에 미포함(소모품이 아닌 식비)"
  },
  {
    "category": "리필형 고양이 스크래쳐",
    "group": "놀이·운동",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "리필 골판지/스크래치패드", "cycle": "1~3개월", "annual_cost_krw": "20000~60000"}
    ],
    "consumable_name": "리필패드",
    "annual_cost_range": "20000~60000",
    "tco_label": "N년 리필패드 포함 총비용",
    "tco_formula": "구매가 + (리필패드 × 교체횟수) × N년",
    "subscription_model": false,
    "notes": "프레임 고정 + 골판지 교체형. 일체형 스크래쳐 대비 장기 비용 절감 가능. 단, 교체 빈도는 고양이 성향(활동량, 다묘 여부)에 따라 크게 다름. 호환 리필 유무가 TCO 핵심"
  },
  {
    "category": "펫 살균탈취기(전해수/UV)",
    "group": "배변·위생",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "UV 램프(UV형)", "cycle": "12~24개월", "annual_cost_krw": "10000~20000"},
      {"name": "소금/전해질(전해수형)", "cycle": "1~2개월", "annual_cost_krw": "5000~10000"}
    ],
    "consumable_name": "소모품",
    "annual_cost_range": "5000~20000",
    "tco_label": "N년 소모품 포함 총비용",
    "tco_formula": "구매가 + 소모품비 × N년",
    "subscription_model": false,
    "notes": "전해수 생성기(물+소금→차아염소산수)는 소모품 극소. UV형은 램프 교체 필요. 오존 방식은 소모품 없음. 방식별 소모품 구조가 완전히 다름"
  },
  {
    "category": "펫 발세척기",
    "group": "미용·위생",
    "tco_tier": "optional",
    "consumables": [
      {"name": "실리콘 브러시(마모 교체)", "cycle": "6~12개월", "annual_cost_krw": "5000~15000"},
      {"name": "전용 세정제(선택)", "cycle": "1~2개월", "annual_cost_krw": "10000~20000"}
    ],
    "consumable_name": "소모품",
    "annual_cost_range": "10000~35000",
    "tco_label": "N년 소모품 포함 총비용",
    "tco_formula": "구매가 + 소모품비 × N년",
    "subscription_model": false,
    "notes": "수동형(컵형)은 소모품 거의 없음. 자동형은 브러시+세정제. 전용 세정제는 선택사항(물만으로 사용 가능)"
  },
  {
    "category": "점착형 펫 털제거 롤러",
    "group": "실내환경",
    "tco_tier": "optional",
    "consumables": [
      {"name": "점착 리필 테이프", "cycle": "1~2주", "annual_cost_krw": "15000~40000"}
    ],
    "consumable_name": "리필",
    "annual_cost_range": "15000~40000",
    "tco_label": "N년 리필 포함 총비용",
    "tco_formula": "구매가 + (리필 × 교체횟수) × N년",
    "subscription_model": false,
    "notes": "본체 1~3만원, 리필 연 1.5~4만원. 실리콘 재사용형은 소모품 0원이지만 제거력 차이. 점착형 vs 실리콘형 TCO 비교가 콘텐츠 훅"
  },
  {
    "category": "강아지 짖음방지기",
    "group": "훈련·교육",
    "tco_tier": "optional",
    "consumables": [
      {"name": "배터리/충전지", "cycle": "1~3개월", "annual_cost_krw": "5000~15000"},
      {"name": "시트로넬라 리필(스프레이형)", "cycle": "1~2개월", "annual_cost_krw": "15000~30000"}
    ],
    "consumable_name": "리필",
    "annual_cost_range": "5000~45000",
    "tco_label": "N년 리필 포함 총비용",
    "tco_formula": "구매가 + 리필비 × N년",
    "subscription_model": false,
    "notes": "초음파형은 배터리만(소액). 시트로넬라 스프레이형은 리필 비용 의미있음. 진동형은 충전식이라 소모품 거의 없음. 방식별 소모품 차이 큼"
  },
  {
    "category": "고양이 자동 장난감",
    "group": "놀이·운동",
    "tco_tier": "optional",
    "consumables": [
      {"name": "깃털/끈 리필", "cycle": "1~3개월", "annual_cost_krw": "10000~25000"},
      {"name": "배터리(비충전형)", "cycle": "1~3개월", "annual_cost_krw": "5000~15000"}
    ],
    "consumable_name": "리필",
    "annual_cost_range": "10000~40000",
    "tco_label": "N년 리필 포함 총비용",
    "tco_formula": "구매가 + 리필비 × N년",
    "subscription_model": false,
    "notes": "레이저형은 소모품 거의 없음(충전식). 깃털/움직이는 물체형은 리필 교체 빈번. 고양이가 물어뜯어 파손되므로 내구성이 교체주기 결정"
  },
  {
    "category": "어항 여과기",
    "group": "관상어·수족관",
    "tco_tier": "essential",
    "consumables": [
      {"name": "여과재(세라믹/활성탄)", "cycle": "3~6개월", "annual_cost_krw": "20000~50000"},
      {"name": "여과솜/스펀지", "cycle": "1~2개월", "annual_cost_krw": "10000~25000"},
      {"name": "UV 램프(UV형만)", "cycle": "6~12개월", "annual_cost_krw": "15000~30000"}
    ],
    "consumable_name": "여과재",
    "annual_cost_range": "30000~100000",
    "tco_label": "N년 여과재 포함 총비용",
    "tco_formula": "구매가 + (여과재 + 여과솜 + UV램프) × N년",
    "subscription_model": false,
    "notes": "외부여과기(에하임, 테트라 등) 본체 5~30만원. 여과재 종류 다양(세라믹링, 활성탄, 바이오볼). 수조 크기별 교체량 비례. 해수어 수조는 비용 2~3배"
  },
  {
    "category": "펫 미용 드라이기",
    "group": "미용·위생",
    "tco_tier": "optional",
    "consumables": [
      {"name": "필터(일부 모델)", "cycle": "6~12개월", "annual_cost_krw": "5000~15000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "0~15000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + 필터비 × N년",
    "subscription_model": false,
    "notes": "대부분 소모품 없음. 일부 고급 모델만 흡입 필터 교체. 인간용 헤어드라이어와 유사. TCO 임팩트 작음"
  },
  {
    "category": "강아지 자동 공던지기",
    "group": "놀이·운동",
    "tco_tier": "optional",
    "consumables": [
      {"name": "전용 공", "cycle": "1~3개월", "annual_cost_krw": "10000~25000"}
    ],
    "consumable_name": "공",
    "annual_cost_range": "10000~25000",
    "tco_label": "N년 전용 공 포함 총비용",
    "tco_formula": "구매가 + (공 × 교체횟수) × N년",
    "subscription_model": false,
    "notes": "iFetch, GoDogGo 등. 전용 공 필수 모델 vs 일반 테니스공 호환 모델 차이. 대형견은 공 파손 빈번(교체 주기 짧음). 실내/실외 모델 구분"
  },
  {
    "category": "펫 CCTV(간식투척형)",
    "group": "스마트·모니터링",
    "tco_tier": "optional",
    "consumables": [
      {"name": "클라우드 저장 구독(선택)", "cycle": "매월", "annual_cost_krw": "0~60000"},
      {"name": "간식 카트리지(간식투척형)", "cycle": "사용빈도에 따라", "annual_cost_krw": "간식비용은 TCO 미포함"}
    ],
    "consumable_name": "구독료",
    "annual_cost_range": "0~60000",
    "tco_label": "N년 구독료 포함 총비용",
    "tco_formula": "구매가 + 클라우드 구독료 × N년",
    "subscription_model": true,
    "notes": "펫캠 자체는 소모품 없음. 클라우드 영상 저장 구독은 선택(무료 실시간 스트리밍은 기본). 퍼보, 펫큐브 등 간식투척형은 간식 소비 있으나 TCO에는 미포함(식비 분류)"
  }
]
```

---

## 4. 빠른 조회 테이블

### TCO 필수 (essential) — 5개
| 카테고리 | 소모품명 | 연간비용 | TCO 표기 | 특징 |
|----------|----------|----------|----------|------|
| 자동 고양이 화장실 | 모래+소모품 | 25~54만원 | N년 모래·소모품 포함 총비용 | 🔥 반려용품 TCO 최대 |
| 펫 정수형 급수기 | 필터 | 3~7만원 | N년 필터 포함 총비용 | 💡 1년에 본체가 초과 |
| 펫 탈취기 | 캡슐 | 5~13만원 | N년 캡슐 포함 총비용 | 전용 캡슐 락인 주의 |
| 펫 배변패드 자동수거기 | 리필 | 6~15만원 | N년 리필 포함 총비용 | 💡 1년에 본체가 초과 |
| 어항 여과기 | 여과재 | 3~10만원 | N년 여과재 포함 총비용 | 수조 크기 비례 |

### 구독형 TCO 필수 — 1개
| 카테고리 | 소모품명 | 연간비용 | TCO 표기 | 특징 |
|----------|----------|----------|----------|------|
| 펫 GPS 트래커 | 구독료 | 6~12만원 | N년 구독료 포함 총비용 | ⚠️ 해지 시 기기 무용 |

### TCO 권장 (recommended) — 7개
| 카테고리 | 소모품명 | 연간비용 | TCO 표기 |
|----------|----------|----------|----------|
| 펫 드라이룸 | 필터 | 2~7만원 | N년 필터 포함 총비용 |
| 펫 공기청정기 | 필터 | 4~8만원 | N년 필터 포함 총비용 |
| 전동 펫 클리퍼 | 칼날 | 2~5만원 | N년 칼날 포함 총비용 |
| 펫 구강관리기 | 브러시 | 1.5~3만원 | N년 브러시 포함 총비용 |
| 자동 급식기 | 소모품 | 1.5~5만원 | N년 소모품 포함 총비용 |
| 리필형 고양이 스크래쳐 | 리필패드 | 2~6만원 | N년 리필패드 포함 총비용 |
| 펫 살균탈취기 | 소모품 | 0.5~2만원 | N년 소모품 포함 총비용 |

### TCO 선택 (optional) — 7개
| 카테고리 | 소모품명 | 연간비용 |
|----------|----------|----------|
| 펫 발세척기 | 소모품 | 1~3.5만원 |
| 점착형 펫 털제거 롤러 | 리필 | 1.5~4만원 |
| 강아지 짖음방지기 | 리필 | 0.5~4.5만원 |
| 고양이 자동 장난감 | 리필 | 1~4만원 |
| 펫 미용 드라이기 | 필터 | 0~1.5만원 |
| 강아지 자동 공던지기 | 공 | 1~2.5만원 |
| 펫 CCTV(간식투척형) | 구독료 | 0~6만원 |

---

## 5. 전자기기 레퍼런스와의 차이점

| 비교 항목 | 전자기기 | 반려동물 용품 |
|-----------|---------|-------------|
| 소모품비 vs 구매가 비율 | 보통 10~30% | **50~300%** (역전 구조 흔함) |
| 전용 소모품 락인 | 일부 (다이슨 등) | **대부분** (전용 모래, 캡슐 등) |
| 호환품 시장 | 활발 | 카테고리별 차이 큼 |
| 구독 모델 | 거의 없음 | GPS, 자동화장실, CCTV 등 |
| TCO N년 기준 | 3년 (고가 5년) | **2년** 권장 (제품 수명 짧음) |
| 사용자 변수 | 가구 환경 (평수 등) | **반려동물 수·체중·활동량** |

> **중요**: N년 기준을 전자기기(3년)보다 짧은 **2년**으로 설정 권장. 반려동물 용품은 제품 수명이 짧고, 소모품 단가가 높아 2년 비교로도 충분한 TCO 차이가 발생.

---

## 6. 블로그 글 생성 시 활용 규칙

1. **카테고리 입력** → JSON에서 `tco_tier` 확인
2. **`essential`** → TCO 프레이밍 필수
   - 제목: "2026년 {카테고리} N년 {consumable_name} 포함 총비용 비교"
   - 비교표: 구매가 + N년 {consumable_name}비 = N년 총비용
   - **역전 구조 강조**: "본체보다 소모품이 더 비쌉니다" 훅 활용
3. **`recommended`** → 소모품비를 부가 비교 항목으로
4. **`optional`** → 해당되는 경우만 언급
5. **N년 기준**: 기본 **2년**. 고가 제품(드라이룸, 자동화장실)은 3년
6. **다두/다묘 변수**: "1마리 기준" 명시, 다두가정 시 비례 증가 안내
7. **호환품 비교**: `compatible_available: true`인 소모품은 정품 vs 호환품 TCO 이중 비교
8. **구독형 모델**: `subscription_model: true`이면 "해지 시 기기 무용" 경고 포함

### 반려동물 용품 전용 블로그 훅 패턴

```
패턴 A (역전 구조): "본체 {구매가}만원, 2년 모래값 {소모품비}만원 — 진짜 비용은 {tco}만원"
패턴 B (락인 경고): "{브랜드} 전용 모래만 써야 합니다 — 2년 총비용 차이 {금액}만원"
패턴 C (다두 변수): "고양이 2마리면? 모래값만 연 {금액}만원 — 호환 모래 쓸 수 있는 제품이 답"
```