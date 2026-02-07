"""CLI entry point for content generation.

Usage:
    python -m src.part_b.content_writer.main --category "로봇청소기"
    python -m src.part_b.content_writer.main --input fixtures/sample_tco_data.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.common.config import PROJECT_ROOT, DATA_EXPORTS_DIR
from src.common.logging import setup_logging
from src.part_b.template_engine import render_blog_post

from .models import LLMProvider, WriterConfig
from .writer import ContentWriter

logger = setup_logging(module_name="content_writer.main")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TCO blog post content")
    parser.add_argument(
        "--category",
        default="로봇청소기",
        help="Product category (default: 로봇청소기)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to TCO data JSON (Part A export)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for rendered blog post markdown",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic"],
        default="openai",
        help="LLM provider (default: openai)",
    )

    args = parser.parse_args()

    # Determine input path
    input_path = args.input
    if input_path is None:
        input_path = PROJECT_ROOT / "fixtures" / "sample_tco_data.json"
        if not input_path.exists():
            logger.error("No input file specified and sample fixture not found")
            sys.exit(1)
        logger.info("Using sample fixture: %s", input_path)

    # Configure writer
    config = WriterConfig(
        provider=LLMProvider(args.provider),
        target_category=args.category,
    )

    # Generate content
    writer = ContentWriter(config=config)
    blog_data = writer.generate(tco_data_path=input_path)

    # Render with template engine
    rendered = render_blog_post(blog_data)

    # Write output
    if args.output:
        output_path = args.output
    else:
        output_path = DATA_EXPORTS_DIR / f"blog_{args.category}_{blog_data.generated_at[:10]}.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    logger.info("Blog post written to: %s", output_path)
    print(f"\nGenerated blog post: {output_path}")


if __name__ == "__main__":
    main()
