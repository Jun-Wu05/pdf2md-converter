"""Core implementation of the pdf2md_full post-processing layer.

Issues #4 + #6 — wireframe-free field-table reconstruction, incl. multi-row
(vertical-per-char) header merge.

``convert_pdf_to_markdown`` returns the pdf-inspector body Markdown **plus** a
``## 表格还原`` section: rebuilt Markdown tables derived from the structured
``TextItem`` coordinates (see :mod:`pdf2md_full.tables`). Markdown and
coordinates arrive together from ``pdf_inspector.process_pdf_with_positions``
after one PDF parse; these slices only *append* rebuilt tables, they do not
rewrite the body, so the 98% text-completeness contract inherited from #2 is
preserved.

The public entry signature and the text-completeness guarantee are the public
contract; downstream slices swap the body source and insert table-restoration
stages without changing this entry point.
"""
from __future__ import annotations

import os
from typing import Any

import pdf_inspector

from .garble import annotate_decode_garble
from .tables import rebuild_field_tables


def convert_pdf_to_markdown(pdf_path: str) -> str:
    """Convert a PDF file at ``pdf_path`` into Markdown.

    Returns the pdf-inspector body Markdown followed by a ``## 表格还原``
    section holding wireframe-free field tables rebuilt from ``TextItem``
    coordinates. For scanned/image-based PDFs the body may be empty but the
    call is never an exception.
    """
    markdown, text_items = _convert(pdf_path)
    return _assemble(markdown, text_items)


def convert_pdf_to_markdown_bytes(data: bytes) -> str:
    """Bytes-input variant of :func:`convert_pdf_to_markdown`."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    markdown, text_items = _convert_bytes(bytes(data))
    return _assemble(markdown, text_items)


# --- Internal pipeline ---------------------------------------------------

# Internal conversion helpers return the two outputs of the combined intake
# directly — ``(markdown, text_items)`` — mirroring the single PDF parse.


def _convert(pdf_path: str) -> tuple[str, list[Any]]:
    _validate_path(pdf_path)
    intake = pdf_inspector.process_pdf_with_positions(pdf_path)
    return (intake.result.markdown or "", intake.text_items)


def _convert_bytes(data: bytes) -> tuple[str, list[Any]]:
    intake = pdf_inspector.process_pdf_with_positions_bytes(data)
    return (intake.result.markdown or "", intake.text_items)


def _assemble(markdown: str, text_items: list[Any]) -> str:
    """Body Markdown + rebuilt field-table section (appended, never rewritten).

    The body is annotated for decode-garble (#5) *before* the table section is
    appended — garble lives in the pdf-inspector body, not in the rebuilt
    tables. The rebuilt field-table section is structured output (clean
    column-aligned cells) and is left as-is.
    """
    body = annotate_decode_garble(markdown)
    tables = rebuild_field_tables(text_items)
    if not tables:
        return body
    section = "## 表格还原\n\n" + "\n\n".join(tables)
    if not body:
        return section
    if body.endswith("\n"):
        return body + "\n" + section
    return body + "\n\n" + section


def _validate_path(pdf_path: str) -> None:
    if not isinstance(pdf_path, str):
        raise TypeError("pdf_path must be a str path")
    if not pdf_path:
        raise ValueError("pdf_path must not be empty")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)
