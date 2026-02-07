"""Configuration management for Part A modules."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass
class Config:
    """Central configuration loaded from environment variables."""

    # Database
    database_path: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_PATH", "data/tco_engine.db"
        )
    )

    # Scraping
    proxy_list: list[str] = field(default_factory=list)
    request_timeout: int = 30
    rate_limit_rpm: int = 20

    # Cache
    raw_html_cache_dir: str = field(
        default_factory=lambda: os.getenv(
            "RAW_HTML_CACHE_DIR", "data/raw_html"
        )
    )

    # Danawa
    danawa_base_url: str = "https://prod.danawa.com"

    # Danggeun
    danggeun_base_url: str = "https://www.daangn.com"

    # Naver Shopping
    naver_shopping_base_url: str = "https://search.shopping.naver.com"

    # Coupang
    coupang_base_url: str = "https://www.coupang.com"

    # Naver API (DataLab, Shopping Search, etc.)
    naver_datalab_client_id: str = field(
        default_factory=lambda: os.getenv("NAVER_DATALAB_CLIENT_ID")
        or os.getenv("NAVER_CLIENT_ID", "")
    )
    naver_datalab_client_secret: str = field(
        default_factory=lambda: os.getenv("NAVER_DATALAB_CLIENT_SECRET")
        or os.getenv("NAVER_CLIENT_SECRET", "")
    )

    def __post_init__(self) -> None:
        """Load overrides from environment."""
        if timeout := os.getenv("REQUEST_TIMEOUT"):
            self.request_timeout = int(timeout)
        if rpm := os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE"):
            self.rate_limit_rpm = int(rpm)
        if proxies := os.getenv("PROXY_LIST"):
            self.proxy_list = [p.strip() for p in proxies.split(",") if p.strip()]
        if url := os.getenv("DANAWA_BASE_URL"):
            self.danawa_base_url = url
        if url := os.getenv("DANGGEUN_BASE_URL"):
            self.danggeun_base_url = url
        if url := os.getenv("NAVER_SHOPPING_BASE_URL"):
            self.naver_shopping_base_url = url
        if url := os.getenv("COUPANG_BASE_URL"):
            self.coupang_base_url = url

    @property
    def database_abs_path(self) -> Path:
        """Resolve database path relative to project root."""
        p = Path(self.database_path)
        if p.is_absolute():
            return p
        return _PROJECT_ROOT / p

    @property
    def raw_html_cache_abs_dir(self) -> Path:
        """Resolve raw HTML cache dir relative to project root."""
        p = Path(self.raw_html_cache_dir)
        if p.is_absolute():
            return p
        return _PROJECT_ROOT / p
