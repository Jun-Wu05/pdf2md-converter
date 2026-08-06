"""Core implementation of the pdf2md_full post-processing layer.

Issue #2 — scaffolding slice (tracer-bullet).

This is the ``convert_pdf_to_markdown`` **direct-passthrough** version: it
delegates to ``pdf_inspector.process_pdf`` and returns its ``markdown`` field
verbatim. No table restoration, no garble annotation — those land in later
slices (#3–#9) and replace/extend stages of this pipeline.

The function signature and the text-completeness guarantee are the public
contract; downstream slices swap the internal extraction source (issue #3)
and insert table-restoration stages without changing this entry point.
"""
from __future__ import annotations

import os

import pdf_inspector


def convert_pdf_to_markdown(pdf_path: str) -> str:
    """Convert a PDF file at ``pdf_path`` into Markdown.

    Returns the Markdown string. For scanned/image-based PDFs the result may
    be empty (whatever pdf-inspector produced) but is never an exception.
    """
    _validate_path(pdf_path)
    result = pdf_inspector.process_pdf(pdf_path)
    return result.markdown or ""


def convert_pdf_to_markdown_bytes(data: bytes) -> str:
    """Bytes-input variant of :func:`convert_pdf_to_markdown`."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    result = pdf_inspector.process_pdf_bytes(bytes(data))
    return result.markdown or ""


def _validate_path(pdf_path: str) -> None:
    if not isinstance(pdf_path, str):
        raise TypeError("pdf_path must be a str path")
    if not pdf_path:
        raise ValueError("pdf_path must not be empty")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)
