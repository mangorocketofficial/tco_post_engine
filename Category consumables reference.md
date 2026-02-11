# 가전제품 카테고리별 소모품 & TCO 레퍼런스

> 이 문서는 블로그 자동 생성 시스템에서 카테고리별 TCO(총소유비용) 분석 여부와 소모품 정보를 빠르게 조회하기 위한 레퍼런스입니다.

---

## 1. 사용법

- `tco_tier`로 해당 카테고리의 TCO 글 작성 필요성을 판단
- `consumable_name`을 활용해 "N년 {consumable_name} 포함 총비용" 형태로 TCO 표기
- `tco_formula`를 기반으로 비용 산출 구조 설정
- `tco_tier: none`인 카테고리는 TCO 프레이밍 없이 구매가+성능+AS 비교로 글 작성

---

## 2. TCO 등급 정의

| tier | 의미 | 글 전략 |
|------|------|---------|
| `essential` | 소모품비가 구매결정에 큰 영향 (연 2만원+) | **TCO 비교 필수**. "N년 {소모품} 포함 총비용" 프레이밍 |
| `recommended` | 소모품비가 의미 있는 수준 (연 1~5만원) | **TCO 비교 권장**. 소모품비를 부가 비교 항목으로 |
| `optional` | 소모품비 소액 또는 일부 모델만 해당 | TCO 선택적. 해당되는 경우만 언급 |
| `none` | 소모품 없음 | TCO 프레이밍 불필요. 구매가+성능+AS 중심 |

---

## 3. 카테고리 데이터

