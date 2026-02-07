"""Data models for the content writer module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ToneStyle(str, Enum):
    """Blog tone styles."""
    CONVERSATIONAL = "conversational"  # 친근한 대화체
    EXPERT = "expert"  # 전문가 분석체
    REVIEW = "review"  # 리뷰어 톤


@dataclass
class WriterConfig:
    """Configuration for the content writer."""
    provider: LLMProvider = LLMProvider.OPENAI
    model: str = ""  # Empty = use default from settings
    temperature: float = 0.7
    max_tokens: int = 4096
    tone: ToneStyle = ToneStyle.CONVERSATIONAL
    target_category: str = "로봇청소기"
    min_faq_count: int = 3
    max_faq_count: int = 5


@dataclass
class SectionPrompt:
    """A section-specific prompt for LLM generation."""
    section_name: str
    system_prompt: str
    user_prompt: str
    max_tokens: int = 1024


@dataclass
class GeneratedSection:
    """Result of a single section generation."""
    section_name: str
    content: str
    tokens_used: int = 0


@dataclass
class GenerationResult:
    """Complete blog generation result."""
    sections: list[GeneratedSection] = field(default_factory=list)
    total_tokens: int = 0
    provider: str = ""
    model: str = ""
    success: bool = True
    error: Optional[str] = None
