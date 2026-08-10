"""Decode-garble annotation for the pdf2md_full post-processing layer.

Issue #5 — detect CJK decode-garble (tounicode mis-decodes) and mark it
with a ``[疑似解码错误]`` prefix **without** dropping or rewriting the
garble. The original bytes are preserved verbatim; only a marker is
inserted before the offending run.

Context
-------
pdf-inspector's ``tounicode.rs`` occasionally mis-maps a CMap so that an
ASCII payload decodes to a run of low-frequency CJK glyphs. R4.15.1 §5.5
shows the canonical case: an ASCII syslog example rendered as
``入网网日目入日非高入网网日目入日非高入人工高`` — 21 CJK characters drawn
from only ~7 unique glyphs, no punctuation, no ASCII, no spaces.

Detector
--------
Legitimate Chinese prose has near-100% unique-glyph density (e.g.
``日志详细信息`` → 6 unique / 6 total). A tounicode mis-decode produces a
*long CJK run with very low unique-glyph density* — the same few glyphs
repeat. So the fingerprint is:

* a contiguous run of ≥ ``_MIN_RUN`` CJK characters, **and**
* unique-glyph ratio ≤ ``_MAX_UNIQUE_RATIO`` over that run.

Runs that contain ASCII, digits, or CJK punctuation are not pure-garble
candidates and are left alone (``时间字段`` next to ``YYYY-MM-DD`` is
legitimate even if a glyph repeats). The detector scans the text, finds
maximal CJK-only runs, and annotates each qualifying run in place.

Scope
-----
This layer **annotates**, it does not repair. Fixing the tounicode root
cause lives in the Rust kernel (ADR-0001 — out of scope). The contract is:
garble never flows out silently, and the garble text itself is never
altered.
"""
from __future__ import annotations

import re

# CJK Unified Ideographs + a few common extension ranges. Good enough to
# isolate "Asian glyph runs" from ASCII / digits / punctuation in the
# security-vendor corpus; we are not doing full Unicode coverage here.
_CJK = r"[一-鿿㐀-䶿]"
_CJK_RE = re.compile(_CJK)

# A run of ≥ this many CJK characters is long enough for the density test
# to be meaningful. Shorter runs (字段名, 源ip) never qualify.
_MIN_RUN = 6

# Unique-glyph ratio over the run. Real prose sits at ~0.85–1.0; the §5.5
# garble (7 unique / 21 total ≈ 0.33) is far below. 0.5 separates the two
# regimes with margin.
_MAX_UNIQUE_RATIO = 0.5

_MARKER = "[疑似解码错误]"


def _is_garble_run(run: str) -> bool:
    """True if a CJK-only run looks like a tounicode mis-decode."""
    if len(run) < _MIN_RUN:
        return False
    unique = len(set(run))
    return unique / len(run) <= _MAX_UNIQUE_RATIO


def annotate_decode_garble(text: str) -> str:
    """Insert ``[疑似解码错误]`` before each suspected decode-garble run.

    The garble text itself is preserved verbatim — never dropped, never
    rewritten. Returns ``text`` unchanged when no garble is detected
    (including all-legitimate CJK prose, table cells, and ASCII-only text).
    """
    if not text:
        return text
    # Walk maximal CJK-only runs; annotate qualifying ones in place.
    out: list[str] = []
    pos = 0
    for m in re.finditer(rf"{_CJK}+", text):
        start, end = m.span()
        out.append(text[pos:start])  # gap before this run (ASCII/punct/etc.)
        run = m.group()
        if _is_garble_run(run):
            out.append(_MARKER)
        out.append(run)
        pos = end
    out.append(text[pos:])
    return "".join(out)
