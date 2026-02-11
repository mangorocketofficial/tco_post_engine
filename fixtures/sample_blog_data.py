"""
Sample blog post data for template testing.
Matches the consumable-based api-contract schema with added content fields.
"""

from src.part_b.template_engine.models import (
    BlogPostData,
    CategoryCriteria,
    ConsumableItem,
    CredibilityStats,
    FAQ,
    HomeType,
    PriceVolatility,
    Product,
    SituationPick,
    TCOData,
)


def get_sample_products() -> list[Product]:
    """Create sample product list with consumable-based TCO data."""
    return [
        Product(
            product_id="roborock-q-revo-s",
            name="로보락 Q Revo S",
            brand="로보락",
            release_date="2024-03-15",
            tco=TCOData(
                purchase_price=899000,
                annual_consumable_cost=60000,
                consumable_cost_total=180000,
                real_cost_total=1079000,
                consumable_breakdown=[
                    ConsumableItem(name="필터", unit_price=15000, changes_per_year=2, annual_cost=30000, compatible_available=True, compatible_price=8000),
                    ConsumableItem(name="사이드브러시", unit_price=10000, changes_per_year=2, annual_cost=20000),
                    ConsumableItem(name="먼지봉투", unit_price=5000, changes_per_year=2, annual_cost=10000),
                ],
            ),
            cta_link="https://link.coupang.com/roborock-q-revo-s?utm_source=tco_blog",
            highlight="3년 소모품 포함 총비용 최저, 가성비 최강",
            slot_label="최소 비용 실속",
            verdict="recommend",
            recommendation_reason="3년 소모품 포함 총비용이 1,079,000원으로 가장 낮고, 호환필터 사용 시 추가 절감 가능합니다.",
        ),
        Product(
            product_id="samsung-bespoke-jet-ai",
            name="삼성 비스포크 제트 AI",
            brand="삼성",
            release_date="2024-06-01",
            tco=TCOData(
                purchase_price=1290000,
                annual_consumable_cost=45000,
                consumable_cost_total=135000,
                real_cost_total=1425000,
                consumable_breakdown=[
                    ConsumableItem(name="필터", unit_price=25000, changes_per_year=1, annual_cost=25000),
                    ConsumableItem(name="사이드브러시", unit_price=10000, changes_per_year=2, annual_cost=20000),
                ],
            ),
            cta_link="https://link.coupang.com/samsung-bespoke-jet-ai?utm_source=tco_blog",
            highlight="연간 소모품비 최저, 삼성 AS망",
            slot_label="유지비 절약형",
            verdict="recommend",
            recommendation_reason="연간 소모품비가 45,000원으로 가장 낮고, 삼성 AS망으로 부품 수급이 빠릅니다.",
        ),
        Product(
            product_id="ecovacs-x2-combo",
            name="에코백스 X2 콤보",
            brand="에코백스",
            release_date="2024-09-10",
            tco=TCOData(
                purchase_price=1490000,
                annual_consumable_cost=90000,
                consumable_cost_total=270000,
                real_cost_total=1760000,
                consumable_breakdown=[
                    ConsumableItem(name="필터", unit_price=20000, changes_per_year=2, annual_cost=40000, compatible_available=True, compatible_price=12000),
                    ConsumableItem(name="사이드브러시", unit_price=10000, changes_per_year=3, annual_cost=30000),
                    ConsumableItem(name="물걸레패드", unit_price=10000, changes_per_year=2, annual_cost=20000),
                ],
            ),
            cta_link="https://link.coupang.com/ecovacs-x2-combo?utm_source=tco_blog",
            highlight="핸디+로봇 올인원",
            slot_label="풀옵션 올인원",
            verdict="caution",
            caution_reason="핸디 청소기 일체형으로 편리하지만, 3년 소모품 포함 총비용이 176만원으로 가장 높고 소모품 종류도 많습니다.",
        ),
    ]


def get_sample_blog_data() -> BlogPostData:
    """Create complete sample BlogPostData for template testing."""
    products = get_sample_products()

    return BlogPostData(
        title="2026년 로봇청소기 추천 TOP 3 — 3년 소모품 포함 총비용 비교",
        category="로봇청소기",
        generated_at="2026-02-07",
        products=products,
        top_products=products[:3],
        situation_picks=[
            SituationPick(
                situation="가성비 중시",
                product_name="로보락 Q Revo S",
                reason="3년 소모품 포함 총비용 1,079,000원으로 최저",
            ),
            SituationPick(
                situation="유지비 최소화",
                product_name="삼성 비스포크 제트 AI",
                reason="연간 소모품비 45,000원 + 삼성 AS",
            ),
            SituationPick(
                situation="올인원 편의성",
                product_name="에코백스 X2 콤보",
                reason="핸디 청소기 일체형",
            ),
        ],
        home_types=[
            HomeType(
                type="소형 원룸/오피스텔",
                recommendation="로보락 Q Revo S — 가성비 좋고 공간 효율적",
            ),
            HomeType(
                type="25평대 아파트",
                recommendation="삼성 비스포크 제트 AI — 유지비 적고 AS 편리",
            ),
            HomeType(
                type="넓은 복층/단독주택",
                recommendation="에코백스 X2 콤보 — 계단은 핸디로 추가 청소 가능",
            ),
        ],
        faqs=[
            FAQ(
                question="로봇청소기 소모품 비용, 실제로 얼마나 들까요?",
                answer="제품별로 연간 4.5~9만원 수준입니다. 필터, 사이드브러시, 먼지봉투가 주요 소모품이며, 호환품을 활용하면 30~50% 절감할 수 있습니다.",
            ),
            FAQ(
                question="호환 소모품을 써도 괜찮나요?",
                answer="필터와 사이드브러시는 호환품 사용이 일반적입니다. 다만 정품 대비 내구성이 다소 떨어질 수 있으니, 교체 주기를 20% 정도 앞당기는 것을 권장합니다.",
            ),
            FAQ(
                question="반려동물 털 청소에 효과적인가요?",
                answer="모든 비교 모델이 펫 모드를 제공합니다. 다만 털이 많은 환경에서는 사이드브러시 교체 주기가 짧아지므로 소모품비가 10~20% 증가할 수 있습니다.",
            ),
        ],
        category_criteria=CategoryCriteria(
            myth_busting="많은 분들이 흡입력 Pa 수치를 비교하지만, 실제 테스트에서 7,000Pa와 11,000Pa의 픽업률 차이는 1~2%에 불과합니다.",
            real_differentiator="2026년 로봇청소기의 진짜 차별점은 소모품 비용과 호환품 활용 가능 여부입니다. 같은 성능이라도 연간 유지비가 2배 차이 날 수 있습니다.",
            decision_fork="소모품비를 아끼려면 호환품이 풍부한 로보락, 유지관리 신경 쓰기 싫다면 삼성을 선택하세요.",
        ),
        credibility=CredibilityStats(
            total_review_count=375,
            price_data_count=3,
            consumable_data_count=9,
        ),
        price_volatility=PriceVolatility(
            min_diff="50,000",
            max_diff="150,000",
            status="평균 대비 저렴한 시기",
            updated_date="2026-02-07",
        ),
        price_updated_date="2026-02-07",
    )


if __name__ == "__main__":
    data = get_sample_blog_data()
    print(f"Title: {data.title}")
    print(f"Category: {data.category}")
    print(f"Products: {len(data.products)}")
    for p in data.products:
        print(f"  - {p.name}: total cost = {p.tco.real_cost_total:,}원 (소모품 연 {p.tco.annual_consumable_cost:,}원)")
