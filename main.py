"""AI Interior Product Binder Generator — CLI entry point.

Usage:
    python main.py examples/example_basic.xlsx
    python main.py schedule.xlsx --output output/binder.pdf --project-name "..." --prepared-by "..."
"""

import argparse
import os
import sys

from dotenv import load_dotenv

import config
from src import pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an interior product binder PDF from a schedule .xlsx"
    )
    parser.add_argument("input_xlsx", help="Path to the schedule spreadsheet (.xlsx)")
    parser.add_argument(
        "--output",
        default=None,
        help="Output PDF path (default: output/<project>__<company>__<timestamp>.pdf)",
    )
    parser.add_argument(
        "--project-name", default="Untitled Project", help="Project name for the cover page"
    )
    parser.add_argument(
        "--prepared-by",
        default=None,
        help="'Prepared by' line for the cover page (defaults to COMPANY_NAME from .env)",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=None,
        help=f"Max images per product (default {config.MAX_IMAGES_PER_PRODUCT})",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY is not set.\n"
            "Copy .env.example to .env and fill in your Anthropic API key."
        )
        return 1

    args = parse_args()
    prepared_by = args.prepared_by or os.environ.get("COMPANY_NAME", "")
    if args.max_images is not None:
        config.MAX_IMAGES_PER_PRODUCT = args.max_images

    if not os.path.exists(args.input_xlsx):
        print(f"ERROR: input file not found: {args.input_xlsx}")
        return 1

    # Auto-name a unique output file per run unless the user set one explicitly.
    output_path = args.output or (
        pipeline.unique_output_base(args.project_name, prepared_by) + ".pdf"
    )

    try:
        results = pipeline.generate_from_xlsx(
            args.input_xlsx, output_path, args.project_name, prepared_by
        )
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1
    except PermissionError:
        print(
            f"ERROR: cannot read '{args.input_xlsx}' — it may be open in Excel. "
            "Close it and try again."
        )
        return 1

    failed = [r for r in results if r.error]
    print(
        f"\nDone. {len(results)} product group(s): "
        f"{len(results) - len(failed)} succeeded, {len(failed)} failed."
    )
    for r in failed:
        print(f"  FAILED {', '.join(r.product.keys)}: {r.error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
