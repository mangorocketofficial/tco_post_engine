# Template Engine Module
# Jinja2 blog structure templates with variable slots

from .renderer import TemplateRenderer, render_blog_post, load_tco_data_from_json
from .models import (
    BlogPostData,
    CredibilityStats,
    FAQ,
    HomeType,
    MaintenanceTask,
    PriceVolatility,
    Product,
    ResaleCurve,
    SituationPick,
    TCOData,
)

__all__ = [
    "TemplateRenderer",
    "render_blog_post",
    "load_tco_data_from_json",
    "BlogPostData",
    "CredibilityStats",
    "FAQ",
    "HomeType",
    "MaintenanceTask",
    "PriceVolatility",
    "Product",
    "ResaleCurve",
    "SituationPick",
    "TCOData",
]