```json
[
  {
    "category": "공기청정기",
    "group": "공기질·환경",
    "tco_tier": "essential",
    "consumables": [
      {"name": "HEPA필터", "cycle": "6~12개월", "annual_cost_krw": "15000~40000"},
      {"name": "탈취필터", "cycle": "6~12개월", "annual_cost_krw": "10000~20000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "20000~60000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터단가 × 교체횟수)",
    "notes": "호환필터 사용 시 50% 절감. 일부 제품 HEPA 5년 무교체(다이슨). 제품별 필터 구조 상이"
  },
  {
    "category": "가습기",
    "group": "공기질·환경",
    "tco_tier": "optional",
    "consumables": [
      {"name": "가습필터(자연기화식만)", "cycle": "3~6개월", "annual_cost_krw": "20000~40000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "0~40000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터단가 × 교체횟수)",
    "notes": "초음파식은 필터 없음(전기료만). 자연기화식만 필터 소모품 발생. 방식에 따라 TCO 구조 다름"
  },
  {
    "category": "제습기",
    "group": "공기질·환경",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음. 필터 물세척 반영구. 전기료가 주요 유지비"
  },
  {
    "category": "음식물처리기",
    "group": "공기질·환경",
    "tco_tier": "essential",
    "consumables": [
      {"name": "탈취필터", "cycle": "1~3개월", "annual_cost_krw": "40000~100000"},
      {"name": "미생물제(발효식만)", "cycle": "3~6개월", "annual_cost_krw": "20000~50000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "60000~150000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터단가 × 교체횟수)",
    "notes": "건조식: 탈취필터만. 발효식: 미생물 추가. 냄새 민감한 사람은 교체주기 더 짧음. 연간 유지비 높음"
  },
  {
    "category": "로봇청소기",
    "group": "청소",
    "tco_tier": "essential",
    "consumables": [
      {"name": "필터", "cycle": "3~6개월", "annual_cost_krw": "10000~30000"},
      {"name": "사이드브러시", "cycle": "3~6개월", "annual_cost_krw": "5000~15000"},
      {"name": "메인브러시", "cycle": "6~12개월", "annual_cost_krw": "10000~30000"},
      {"name": "먼지봉투", "cycle": "1~2개월", "annual_cost_krw": "20000~60000"},
      {"name": "물걸레패드", "cycle": "1~3개월", "annual_cost_krw": "15000~40000"}
    ],
    "consumable_name": "소모품",
    "annual_cost_range": "160000~330000",
    "tco_label": "N년 소모품 포함 총비용",
    "tco_formula": "구매가 + 연간 소모품비 × N년",
    "notes": "소모품 종류 많고 비용 높음(연 16~33만원). 구매가의 10~30%. 호환품 활용 시 절감 가능"
  },
  {
    "category": "무선청소기",
    "group": "청소",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "필터", "cycle": "6~12개월", "annual_cost_krw": "10000~30000"},
      {"name": "배터리", "cycle": "24~36개월", "annual_cost_krw": "교체시 50000~100000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "10000~30000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터비 × N년) + 배터리 1회 교체",
    "notes": "배터리 교체비 5~10만원(2~3년). 배터리 수명이 제품 수명 결정. 배터리 별도 표기 권장"
  },
  {
    "category": "유선청소기",
    "group": "청소",
    "tco_tier": "optional",
    "consumables": [
      {"name": "HEPA필터", "cycle": "6~12개월", "annual_cost_krw": "10000~20000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "10000~20000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터단가 × 교체횟수)",
    "notes": "소모품 최소. 먼지봉투형은 봉투 추가(월 1~2천원)"
  },
  {
    "category": "핸디형청소기",
    "group": "청소",
    "tco_tier": "optional",
    "consumables": [
      {"name": "필터", "cycle": "6~12개월", "annual_cost_krw": "10000~20000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "10000~20000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터단가 × 교체횟수)",
    "notes": "무선청소기와 유사. 소형이라 필터 저렴"
  },
  {
    "category": "물걸레청소기",
    "group": "청소",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "물걸레패드", "cycle": "1~3개월", "annual_cost_krw": "20000~50000"},
      {"name": "필터", "cycle": "6개월", "annual_cost_krw": "10000~15000"}
    ],
    "consumable_name": "패드",
    "annual_cost_range": "30000~60000",
    "tco_label": "N년 패드 포함 총비용",
    "tco_formula": "구매가 + (패드비 × 교체횟수) + 필터비",
    "notes": "패드 교체가 주요 비용. 일회용 vs 세탁형에 따라 비용 차이 큼"
  },
  {
    "category": "세탁기",
    "group": "세탁·의류",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "10000~20000",
    "tco_label": null,
    "tco_formula": null,
    "notes": "고정 소모품 없음. 세탁조 클리너는 선택사항(월 1회, 연 1~2만원). 전기+수도가 주 유지비"
  },
  {
    "category": "건조기",
    "group": "세탁·의류",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음. 보풀필터 세척만. 전기료가 유일한 유지비(히트펌프 vs 콘덴서 차이). 월 5천~1만원"
  },
  {
    "category": "세탁기건조기",
    "group": "세탁·의류",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "10000~20000",
    "tco_label": null,
    "tco_formula": null,
    "notes": "세탁기와 동일. 건조 기능 전기료 추가"
  },
  {
    "category": "의류관리기",
    "group": "세탁·의류",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "탈취필터(에어드레서)", "cycle": "3~6개월", "annual_cost_krw": "20000~40000"},
      {"name": "향시트(선택)", "cycle": "사용시마다", "annual_cost_krw": "10000~20000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "20000~50000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터비 × 교체횟수)",
    "notes": "LG 스타일러: 먼지필터 세척만(소모품 거의 없음). 삼성 에어드레서: 미세먼지 필터 교체. 브랜드별 차이 큼"
  },
  {
    "category": "스팀다리미",
    "group": "세탁·의류",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음. 석회질 제거용 세척만 필요"
  },
  {
    "category": "보풀제거기",
    "group": "세탁·의류",
    "tco_tier": "optional",
    "consumables": [
      {"name": "칼날", "cycle": "6~12개월", "annual_cost_krw": "5000~10000"}
    ],
    "consumable_name": "칼날",
    "annual_cost_range": "5000~10000",
    "tco_label": "N년 칼날 포함 총비용",
    "tco_formula": "구매가 + (칼날비 × 교체횟수)",
    "notes": "소모품 매우 저가. 제품 단가 자체가 낮아 TCO 임팩트 작음"
  },
  {
    "category": "에어컨",
    "group": "냉난방·공조",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "필터 물세척 반영구. 2년마다 분해세척 권장(전문업체 8~15만원). 전기료가 핵심 유지비"
  },
  {
    "category": "이동식에어컨",
    "group": "냉난방·공조",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "에어컨과 동일. 배수통 관리만 추가. 전기료가 핵심"
  },
  {
    "category": "창문형에어컨",
    "group": "냉난방·공조",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "에어컨과 동일. 설치비 별도"
  },
  {
    "category": "전기매트",
    "group": "냉난방·공조",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음. 전자파·안전이 핵심 구매 기준"
  },
  {
    "category": "선풍기",
    "group": "냉난방·공조",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음"
  },
  {
    "category": "서큘레이터",
    "group": "냉난방·공조",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음"
  },
  {
    "category": "휴대용선풍기",
    "group": "냉난방·공조",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음. 내장배터리 수명=제품 수명"
  },
  {
    "category": "정수기",
    "group": "주방",
    "tco_tier": "essential",
    "consumables": [
      {"name": "세디멘트필터", "cycle": "3~6개월", "annual_cost_krw": "10000~20000"},
      {"name": "카본필터", "cycle": "6~12개월", "annual_cost_krw": "15000~30000"},
      {"name": "멤브레인필터", "cycle": "12~24개월", "annual_cost_krw": "15000~40000"}
    ],
    "consumable_name": "카트리지",
    "annual_cost_range": "50000~150000",
    "tco_label": "N년 카트리지 포함 총비용",
    "tco_formula": "구매가 + (단계별 필터단가 × 교체횟수) 또는 렌탈비 × N년",
    "notes": "렌탈 vs 구매 비교 필수. 자가관리 시 필터비만. 렌탈은 관리비 포함. 필터 단계 수는 모델별 상이(2~5단계)"
  },
  {
    "category": "식기세척기",
    "group": "주방",
    "tco_tier": "optional",
    "consumables": [
      {"name": "정수필터(일부 모델)", "cycle": "12개월", "annual_cost_krw": "20000~30000"},
      {"name": "세제+린스+소금", "cycle": "상시", "annual_cost_krw": "30000~70000"}
    ],
    "consumable_name": "세제",
    "annual_cost_range": "50000~100000",
    "tco_label": "N년 세제 포함 총비용",
    "tco_formula": "구매가 + 연간 세제류비 + 필터비",
    "notes": "정수필터는 일부 모델만. 세제+린스+소금이 실질 소모품. 수도+전기료 추가"
  },
  {
    "category": "냉장고",
    "group": "주방",
    "tco_tier": "optional",
    "consumables": [
      {"name": "정수필터(정수/제빙 모델만)", "cycle": "6~12개월", "annual_cost_krw": "20000~30000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "0~30000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터단가 × 교체횟수)",
    "notes": "정수/제빙 기능 있는 모델만 필터 교체. 없으면 소모품 0원. 전기료가 핵심 유지비"
  },
  {
    "category": "에어프라이어",
    "group": "주방",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음. 종이호일은 선택사항"
  },
  {
    "category": "비데",
    "group": "개인위생·미용",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "탈취필터", "cycle": "6~12개월", "annual_cost_krw": "10000~20000"},
      {"name": "정수필터", "cycle": "6~12개월", "annual_cost_krw": "10000~20000"},
      {"name": "노즐", "cycle": "24~36개월", "annual_cost_krw": "교체시 10000~20000"}
    ],
    "consumable_name": "필터",
    "annual_cost_range": "20000~40000",
    "tco_label": "N년 필터 포함 총비용",
    "tco_formula": "구매가 + (필터비 × 교체횟수)",
    "notes": "탈취필터+정수필터 교체. 노즐은 소모성이지만 장수명. 전기료 추가(온수·건조)"
  },
  {
    "category": "구강세정기",
    "group": "개인위생·미용",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "노즐팁", "cycle": "3~6개월", "annual_cost_krw": "10000~20000"}
    ],
    "consumable_name": "노즐",
    "annual_cost_range": "10000~20000",
    "tco_label": "N년 노즐 포함 총비용",
    "tco_formula": "구매가 + (노즐팁 × 교체횟수)",
    "notes": "노즐팁만 교체. 가족 구성원별 노즐 필요. 호환 노즐 유통 여부 확인"
  },
  {
    "category": "전기면도기",
    "group": "개인위생·미용",
    "tco_tier": "recommended",
    "consumables": [
      {"name": "칼날+망 세트", "cycle": "12~24개월", "annual_cost_krw": "30000~50000"},
      {"name": "세척액 카트리지(해당 모델)", "cycle": "2~3개월", "annual_cost_krw": "20000~40000"}
    ],
    "consumable_name": "칼날",
    "annual_cost_range": "30000~50000",
    "tco_label": "N년 칼날 포함 총비용",
    "tco_formula": "구매가 + (칼날세트 × 교체횟수)",
    "notes": "브라운 18개월, 필립스 24개월 권장. 세척액 카트리지 모델은 세척액 추가 비용. 매일 사용 시 더 짧아짐"
  },
  {
    "category": "헤어드라이어",
    "group": "개인위생·미용",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음. 다이슨은 필터 청소만(교체 불필요)"
  },
  {
    "category": "고데기",
    "group": "개인위생·미용",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음. 열판 코팅 마모 시 본체 교체"
  },
  {
    "category": "안마의자",
    "group": "건강·마사지",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음. 고장 시 수리비가 핵심(부품비 높음). AS 접근성이 핵심 비교 포인트"
  },
  {
    "category": "마사지건",
    "group": "건강·마사지",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음. 어태치먼트 추가 구매 가능(선택)"
  },
  {
    "category": "어깨안마기",
    "group": "건강·마사지",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음"
  },
  {
    "category": "종아리마사지기",
    "group": "건강·마사지",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음"
  },
  {
    "category": "TV",
    "group": "생활",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음. 전기료+구독서비스가 유지비이나 제품 비교와 무관"
  },
  {
    "category": "스마트휴지통",
    "group": "생활",
    "tco_tier": "optional",
    "consumables": [
      {"name": "전용 리필 비닐", "cycle": "1~2주", "annual_cost_krw": "20000~50000"}
    ],
    "consumable_name": "리필",
    "annual_cost_range": "20000~50000",
    "tco_label": "N년 리필 포함 총비용",
    "tco_formula": "구매가 + (리필비 × 교체횟수)",
    "notes": "전용 리필 비닐이 핵심 소모품. 호환 비닐 사용 가능 여부 확인 필요"
  },
  {
    "category": "에어건",
    "group": "생활",
    "tco_tier": "none",
    "consumables": [],
    "consumable_name": null,
    "annual_cost_range": "0",
    "tco_label": null,
    "tco_formula": null,
    "notes": "소모품 없음"
  }
]
```

