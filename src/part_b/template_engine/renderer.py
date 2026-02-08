"""
Template Renderer for TCO Blog Posts.
Handles Jinja2 template loading and rendering.
"""

import json
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import BlogPostData, Product, TCOData


class TemplateRenderer:
    """
    Renders TCO blog posts using Jinja2 templates.

    Usage:
        renderer = TemplateRenderer()
        markdown = renderer.render(blog_data)
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize the template renderer.

        Args:
            templates_dir: Path to templates directory.
                          Defaults to ./templates relative to this file.
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"

        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, data: BlogPostData) -> str:
        """
        Render a complete blog post from BlogPostData.

        Args:
            data: Complete blog post data structure

        Returns:
            Rendered markdown string
        """
        template = self.env.get_template("blog_post.jinja2")
        context = data.to_template_context()
        return template.render(**context)

    def render_section(self, section_name: str, context: dict[str, Any]) -> str:
        """
        Render a single section template.

        Args:
            section_name: Section template name (e.g., "section_0_hook")
            context: Template variables

        Returns:
            Rendered markdown string
        """
        template = self.env.get_template(f"{section_name}.jinja2")
        return template.render(**context)

    def render_from_dict(self, context: dict[str, Any]) -> str:
        """
        Render a complete blog post from a raw dictionary.

        Args:
            context: Template variables as dictionary

        Returns:
            Rendered markdown string
        """
        template = self.env.get_template("blog_post.jinja2")
        return template.render(**context)


def render_blog_post(data: BlogPostData) -> str:
    """
    Convenience function to render a blog post.

    Args:
        data: Complete blog post data structure

    Returns:
        Rendered markdown string
    """
    renderer = TemplateRenderer()
    return renderer.render(data)


def load_tco_data_from_json(json_path: Path) -> list[Product]:
    """
    Load TCO data from Part A JSON export.

    Args:
        json_path: Path to the TCO JSON file from Part A

    Returns:
        List of Product objects with TCO data
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    products = []
    for p in data.get("products", []):
        tco_data = p.get("tco", {})
        tco = TCOData(
            purchase_price_avg=tco_data.get("purchase_price_avg", 0),
            purchase_price_min=tco_data.get("purchase_price_min", 0),
            resale_value_1yr=tco_data.get("resale_value_1yr", 0),
            resale_value_2yr=tco_data.get("resale_value_2yr", 0),
            resale_value_3yr_plus=tco_data.get("resale_value_3yr_plus", 0),
            expected_repair_cost=tco_data.get("expected_repair_cost", 0),
            real_cost_3yr=tco_data.get("real_cost_3yr", 0),
            as_turnaround_days=tco_data.get("as_turnaround_days", 0),
            monthly_maintenance_minutes=tco_data.get("monthly_maintenance_minutes", 0),
        )

        product = Product(
            product_id=p.get("product_id", ""),
            name=p.get("name", ""),
            brand=p.get("brand", ""),
            release_date=p.get("release_date", ""),
            tco=tco,
        )
        products.append(product)

    return products
