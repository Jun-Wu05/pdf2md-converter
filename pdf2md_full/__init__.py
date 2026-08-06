"""pdf2md_full — Python post-processing layer over pdf-inspector.

Public entry point: :func:`convert_pdf_to_markdown`.
See ADR-0001 (docs/adr/0001-table-restoration-in-python.md) for the decision
to keep table-restoration logic in Python rather than the Rust core.
"""

from .core import convert_pdf_to_markdown, convert_pdf_to_markdown_bytes

__all__ = ["convert_pdf_to_markdown", "convert_pdf_to_markdown_bytes"]