---

## 4. 빠른 조회 테이블

### TCO 필수 (essential) — 4개
| 카테고리 | 소모품명 | 연간비용 | TCO 표기 |
|----------|----------|----------|----------|
| 공기청정기 | 필터 | 2~6만원 | N년 필터 포함 총비용 |
| 로봇청소기 | 소모품 | 16~33만원 | N년 소모품 포함 총비용 |
| 정수기 | 카트리지 | 5~15만원 | N년 카트리지 포함 총비용 |
| 음식물처리기 | 필터 | 6~15만원 | N년 필터 포함 총비용 |

### TCO 권장 (recommended) — 6개
| 카테고리 | 소모품명 | 연간비용 | TCO 표기 |
|----------|----------|----------|----------|
| 무선청소기 | 필터 | 1~3만원 | N년 필터 포함 총비용 |
| 물걸레청소기 | 패드 | 3~6만원 | N년 패드 포함 총비용 |
| 비데 | 필터 | 2~4만원 | N년 필터 포함 총비용 |
| 전기면도기 | 칼날 | 3~5만원 | N년 칼날 포함 총비용 |
| 구강세정기 | 노즐 | 1~2만원 | N년 노즐 포함 총비용 |
| 의류관리기 | 필터 | 2~5만원 | N년 필터 포함 총비용 |

