"""Issue #5 — decode-garble annotation (`[疑似解码错误]`).

Seam: ``convert_pdf_to_markdown`` annotates suspected CJK decode-garble in the
body text without dropping or rewriting the garble — the original bytes are
preserved verbatim with a ``[疑似解码错误]`` marker inserted before the run.

R4.15.1 §5.5 emits a tounicode mis-decode of an ASCII syslog payload as a
run of repeated low-frequency CJK characters (``入网网日目入日非高…``): ~7
unique glyphs in a 21-char run, no punctuation, no ASCII. Legitimate Chinese
prose (``日志详细信息``) has near-100% unique-glyph density, so a low
unique-glyph ratio over a ≥6-char CJK run is the garble fingerprint.

AC1: R4.15.1 §5.5 — the garble run is preceded by ``[疑似解码错误]``.
AC2: the garble run is preserved verbatim (not dropped, not "repaired").
AC3: legitimate CJK prose is not annotated (no false positives).
"""
import pytest

from pdf2md_full import convert_pdf_to_markdown
from pdf2md_full.garble import annotate_decode_garble


# --- unit: garble detector on synthetic strings ---------------------------


def test_garble_run_annotated():
    """A long low-unique-density CJK run gets a marker prepended."""
    text = "正常开头\n入网网日目入日非高入网网日目入日非高入人工高\n正常结尾"
    out = annotate_decode_garble(text)
    assert "[疑似解码错误]" in out
    # original garble preserved verbatim
    assert "入网网日目入日非高入网网日目入日非高入人工高" in out


def test_garble_preserved_verbatim_not_repaired():
    """Garble is left untouched — not dropped, not altered."""
    garble = "入网网日目入日非高入网网日目入日非高"
    out = annotate_decode_garble(garble)
    assert garble in out, "garble must be preserved verbatim"
    assert out.startswith("[疑似解码错误]")


def test_normal_cjk_not_annotated():
    """Legitimate Chinese prose with high unique-glyph density is not flagged."""
    texts = [
        "日志详细信息",
        "系统支持使用syslog协议把系统的的数据发送到第三方设备。",
        "时间字段均转换为 YYYY-MM-DD hh:mm:ss",
        "枚举值：组件日志、运行日志、业务日志、升级日志",
        "上述数据格式目前只支持与TCP/UDP协议发送",
    ]
    for t in texts:
        out = annotate_decode_garble(t)
        assert "[疑似解码错误]" not in out, f"false positive on {t!r}: {out!r}"


def test_short_cjk_not_annotated():
    """Short CJK runs (≤5 chars) are below the garble threshold."""
    assert "[疑似解码错误]" not in annotate_decode_garble("你好你好你")
    assert "[疑似解码错误]" not in annotate_decode_garble("数据源IP")


def test_markdown_table_rows_not_annotated():
    """Rebuilt table cells (field names / types) must not be flagged."""
    table = (
        "| 字段名 | 中文名称 | 字段类型 | 是否必填 |\n"
        "|---|---|---|---|\n"
        "| seq | 告警序列 | Long | 是 |\n"
        "| compromiseState | 失陷状态 | Boolean | 是 |"
    )
    assert "[疑似解码错误]" not in annotate_decode_garble(table)


# --- end-to-end: R4.15.1 §5.5 ---------------------------------------------


def test_r4151_section_55_garble_annotated(r4151_pdf):
    """AC1: R4.15.1 §5.5 garble run is preceded by `[`疑似解码错误`]`."""
    md = convert_pdf_to_markdown(r4151_pdf)
    idx = md.find("5.5")
    assert idx >= 0, "R4.15.1 §5.5 heading not found"
    tail = md[idx:]
    assert "[疑似解码错误]" in tail, "§5.5 garble not annotated"


def test_r4151_section_55_garble_preserved(r4151_pdf):
    """AC2: the §5.5 garble run is preserved verbatim, not dropped/repaired."""
    md = convert_pdf_to_markdown(r4151_pdf)
    # The known garble run from §5.5 (tounicode mis-decode of an ASCII payload).
    assert "入网网日目入日非高" in md, "§5.5 garble run was dropped or altered"


def test_r4151_normal_prose_not_annotated(r4151_pdf):
    """AC3: legitimate CJK prose in R4.15.1 is not falsely annotated."""
    md = convert_pdf_to_markdown(r4151_pdf)
    # The garble marker should appear only near §5.5, not scattered through
    # the body. Count occurrences — a false-positive storm would produce many.
    count = md.count("[疑似解码错误]")
    assert count >= 1, "no garble annotated (AC1 would already catch this)"
    # Heuristic ceiling: the document has exactly one known garble region (§5.5);
    # allow a small margin but reject a false-positive flood.
    assert count <= 5, (
        f"too many `[疑似解码错误]` markers ({count}) — likely false positives"
    )
