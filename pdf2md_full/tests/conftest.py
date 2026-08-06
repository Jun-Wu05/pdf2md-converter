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


# --- Local-only real-world fixture (sensitive, not in git) ---------------
R4151_PDF = FIXTURES / "R4.15.1-outbound-config.pdf"


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