### TCO 선택 (optional) — 7개
| 카테고리 | 소모품명 | 연간비용 |
|----------|----------|----------|
| 유선청소기 | 필터 | 1~2만원 |
| 핸디형청소기 | 필터 | 1~2만원 |
| 식기세척기 | 세제 | 5~10만원 |
| 냉장고 | 필터 | 0~3만원 |
| 가습기 | 필터 | 0~4만원 |
| 스마트휴지통 | 리필 | 2~5만원 |
| 보풀제거기 | 칼날 | 0.5~1만원 |

### TCO 불필요 (none) — 20개
제습기, 세탁기, 건조기, 세탁기건조기, 스팀다리미, 에어컨, 이동식에어컨, 창문형에어컨, 전기매트, 선풍기, 서큘레이터, 휴대용선풍기, 에어프라이어, 헤어드라이어, 고데기, 안마의자, 마사지건, 어깨안마기, 종아리마사지기, TV, 에어건

---

## 5. 블로그 글 생성 시 활용 규칙

1. **카테고리 입력** → JSON에서 `tco_tier` 확인
2. **`essential` / `recommended`** → TCO 프레이밍 적용
   - 제목: "2026년 {카테고리} N년 {consumable_name} 포함 총비용 비교"
   - 비교표: 구매가 + N년 {consumable_name}비 = N년 총비용
3. **`optional`** → 소모품비를 부가 정보로만 언급
4. **`none`** → TCO 프레이밍 없이 구매가+성능+AS 중심
5. **N년 기준**: 기본 3년. 고가 제품(에어컨, 냉장고, TV)은 5년