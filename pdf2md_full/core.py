"""Core implementation of the pdf2md_full post-processing layer.

Issue #3 — structured intake slice.

``convert_pdf_to_markdown`` now captures structured ``TextItem`` data via
``pdf_inspector.extract_text_with_positions`` and threads it through an
internal :class:`_Extraction` pipeline object, so downstream slices (#4 row/
column alignment and beyond) can consume coordinates + font metadata without
re-extraction.

The body Markdown is **still sourced from** ``pdf_inspector.process_pdf`` in
this slice. A naive Python coordinate rebuild was probed against the 7 vendor
fixtures and fell under 98% on 3 of them (科来 0.939, ImmunityOne 0.971,
微步 0.972); the missing length is column detection + cross-page merge, which
is the #4 slice's job. Rebuilding it here would silently absorb #4's work, so
the body stays on ``process_pdf`` and the 98% completeness contract inherited
from #2 is preserved unchanged.

The public entry signature and the text-completeness guarantee are the public
contract; downstream slices swap the body source and insert table-restoration
stages without changing this entry point.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import pdf_inspector


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

    Returns the Markdown string. For scanned/image-based PDFs the result may
    be empty (whatever pdf-inspector produced) but is never an exception.

    Structured :class:`TextItem` data is captured into the internal pipeline
    for downstream table-restoration slices; the body text itself still comes
    from ``pdf_inspector.process_pdf`` in this slice.
    """
    extraction = _convert(pdf_path)
    return extraction.markdown


def convert_pdf_to_markdown_bytes(data: bytes) -> str:
    """Bytes-input variant of :func:`convert_pdf_to_markdown`."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    extraction = _convert_bytes(bytes(data))
    return extraction.markdown


# --- Internal pipeline ---------------------------------------------------

# Structured-intake seam: downstream slices (#4+) import this to obtain the
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


def _validate_path(pdf_path: str) -> None:
    if not isinstance(pdf_path, str):
        raise TypeError("pdf_path must be a str path")
    if not pdf_path:
        raise ValueError("pdf_path must not be empty")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)
