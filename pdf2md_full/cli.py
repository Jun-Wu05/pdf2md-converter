"""Command-line entry point for the full PDF-to-Markdown pipeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .core import convert_pdf_to_markdown


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf2md-full",
        description="Convert a PDF to Markdown with pdf2md_full post-processing.",
    )
    parser.add_argument("pdf", type=Path, help="path to the input PDF")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="write Markdown to this UTF-8 file instead of stdout",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI and return a process exit status."""
    args = _parser().parse_args(argv)
    try:
        markdown = convert_pdf_to_markdown(str(args.pdf))
        if args.output is None:
            sys.stdout.write(markdown)
        else:
            args.output.write_text(markdown, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - CLI must report conversion failures.
        print(f"pdf2md-full: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
