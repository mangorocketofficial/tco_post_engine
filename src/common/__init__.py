# Common utilities and shared modules
"""
Shared components used by both Part A and Part B:
- Data models (Pydantic schemas)
- Database utilities
- Logging configuration
- Project configuration
"""

from .config import settings, PROJECT_ROOT, DATA_DIR
from .database import get_connection, init_db
from .logging import setup_logging

__all__ = [
    "settings",
    "PROJECT_ROOT",
    "DATA_DIR",
    "get_connection",
    "init_db",
    "setup_logging",
]
