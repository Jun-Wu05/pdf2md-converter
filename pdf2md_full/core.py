"""Core implementation of the pdf2md_full post-processing layer.

Issues #4 + #6 — wireframe-free field-table reconstruction, incl. multi-row
(vertical-per-char) header merge.

``convert_pdf_to_markdown`` returns the pdf-inspector body Markdown **plus** a
``## 表格还原`` section: rebuilt Markdown tables derived from the structured
``TextItem`` coordinates (see :mod:`pdf2md_full.tables`). The body itself is
still sourced from ``pdf_inspector.process_pdf`` — these slices only *append*
rebuilt tables, they do not rewrite the body, so the 98% text-completeness
contract inherited from #2 is preserved.

The public entry signature and the text-completeness guarantee are the public
contract; downstream slices swap the body source and insert table-restoration
stages without changing this entry point.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import pdf_inspector

from .garble import annotate_decode_garble
from .tables import rebuild_field_tables


@dataclass
class _Extraction:
    """Internal pipeline state shared across slices.

    ``markdown`` is the body text returned to callers; ``text_items`` is the
    structured intake that #4+ consume. Kept private (leading underscore) —
    only :func:`convert_pdf_to_markdown` and downstream internal stages touch it.
    """

    markdown: str = ""
    text_items: list[Any] = field(default_factory=list)


def convert_pdf_to_markdown(pdf_path: str) -> str:
    """Convert a PDF file at ``pdf_path`` into Markdown.

    Returns the pdf-inspector body Markdown followed by a ``## 表格还原``
    section holding wireframe-free field tables rebuilt from ``TextItem``
    coordinates. For scanned/image-based PDFs the body may be empty but the
    call is never an exception.
    """
    extraction = _convert(pdf_path)
    return _assemble(extraction)


def convert_pdf_to_markdown_bytes(data: bytes) -> str:
    """Bytes-input variant of :func:`convert_pdf_to_markdown`."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    extraction = _convert_bytes(bytes(data))
    return _assemble(extraction)


# --- Internal pipeline ---------------------------------------------------

# Structured-intake seam: downstream slices (#5+) import this to obtain the
# TextItem list without re-running extraction. Named with a leading underscore
# because it is an internal seam, not part of the public API.


def _extract_text_items(pdf_path: str) -> list[Any]:
    """Structured intake: ``TextItem`` list with x/y/font/font_size/page."""
    return pdf_inspector.extract_text_with_positions(pdf_path)


def _convert(pdf_path: str) -> _Extraction:
    _validate_path(pdf_path)
    text_items = _extract_text_items(pdf_path)
    markdown = pdf_inspector.process_pdf(pdf_path).markdown or ""
    return _Extraction(markdown=markdown, text_items=text_items)


def _convert_bytes(data: bytes) -> _Extraction:
    text_items = pdf_inspector.extract_text_with_positions_bytes(data)
    markdown = pdf_inspector.process_pdf_bytes(data).markdown or ""
    return _Extraction(markdown=markdown, text_items=text_items)


def _assemble(extraction: _Extraction) -> str:
    """Body Markdown + rebuilt field-table section (appended, never rewritten).

    The body is annotated for decode-garble (#5) *before* the table section is
    appended — garble lives in the pdf-inspector body, not in the rebuilt
    tables. The rebuilt field-table section is structured output (clean
    column-aligned cells) and is left as-is.
    """
    body = annotate_decode_garble(extraction.markdown)
    tables = rebuild_field_tables(extraction.text_items)
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
