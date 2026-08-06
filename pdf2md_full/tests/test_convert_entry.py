"""Issue #2 — scaffolding & text-completeness slice.

Seam: ``convert_pdf_to_markdown`` public entry point.

Tests verify external behaviour only. Each acceptance criterion maps to one
RED→GREEN cycle.

Fixtures
--------
* ``sample_pdf`` / ``sample_bytes`` — a public, committed PDF
  (``tests/fixtures/nexo-price-en.pdf``), so these tests run on every clone.
* ``r4151_pdf`` / ``r4151_bytes`` — a local-only sensitive sample; tests that
  use it auto-skip when the file is absent.

AC3 (scanned/image-based PDF does not raise) is deferred to issue #9, which
introduces the real multi-vendor + scanned fixtures; faking a scanned PDF
here would test imagination, not behaviour.
"""
import pdf_inspector

from pdf2md_full import convert_pdf_to_markdown, convert_pdf_to_markdown_bytes


# --- AC1: public entry points exist and return str -----------------------
# Using the public, always-available fixture keeps the committed suite green.

def test_convert_pdf_to_markdown_returns_str(sample_pdf):
    result = convert_pdf_to_markdown(sample_pdf)
    assert isinstance(result, str)


def test_convert_pdf_to_markdown_bytes_returns_str(sample_bytes):
    result = convert_pdf_to_markdown_bytes(sample_bytes)
    assert isinstance(result, str)


# --- AC2: text completeness >= 98% of pdf-inspector baseline --------------

def test_text_completeness_at_least_98_percent(sample_pdf):
    baseline = pdf_inspector.process_pdf(sample_pdf).markdown or ""
    converted = convert_pdf_to_markdown(sample_pdf)
    assert len(converted) >= 0.98 * len(baseline)


# --- Real-world regression (local-only, skipped when absent) -------------

def test_text_completeness_r4151_local(r4151_pdf):
    """Regression against the real R4.15.1 document when it is present."""
    baseline = pdf_inspector.process_pdf(r4151_pdf).markdown or ""
    converted = convert_pdf_to_markdown(r4151_pdf)
    assert len(converted) >= 0.98 * len(baseline)
