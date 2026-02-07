"""Structured logging configuration for TCO Post Engine."""

from __future__ import annotations

import logging
import sys


def setup_logging(
    level: int = logging.INFO,
    module_name: str = "tco_engine",
) -> logging.Logger:
    """Configure and return a logger with consistent formatting.

    Args:
        level: Logging level (default INFO).
        module_name: Name for the logger instance.

    Returns:
        Configured logger.
    """
    logger = logging.getLogger(module_name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
