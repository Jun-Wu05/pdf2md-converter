"""Shared pytest fixtures for the pdf2md_full test suite."""
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PUBLIC_FIXTURES = REPO_ROOT / "tests" / "fixtures"

# Public, in-repo sample used by committed (always-run) tests. Already
# published via the upstream firecrawl/pdf-inspector fixtures, so no
# sensitivity concern.
PUBLIC_SAMPLE_PDF = PUBLIC_FIXTURES / "nexo-price-en.pdf"


@pytest.fixture
def sample_pdf() -> str:
    """Absolute path to a public, committed sample PDF (always available)."""
    return str(PUBLIC_SAMPLE_PDF)


@pytest.fixture
def sample_bytes() -> bytes:
    return PUBLIC_SAMPLE_PDF.read_bytes()


# --- Local-only real-world fixtures (sensitive, not in git) ---------------
# Two local-only pools, both gitignored (see .gitignore `*.pdf` rule — no
# `!` exception for these). Tests using them auto-skip when absent so the
# committed suite stays green on clones without the sensitive samples.

R4151_PDF = FIXTURES / "R4.15.1-outbound-config.pdf"

# 7 vendor log/syslog manuals — the real target corpus for this project.
# Lives in fixtures_private/ (gitignored). Used by the issue #3+ regression
# suite; issue #3's AC2 calls for "6 份安全厂商 fixture".
PRIVATE_FIXTURES = pathlib.Path(__file__).parent / "fixtures_private"


def _r4151_available() -> bool:
    return R4151_PDF.exists()


@pytest.fixture
def r4151_pdf() -> str:
    """Absolute path to the local-only R4.15.1 outbound-config fixture.

    Skipped when the file is absent (e.g. on clones without the sensitive
    sample) so committed tests stay green everywhere.
    """
    if not _r4151_available():
        pytest.skip("R4.15.1 fixture not present (local-only sensitive sample)")
    return str(R4151_PDF)


@pytest.fixture
def r4151_bytes() -> bytes:
    if not _r4151_available():
        pytest.skip("R4.15.1 fixture not present (local-only sensitive sample)")
    return R4151_PDF.read_bytes()


def _vendor_pdfs() -> list[pathlib.Path]:
    """All local-only vendor fixture PDFs (sorted, stable order)."""
    if not PRIVATE_FIXTURES.exists():
        return []
    return sorted(PRIVATE_FIXTURES.glob("*.pdf"))


@pytest.fixture
def vendor_pdfs() -> list[str]:
    """Absolute paths to the local-only vendor fixtures (7 security-vendor manuals).

    Skipped when none are present. Used by the multi-vendor regression suite
    (issue #3+ AC2: "6 份安全厂商 fixture"); one extra is tolerated.
    """
    paths = _vendor_pdfs()
    if not paths:
        pytest.skip("vendor fixtures not present (local-only sensitive samples)")
    return [str(p) for p in paths]
