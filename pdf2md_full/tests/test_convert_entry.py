"""Issue #3 — structured extraction intake slice.

Seam: ``convert_pdf_to_markdown`` consumes a single combined intake that
returns body Markdown plus structured ``TextItem`` data from one PDF parse,
threaded through an internal ``_Extraction`` pipeline object for downstream
slices (#4+).

Tests verify external behaviour only. Each acceptance criterion maps to one
RED→GREEN cycle.

Fixtures
--------
* ``sample_pdf`` / ``sample_bytes`` — public, committed PDF; always-run.
* ``r4151_pdf`` — local-only; auto-skip when absent.
* ``vendor_pdfs`` — local-only 7 vendor manuals; auto-skip when absent.

AC1 (structured TextItems captured into internal pipeline) — covered here.
AC2 (6 vendor fixtures, completeness >= 98% of pdf-inspector baseline) —
covered by the vendor regression test below (one extra vendor tolerated).
AC3 (each TextItem has x/y/font/font_size/page) — covered here.
"""
import pdf_inspector
import pytest

pytestmark = pytest.mark.skipif(
    not hasattr(pdf_inspector, "process_pdf_with_positions"),
    reason="requires a rebuilt pdf_inspector extension",
)

from pdf2md_full import convert_pdf_to_markdown, convert_pdf_to_markdown_bytes
from pdf2md_full.core import _convert


# --- AC1: structured TextItems captured into the internal pipeline --------

def test_internal_extraction_holds_text_items(sample_pdf):
    """``_convert`` returns ``(markdown, text_items)`` from the combined intake."""
    markdown, text_items = _convert(sample_pdf)
    assert text_items, "structured intake produced no TextItems"
    assert markdown, "body markdown should be non-empty for sample"


def test_internal_extraction_text_items_match_combined_intake(sample_pdf):
    """The pipeline consumes the single combined conversion intake."""
    direct = pdf_inspector.process_pdf_with_positions(sample_pdf)
    _, text_items = _convert(sample_pdf)
    assert len(text_items) == len(direct.text_items)
    assert text_items[0].text == direct.text_items[0].text
    assert text_items[0].x == direct.text_items[0].x


def test_convert_uses_single_combined_intake(monkeypatch, sample_pdf):
    """The internal pipeline does not fall back to either legacy binding."""

    class Result:
        markdown = "single parse body"

    class Intake:
        result = Result()
        text_items = []

    monkeypatch.setattr(pdf_inspector, "process_pdf_with_positions", lambda _: Intake())
    monkeypatch.setattr(
        pdf_inspector,
        "process_pdf",
        lambda *_: (_ for _ in ()).throw(AssertionError("legacy process_pdf called")),
    )
    monkeypatch.setattr(
        pdf_inspector,
        "extract_text_with_positions",
        lambda *_: (_ for _ in ()).throw(AssertionError("legacy positions called")),
    )

    markdown, text_items = _convert(sample_pdf)
    assert markdown == "single parse body"
    assert text_items == []


def test_convert_pdf_to_markdown_returns_str(sample_pdf):
    # Regression of #2's public contract under the new intake path.
    result = convert_pdf_to_markdown(sample_pdf)
    assert isinstance(result, str)


def test_convert_pdf_to_markdown_bytes_returns_str(sample_bytes):
    result = convert_pdf_to_markdown_bytes(sample_bytes)
    assert isinstance(result, str)


# --- AC3: every TextItem carries the required fields ----------------------

_REQUIRED_FIELDS = ("x", "y", "font", "font_size", "page")


def test_text_items_carry_required_fields(sample_pdf):
    items = pdf_inspector.extract_text_with_positions(sample_pdf)
    assert items, "no TextItems extracted from sample"
    for it in items:
        for name in _REQUIRED_FIELDS:
            assert hasattr(it, name), f"TextItem missing field {name}"


def test_internal_extraction_items_carry_required_fields(sample_pdf):
    _, text_items = _convert(sample_pdf)
    for it in text_items:
        for name in _REQUIRED_FIELDS:
            assert hasattr(it, name), f"pipeline TextItem missing field {name}"


# --- AC2: 6 vendor fixtures, completeness >= 98% of baseline --------------

def test_text_completeness_at_least_98_percent(sample_pdf):
    # Public-fixture guard for the 98% contract inherited from #2.
    baseline = pdf_inspector.process_pdf(sample_pdf).markdown or ""
    converted = convert_pdf_to_markdown(sample_pdf)
    assert len(converted) >= 0.98 * len(baseline)


def test_text_completeness_r4151_local(r4151_pdf):
    """Regression against the real R4.15.1 document when it is present."""
    baseline = pdf_inspector.process_pdf(r4151_pdf).markdown or ""
    converted = convert_pdf_to_markdown(r4151_pdf)
    assert len(converted) >= 0.98 * len(baseline)


def test_text_completeness_vendor_fixtures(vendor_pdfs):
    """AC2: each vendor fixture keeps >= 98% of pdf-inspector baseline length.

    Uses the local-only 7 security-vendor manuals (>= 6 required by the AC;
    one extra is tolerated). Skipped on clones without the sensitive samples.
    """
    assert len(vendor_pdfs) >= 6, f"AC2 needs >=6 vendor fixtures, got {len(vendor_pdfs)}"
    under = []
    empty = []
    for pdf_path in vendor_pdfs:
        baseline = pdf_inspector.process_pdf(pdf_path).markdown or ""
        converted = convert_pdf_to_markdown(pdf_path)
        if not converted:
            empty.append(pdf_path)
        ratio = len(converted) / len(baseline) if baseline else 1.0
        if ratio < 0.98:
            under.append((pdf_path, ratio))
    assert not empty, f"empty output on: {empty}"
    assert not under, f"completeness < 98% on: {under}"
