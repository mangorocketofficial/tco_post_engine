"""
Sample blog post data for template testing.
Matches the api-contract.json schema with added content fields.
"""

from src.part_b.template_engine.models import (
    BlogPostData,
    CredibilityStats,
    FAQ,
    HomeType,
    PriceVolatility,
    Product,
    ResaleCurve,
    SituationPick,
    TCOData,
)


def get_sample_products() -> list[Product]:
    """Create sample product list with TCO data."""
    return [
        Product(
            product_id="roborock-q-revo-s",
            name="로보락 Q Revo S",
            brand="로보락",
            release_date="2024-03-15",
            tco=TCOData(
                purchase_price_avg=899000,
                purchase_price_min=849000,
                resale_value_24mo=450000,
                expected_repair_cost=85000,
                real_cost_3yr=534000,
                as_turnaround_days=5.2,
                monthly_maintenance_minutes=10,
            ),
            resale_curve=ResaleCurve(mo_6=85, mo_12=72, mo_18=60, mo_24=50),
            cta_link="https://link.coupang.com/roborock-q-revo-s?utm_source=tco_blog",
            highlight="3년 실비용 최저, 가성비 최강",
            verdict="recommend",
            recommendation_reason="3년 실사용 비용이 534,000원으로 가장 낮고, 중고가 보존율도 양호합니다. AS 소요일도 5일로 적당한 편입니다.",
        ),
        Product(
            product_id="samsung-bespoke-jet-ai",
            name="삼성 비스포크 제트 AI",
            brand="삼성",
            release_date="2024-06-01",
            tco=TCOData(
                purchase_price_avg=1290000,
                purchase_price_min=1190000,
                resale_value_24mo=650000,
                expected_repair_cost=45000,
                real_cost_3yr=685000,
                as_turnaround_days=3.1,
                monthly_maintenance_minutes=5,
            ),
            resale_curve=ResaleCurve(mo_6=88, mo_12=75, mo_18=62, mo_24=50),
            cta_link="https://link.coupang.com/samsung-bespoke-jet-ai?utm_source=tco_blog",
            highlight="AS 최단 3일, 유지관리 최소",
            verdict="recommend",
            recommendation_reason="삼성 AS망 덕분에 수리 기간이 3.1일로 가장 짧습니다. 월 유지관리 시간도 5분으로 가장 적어 바쁜 분들께 추천합니다.",
        ),
        Product(
            product_id="ecovacs-x2-combo",
            name="에코백스 X2 콤보",
            brand="에코백스",
            release_date="2024-09-10",
            tco=TCOData(
                purchase_price_avg=1490000,
                purchase_price_min=1390000,
                resale_value_24mo=700000,
                expected_repair_cost=120000,
                real_cost_3yr=910000,
                as_turnaround_days=8.5,
                monthly_maintenance_minutes=15,
            ),
            resale_curve=ResaleCurve(mo_6=82, mo_12=68, mo_18=55, mo_24=47),
            cta_link="https://link.coupang.com/ecovacs-x2-combo?utm_source=tco_blog",
            highlight="핸디+로봇 올인원",
            verdict="caution",
            caution_reason="핸디 청소기 일체형으로 편리하지만, 3년 실비용이 91만원으로 가장 높습니다. AS 소요일도 8.5일로 긴 편이니 여유 있는 분께 맞습니다.",
        ),
    ]


def get_sample_blog_data() -> BlogPostData:
    """Create complete sample BlogPostData for template testing."""
    products = get_sample_products()

    return BlogPostData(
        title="2026년 로봇청소기 추천 TOP 3 — 3년 실비용 비교 분석",
        category="로봇청소기",
        generated_at="2026-02-07",
        products=products,
        top_products=products[:3],  # All 3 are top picks
        situation_picks=[
            SituationPick(
                situation="가성비 중시",
                product_name="로보락 Q Revo S",
                reason="3년 실비용 534,000원으로 최저",
            ),
            SituationPick(
                situation="AS/유지관리 최소화",
                product_name="삼성 비스포크 제트 AI",
                reason="AS 3일 + 월 유지관리 5분",
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
                recommendation="삼성 비스포크 제트 AI — AS 편하고 유지관리 적음",
            ),
            HomeType(
                type="넓은 복층/단독주택",
                recommendation="에코백스 X2 콤보 — 계단은 핸디로 추가 청소 가능",
            ),
        ],
        faqs=[
            FAQ(
                question="로봇청소기 물걸레 기능, 진짜 쓸만한가요?",
                answer="자동 세척 스테이션이 있는 모델(로보락, 삼성)은 위생적으로 사용 가능합니다. 단, 기름기나 찌든 때는 손걸레가 필요합니다. 일상적인 먼지 제거 + 가벼운 물청소 용도로 활용하세요.",
            ),
            FAQ(
                question="중고로 팔 때 가격이 얼마나 떨어지나요?",
                answer="브랜드와 모델에 따라 다릅니다. 분석 결과, 삼성과 로보락은 2년 후에도 50% 가치를 유지하지만, 일부 중국 브랜드는 40% 미만으로 떨어지는 경우도 있습니다.",
            ),
            FAQ(
                question="AS 기간 동안 청소는 어떻게 하나요?",
                answer="AS 평균 소요일이 3~8일인 점을 감안해 대체 청소 계획을 세우세요. 삼성은 전국 서비스센터가 많아 가장 빠르고, 해외 브랜드는 부품 수급에 시간이 걸릴 수 있습니다.",
            ),
            FAQ(
                question="배터리 교체 비용은 얼마인가요?",
                answer="브랜드별로 15~20만원 사이입니다. 보통 2~3년 사용 후 교체가 필요하며, 이 비용은 예상 수리비에 포함되어 있습니다.",
            ),
            FAQ(
                question="반려동물 털 청소에 효과적인가요?",
                answer="모든 비교 모델이 펫 모드 또는 흡입력 강화 기능을 제공합니다. 다만 브러시에 털이 감기는 건 피할 수 없으니, 주 1회 브러시 청소를 권장합니다.",
            ),
        ],
        credibility=CredibilityStats(
            total_review_count=372,
            price_data_count=450,
            resale_data_count=89,
            repair_data_count=156,
            as_review_count=67,
            maintenance_data_count=45,
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
    # Test: Print sample blog data structure
    data = get_sample_blog_data()
    print(f"Title: {data.title}")
    print(f"Category: {data.category}")
    print(f"Products: {len(data.products)}")
    for p in data.products:
        print(f"  - {p.name}: 3yr cost = {p.tco.real_cost_3yr:,}원")
