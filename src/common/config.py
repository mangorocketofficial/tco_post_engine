"""Project configuration and paths.

Loads settings from config/settings.yaml and environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# === Paths ===
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
DATA_EXPORTS_DIR = DATA_DIR / "exports"

# Load .env from project root
load_dotenv(PROJECT_ROOT / ".env")


class ScraperSettings(BaseModel):
    """Settings for web scrapers."""
    request_delay_seconds: float = 2.0
    max_retries: int = 3
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
    proxy_enabled: bool = False
    cache_raw_html: bool = True


class DatabaseSettings(BaseModel):
    """Database connection settings."""
    db_path: str = str(DATA_DIR / "tco_engine.db")


class LLMSettings(BaseModel):
    """LLM API settings."""
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 4096
    temperature: float = 0.7


class Settings(BaseModel):
    """Top-level application settings."""
    scraper: ScraperSettings = Field(default_factory=ScraperSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    default_category: str = "로봇청소기"

    @classmethod
    def load(cls) -> Settings:
        """Load settings from config/settings.yaml, falling back to defaults."""
        settings_path = CONFIG_DIR / "settings.yaml"
        if settings_path.exists():
            with open(settings_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return cls(**data)
        return cls()


def get_openai_api_key() -> str:
    """Get OpenAI API key from environment."""
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise ValueError("OPENAI_API_KEY not set in environment")
    return key


def get_anthropic_api_key() -> str:
    """Get Anthropic API key from environment."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")
    return key


# Singleton settings instance
settings = Settings.load()
