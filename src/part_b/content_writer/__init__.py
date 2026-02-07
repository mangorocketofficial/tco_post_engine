# Content Writer — GPT/Claude writer with tone guide + data insertion rules
"""
Content Writer module for generating Korean blog content from TCO data.

The writer uses LLM APIs (GPT-4o or Claude) to generate editorial content
while preserving all quantitative data from Part A unchanged.
"""

from .models import GenerationResult, LLMProvider, WriterConfig
from .prompts import SYSTEM_PROMPT, build_enrichment_prompt, build_title_prompt
from .writer import ContentWriter

__all__ = [
    "ContentWriter",
    "GenerationResult",
    "LLMProvider",
    "WriterConfig",
    "SYSTEM_PROMPT",
    "build_enrichment_prompt",
    "build_title_prompt",
]
