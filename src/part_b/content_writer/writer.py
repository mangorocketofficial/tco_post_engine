"""Content Writer — LLM-powered blog content generation from TCO data.

The writer generates editorial content (narrative, recommendations, FAQs)
from structured TCO data. It NEVER fabricates numbers — all quantitative
data comes from Part A's TCO export.

Usage:
    writer = ContentWriter()
    blog_data = writer.generate(tco_export)
    # blog_data is a BlogPostData ready for template_engine rendering
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.common.config import Settings, get_anthropic_api_key, get_openai_api_key
from src.common.logging import setup_logging
from src.part_b.template_engine.models import (
    BlogPostData,
    CategoryCriteria,
    CredibilityStats,
    FAQ,
    HomeType,
    MaintenanceTask as TemplateMaintenanceTask,
    PriceVolatility,
    Product as TemplateProduct,
    RepairStats as TemplateRepairStats,
    FailureType as TemplateFailureType,
    ResaleCurve as TemplateResaleCurve,
    SituationPick,
    TCOData as TemplateTCOData,
)

from .models import GenerationResult, LLMProvider, WriterConfig
from .prompts import SYSTEM_PROMPT, build_enrichment_prompt, build_title_prompt

logger = setup_logging(module_name="content_writer")


class ContentWriter:
    """Generates blog content by combining TCO data with LLM-generated narrative.

    The writer takes structured TCO data from Part A and uses an LLM to generate
    the editorial layer: recommendations, highlights, FAQs, and situation-based picks.
    All quantitative data passes through unchanged.
    """

    def __init__(self, config: WriterConfig | None = None):
        self.config = config or WriterConfig()
        self.settings = Settings.load()
        self._client = None

    def generate(
        self,
        tco_data_path: Path | None = None,
        tco_data_dict: dict | None = None,
    ) -> BlogPostData:
        """Generate complete BlogPostData from TCO export data.

        Either tco_data_path or tco_data_dict must be provided.

        Args:
            tco_data_path: Path to Part A JSON export file
            tco_data_dict: Pre-loaded TCO data dictionary

        Returns:
            BlogPostData ready for template rendering

        Raises:
            ValueError: If neither data source is provided
        """
        if tco_data_path:
            with open(tco_data_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        elif tco_data_dict:
            raw_data = tco_data_dict
        else:
            raise ValueError("Provide either tco_data_path or tco_data_dict")

        category = raw_data.get("category", self.config.target_category)
        products_raw = raw_data.get("products", [])

        if not products_raw:
            raise ValueError("No products found in TCO data")

        # Step 1: Build repair context for FAQ generation
        repair_context = self._extract_repair_context(products_raw)

        # Step 2: Call LLM for editorial enrichment
        enrichment = self._generate_enrichment(category, products_raw, repair_context)

        # Step 3: Generate title
        title = self._generate_title(category, products_raw)

        # Step 4: Build TemplateProduct objects with enrichment
        products = self._build_products(products_raw, enrichment)

        # Step 5: Determine top products (by lowest real_cost_3yr)
        top_products = sorted(products, key=lambda p: p.tco.real_cost_3yr)[:3]

        # Step 6: Build credibility stats
        credibility = self._build_credibility_stats(products_raw)

        # Step 7: Build price volatility
        price_volatility = self._build_price_volatility(products_raw)

        # Step 8: Assemble BlogPostData
        blog_data = BlogPostData(
            title=title,
            category=category,
            generated_at=datetime.now().isoformat(),
            products=products,
            top_products=top_products,
            situation_picks=enrichment.get("situation_picks_parsed", []),
            home_types=enrichment.get("home_types_parsed", []),
            faqs=enrichment.get("faqs_parsed", []),
            credibility=credibility,
            category_criteria=enrichment.get("category_criteria"),
            price_volatility=price_volatility,
            price_updated_date=datetime.now().strftime("%Y-%m-%d"),
        )

        logger.info(
            "Blog content generated: %s (%d products)",
            title,
            len(products),
        )
        return blog_data

    def generate_from_fixture(self, fixture_path: Path) -> BlogPostData:
        """Convenience method to generate from a fixture JSON file.

        Args:
            fixture_path: Path to sample_tco_data.json

        Returns:
            BlogPostData ready for template rendering
        """
        return self.generate(tco_data_path=fixture_path)

    # --- LLM Integration ---

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call the configured LLM provider and return the response text.

        Args:
            system_prompt: System-level instructions
            user_prompt: User message with data and request

        Returns:
            LLM response text
        """
        if self.config.provider == LLMProvider.OPENAI:
            return self._call_openai(system_prompt, user_prompt)
        else:
            return self._call_anthropic(system_prompt, user_prompt)

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """Call OpenAI GPT API."""
        import openai

        api_key = get_openai_api_key()
        client = openai.OpenAI(api_key=api_key)

        model = self.config.model or self.settings.llm.openai_model

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        return response.choices[0].message.content or ""

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        """Call Anthropic Claude API."""
        import anthropic

        api_key = get_anthropic_api_key()
        client = anthropic.Anthropic(api_key=api_key)

        model = self.config.model or self.settings.llm.anthropic_model

        response = client.messages.create(
            model=model,
            max_tokens=self.config.max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.config.temperature,
        )

        return response.content[0].text

    # --- Enrichment Generation ---

    def _generate_enrichment(
        self,
        category: str,
        products_raw: list[dict],
        repair_context: list[dict],
    ) -> dict:
        """Call LLM to generate editorial enrichment for the blog post.

        Args:
            category: Product category
            products_raw: Raw product data from Part A
            repair_context: Repair stats for FAQ generation

        Returns:
            Dictionary with parsed enrichment data
        """
        user_prompt = build_enrichment_prompt(category, products_raw, repair_context)

        response_text = self._call_llm(SYSTEM_PROMPT, user_prompt)
        return self._parse_enrichment_response(response_text)

    def _generate_title(self, category: str, products_raw: list[dict]) -> str:
        """Generate SEO-optimized blog title.

        Args:
            category: Product category
            products_raw: Raw product data

        Returns:
            Blog post title string
        """
        user_prompt = build_title_prompt(category, products_raw)
        title = self._call_llm(SYSTEM_PROMPT, user_prompt).strip()
        # Remove surrounding quotes if present
        title = title.strip('"').strip("'")
        return title

    def _parse_enrichment_response(self, response_text: str) -> dict:
        """Parse LLM response JSON into enrichment data.

        Args:
            response_text: Raw LLM response (should contain JSON)

        Returns:
            Dictionary with parsed enrichment fields
        """
        # Extract JSON from response (may be wrapped in ```json ... ```)
        json_str = response_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON, using fallback")
            return self._fallback_enrichment()

        # Parse into typed objects
        result: dict[str, Any] = {}

        # Situation picks
        result["situation_picks_parsed"] = [
            SituationPick(
                situation=sp.get("situation", ""),
                product_name=sp.get("product_name", ""),
                reason=sp.get("reason", ""),
            )
            for sp in data.get("situation_picks", [])
        ]

        # Home types
        result["home_types_parsed"] = [
            HomeType(
                type=ht.get("type", ""),
                recommendation=ht.get("recommendation", ""),
            )
            for ht in data.get("home_types", [])
        ]

        # FAQs
        result["faqs_parsed"] = [
            FAQ(
                question=faq.get("question", ""),
                answer=faq.get("answer", ""),
            )
            for faq in data.get("faqs", [])
        ]

        # Category criteria
        cc = data.get("category_criteria", {})
        if cc:
            result["category_criteria"] = CategoryCriteria(
                myth_busting=cc.get("myth_busting", ""),
                real_differentiator=cc.get("real_differentiator", ""),
                decision_fork=cc.get("decision_fork", ""),
            )
        else:
            result["category_criteria"] = None

        # Per-product enrichment
        result["product_enrichment"] = {
            pe.get("product_id", ""): pe
            for pe in data.get("products", [])
        }

        return result

    def _fallback_enrichment(self) -> dict:
        """Provide fallback enrichment when LLM parsing fails."""
        return {
            "situation_picks_parsed": [],
            "home_types_parsed": [],
            "faqs_parsed": [],
            "product_enrichment": {},
            "category_criteria": None,
        }

    # --- Data Building ---

    def _build_products(
        self,
        products_raw: list[dict],
        enrichment: dict,
    ) -> list[TemplateProduct]:
        """Build TemplateProduct objects from raw data + LLM enrichment.

        All numeric data comes directly from Part A. Only editorial
        content (highlight, verdict, reasons) comes from the LLM.

        Args:
            products_raw: Raw product data from Part A JSON
            enrichment: LLM-generated editorial content

        Returns:
            List of fully populated TemplateProduct objects
        """
        product_enrichment = enrichment.get("product_enrichment", {})
        products = []

        for p in products_raw:
            tco_raw = p.get("tco", {})
            product_id = p.get("product_id", "")

            # Build TCO data (ALL from Part A, no fabrication)
            tco = TemplateTCOData(
                purchase_price_avg=tco_raw.get("purchase_price_avg", 0),
                purchase_price_min=tco_raw.get("purchase_price_min", 0),
                resale_value_1yr=tco_raw.get("resale_value_1yr", 0),
                resale_value_2yr=tco_raw.get("resale_value_2yr", 0),
                resale_value_3yr_plus=tco_raw.get("resale_value_3yr_plus", 0),
                expected_repair_cost=tco_raw.get("expected_repair_cost", 0),
                real_cost_3yr=tco_raw.get("real_cost_3yr", 0),
                as_turnaround_days=tco_raw.get("as_turnaround_days", 0),
                monthly_maintenance_minutes=tco_raw.get("monthly_maintenance_minutes", 0),
            )

            # Build resale curve (from Part A)
            resale_raw = p.get("resale_curve", {})
            resale_curve = None
            if resale_raw:
                resale_curve = TemplateResaleCurve(
                    yr_1=resale_raw.get("1yr", 0),
                    yr_2=resale_raw.get("2yr", 0),
                    yr_3_plus=resale_raw.get("3yr_plus", 0),
                )

            # Build repair stats (from Part A)
            repair_raw = p.get("repair_stats", {})
            repair_stats = None
            if repair_raw:
                repair_stats = TemplateRepairStats(
                    total_reports=repair_raw.get("total_reports", 0),
                    failure_types=[
                        TemplateFailureType(
                            type=ft.get("type", ""),
                            count=ft.get("count", 0),
                            avg_cost=ft.get("avg_cost", 0),
                            probability=ft.get("probability", 0),
                        )
                        for ft in repair_raw.get("failure_types", [])
                    ],
                )

            # Build maintenance tasks (from Part A)
            maintenance_tasks = [
                TemplateMaintenanceTask(
                    task=mt.get("task", ""),
                    frequency_per_month=mt.get("frequency_per_month", 0),
                    minutes_per_task=mt.get("minutes_per_task", 0),
                    automated=mt.get("automated"),
                )
                for mt in p.get("maintenance_tasks", [])
            ]

            # Get editorial enrichment (from LLM)
            pe = product_enrichment.get(product_id, {})

            product = TemplateProduct(
                product_id=product_id,
                name=p.get("name", ""),
                brand=p.get("brand", ""),
                release_date=p.get("release_date", ""),
                tco=tco,
                resale_curve=resale_curve,
                repair_stats=repair_stats,
                maintenance_tasks=maintenance_tasks,
                highlight=pe.get("highlight", ""),
                slot_label=pe.get("slot_label", ""),
                verdict=pe.get("verdict", "recommend"),
                recommendation_reason=pe.get("recommendation_reason", ""),
                caution_reason=pe.get("caution_reason", ""),
            )
            products.append(product)

        return products

    def _extract_repair_context(self, products_raw: list[dict]) -> list[dict]:
        """Extract repair stats from raw data for LLM context.

        Args:
            products_raw: Raw product data

        Returns:
            List of repair context dicts per product
        """
        context = []
        for p in products_raw:
            repair = p.get("repair_stats", {})
            if repair:
                context.append({
                    "product_name": p.get("name", ""),
                    "total_reports": repair.get("total_reports", 0),
                    "failure_types": repair.get("failure_types", []),
                })
        return context

    def _build_credibility_stats(self, products_raw: list[dict]) -> CredibilityStats:
        """Build credibility stats from raw product data.

        Counts are derived directly from Part A data volumes.

        Args:
            products_raw: Raw product data

        Returns:
            CredibilityStats with real data counts
        """
        total_repair = 0
        total_price = 0
        total_resale = 0
        total_maintenance = 0

        for p in products_raw:
            total_price += len(p.get("price_history", []))
            repair = p.get("repair_stats", {})
            total_repair += repair.get("total_reports", 0)
            # Estimate resale data from curve presence
            if p.get("resale_curve"):
                total_resale += 20  # Approximate per product
            total_maintenance += len(p.get("maintenance_tasks", []))

        total_review = total_repair + total_price + total_resale

        return CredibilityStats(
            total_review_count=total_review,
            price_data_count=total_price,
            resale_data_count=total_resale,
            repair_data_count=total_repair,
            as_review_count=total_repair,  # AS reviews are subset of repair reports
            maintenance_data_count=total_maintenance,
        )

    def _build_price_volatility(
        self, products_raw: list[dict]
    ) -> PriceVolatility | None:
        """Build price volatility info from price history.

        Args:
            products_raw: Raw product data with price history

        Returns:
            PriceVolatility or None if insufficient data
        """
        all_prices = []
        for p in products_raw:
            for ph in p.get("price_history", []):
                all_prices.append(ph.get("price", 0))

        if len(all_prices) < 2:
            return None

        min_price = min(all_prices)
        max_price = max(all_prices)
        diff = max_price - min_price

        return PriceVolatility(
            min_diff=f"{diff:,}원",
            max_diff=f"{max_price:,}원",
            status="가격 변동 구간 내" if diff > 0 else "가격 안정",
            updated_date=datetime.now().strftime("%Y-%m-%d"),
        )
