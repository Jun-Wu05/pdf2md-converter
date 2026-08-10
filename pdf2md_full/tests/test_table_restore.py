"""Issue #4 — row cluster & column alignment for wireframe-free field tables.

Seam: ``convert_pdf_to_markdown`` appends a ``## 表格还原`` section containing
rebuilt Markdown tables derived from structured ``TextItem`` coordinates.

AC1: R4.15.1 §5.3 / 微步 field-table regions → standard Markdown table with
     a ``|---|`` separator row.
AC2: first column is a legal field name; field-name column and 说明 column
     correspond one-to-one, no column drift (empty cells stay empty, not
     shifted left).
AC3: column boundaries come from X-coordinate histogram valleys, so uneven
     column widths (narrow field-name / wide description) are honoured.

Fixtures: ``r4151_pdf`` and a 微步 vendor fixture are local-only and auto-skip
when absent. The public ``sample_pdf`` test only asserts the section is
emitted, so the committed suite stays green on every clone.
"""
import re

import pytest

from pdf2md_full import convert_pdf_to_markdown


_SEP_CELL = re.compile(r"^:?-+:?$")


# --- helpers ---------------------------------------------------------------

def _table_restore_section(md: str) -> str:
    idx = md.find("## 表格还原")
    if idx < 0:
        return ""
    return md[idx:]


def _parse_tables(section: str) -> list[list[list[str]]]:
    """Parse markdown tables from a section into list of tables (rows of cells).

    A table is a run of consecutive ``| ... |`` lines. Separator rows
    (cells of only ``-``/``:``) are kept as rows of empty strings so callers
    can locate them, but are excluded from data-row assertions.
    """
    tables: list[list[list[str]]] = []
    cur: list[list[str]] | None = None
    for line in section.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and len(s) >= 3:
            cells = [c.strip() for c in s[1:-1].split("|")]
            if cur is None:
                cur = []
            cur.append(cells)
        else:
            if cur is not None:
                tables.append(cur)
                cur = None
    if cur is not None:
        tables.append(cur)
    return tables


def _data_rows(table: list[list[str]]) -> list[list[str]]:
    """Rows with at least one non-separator cell."""
    return [r for r in table if not all(_SEP_CELL.match(c) for c in r)]


def _has_separator(table: list[list[str]]) -> bool:
    return any(all(_SEP_CELL.match(c) for c in r) for r in table)


# --- section emission (always-run, public fixture) -------------------------

def test_no_spurious_table_section_when_no_field_table(sample_pdf):
    """The public nexo fixture has no wireframe-free 字段表, so #4 must not
    fabricate a ``## 表格还原`` section — the output is just the body."""
    out = convert_pdf_to_markdown(sample_pdf)
    assert isinstance(out, str)
    assert "## 表格还原" not in out


# --- AC1: standard markdown table with |---| separator ---------------------

def test_r4151_rebuilds_table_with_separator(r4151_pdf):
    md = convert_pdf_to_markdown(r4151_pdf)
    tables = _parse_tables(_table_restore_section(md))
    assert tables, "no table rebuilt from R4.15.1"
    assert any(_has_separator(t) for t in tables), "no |---| separator found"


# --- AC2: field-name column ↔ 说明 column correspond, no drift ------------

def test_r4151_type_row_columns_aligned(r4151_pdf):
    """The `Type` row keeps its columns: Type | 日志类型 | 枚举值….

    The Time/IP rows above it have an empty 说明 cell (no third TextItem),
    so a naive left-shift would misalign this row. Asserting col2 holds the
    枚举值 description proves empty cells were preserved as empty, not
    collapsed.
    """
    md = convert_pdf_to_markdown(r4151_pdf)
    tables = _parse_tables(_table_restore_section(md))
    target = None
    for t in tables:
        for r in _data_rows(t):
            if r and r[0] == "Type":
                target = r
                break
        if target:
            break
    assert target is not None, "Type row not found in rebuilt tables"
    assert target[0] == "Type"
    assert target[1] == "日志类型"
    assert len(target) >= 3, f"说明 column lost (got {target})"
    assert target[2].startswith("枚举值"), f"col2 drifted: {target[2]!r}"


# --- AC3: uneven column widths honoured (微步 field table) -----------------

def test_weibu_field_table_columns_aligned(vendor_pdfs):
    """微步 p1 field table: 字段 | 字段名称 | 字段示例说明.

    Column widths are uneven — the 说明 column (e.g. ``192.168.91.241``) is
    far wider than the 字段 column (e.g. ``src_ip``). Asserting src_ip keeps
    说明 in col2 proves the X-histogram-valley boundaries split the data
    x's correctly rather than merging columns. #4 is single-page scope, so
    only the p1 fragment (time…protocol) is asserted; cross-page continuation
    (severity on p2) is #7.
    """
    weibu = [p for p in vendor_pdfs if "微步" in p]
    if not weibu:
        pytest.skip("微步 fixture not present")
    md = convert_pdf_to_markdown(weibu[0])
    tables = _parse_tables(_table_restore_section(md))
    target = None
    for t in tables:
        data = _data_rows(t)
        if data and any("字段" in c for c in data[0]):
            target = data
            break
    assert target, "微步 field table not rebuilt"
    header = target[0]
    assert header[0].startswith("字段"), f"field-name column not first: {header}"
    src_ip = [r for r in target if r and r[0] == "src_ip"]
    assert src_ip, "src_ip row missing — column alignment dropped a row"
    assert src_ip[0][1] == "源 ip", f"col1 drifted: {src_ip[0]}"
    assert len(src_ip[0]) >= 3, f"说明 column lost (got {src_ip[0]})"
    assert src_ip[0][2] == "192.168.91.241", f"col2 drifted: {src_ip[0][2]!r}"


# --- Issue #6: multi-row (vertical-per-char) header merge ------------------
#
# syslog日志对接.pdf uses a 5-column field table whose header AND data cells
# are laid out vertically-per-character: the header 字段名称/字段类型 are
# split across several y-close rows (gap 4–15pt), and each data cell's Chinese
# text is also split into vertically stacked fragments whose y ranges overlap
# with neighbouring data rows. #4's single-row-header, y-gap-based clustering
# mis-splits this into several 2–3 column tables that each re-emit the header.
#
# AC1: the field-table header appears exactly once (one |---| separator per
#      table), column names complete and merged to a single header row.
# AC2: each data row's field name ↔ 说明 ↔ 示例 correspond one-to-one with no
#      cross-row drift (the `id` row's 示例 UUID is whole, not split).
# AC3: SecIPS (single-row header) does not regress — header still single row.


def _secips(vendor_pdfs):
    return [p for p in vendor_pdfs if "SecIPS" in p or "网神" in p]


def _syslog_duijie(vendor_pdfs):
    return [p for p in vendor_pdfs if "syslog" in p.lower() and "对接" in p]


def test_syslog_multirow_header_appears_once(vendor_pdfs):
    """AC1: syslog field-table header emitted exactly once per table.

    #4 splits the vertical-per-char header into multiple tables, each
    re-emitting `| 字段 | 字段 |`. After #6 the header is a single merged
    row with a single |---| separator per table.
    """
    syslog = _syslog_duijie(vendor_pdfs)
    if not syslog:
        pytest.skip("syslog 日志对接 fixture not present")
    md = convert_pdf_to_markdown(syslog[0])
    tables = _parse_tables(_table_restore_section(md))
    # Find a rebuilt field table whose data rows reference real field names.
    field_tables = [
        t for t in tables
        if any(r and r[0] == "id" for r in _data_rows(t))
    ]
    assert field_tables, "syslog field table (with `id` row) not rebuilt"
    target = field_tables[0]
    headers = [
        r for r in target
        if not all(_SEP_CELL.match(c) for c in r) and any("字段" in c for c in r)
    ]
    assert len(headers) == 1, (
        f"header should appear once, got {len(headers)}: {headers}"
    )
    assert _has_separator(target), "no |---| separator on the merged table"


def test_syslog_multirow_data_cells_aligned(vendor_pdfs):
    """AC2: the `id` data row keeps all 5 columns whole, no drift.

    Expected: id | 事件ID | 字符串 | 事件的唯一标识ID | <full UUID>.
    The vertical-per-char fragments of 事件ID / 字符串 / 事件的唯一标识ID
    must be merged within the row, and the split UUID 示例 must be rejoined.
    """
    syslog = _syslog_duijie(vendor_pdfs)
    if not syslog:
        pytest.skip("syslog 日志对接 fixture not present")
    md = convert_pdf_to_markdown(syslog[0])
    tables = _parse_tables(_table_restore_section(md))
    target = None
    for t in tables:
        for r in _data_rows(t):
            if r and r[0] == "id":
                target = t
                break
        if target:
            break
    assert target is not None, "`id` row not found in rebuilt syslog tables"
    id_row = [r for r in _data_rows(target) if r and r[0] == "id"][0]
    assert len(id_row) >= 5, (
        f"id row should have ≥5 columns, got {len(id_row)}: {id_row}"
    )
    assert id_row[0] == "id"
    # col1 = field-name-cn (事件ID), col2 = type (字符串),
    # col3 = 说明 (事件的唯一标识ID), col4 = 示例 (full UUID).
    assert "事件" in id_row[1] and "ID" in id_row[1], (
        f"col1 (字段名称) fragmented: {id_row[1]!r}"
    )
    assert "字符" in id_row[2] and "串" in id_row[2], (
        f"col2 (字段类型) fragmented: {id_row[2]!r}"
    )
    assert id_row[3].startswith("事件的唯一标识"), (
        f"col3 (说明) drifted: {id_row[3]!r}"
    )
    assert "9a60afc9" in id_row[4] and "925dd9" in id_row[4], (
        f"col4 (示例 UUID) split across cells: {id_row[4]!r}"
    )


def test_secips_single_row_header_not_regressed(vendor_pdfs):
    """AC3: SecIPS fields tables keep their clean single-row header.

    SecIPS lays out 字段名 | 类型 | 描述 on one row; #6 must not over-merge
    neighbouring data rows into the header. Each rebuilt table has exactly
    one header row and the devid row stays 3 columns.
    """
    secips = _secips(vendor_pdfs)
    if not secips:
        pytest.skip("SecIPS fixture not present")
    md = convert_pdf_to_markdown(secips[0])
    tables = _parse_tables(_table_restore_section(md))
    target = None
    for t in tables:
        for r in _data_rows(t):
            if r and r[0] == "devid":
                target = t
                break
        if target:
            break
    assert target is not None, "SecIPS devid table not rebuilt"
    headers = [
        r for r in target
        if not all(_SEP_CELL.match(c) for c in r) and any("字段名" in c for c in r)
    ]
    assert len(headers) == 1, f"SecIPS header should be single row: {headers}"
    devid = [r for r in _data_rows(target) if r and r[0] == "devid"][0]
    assert len(devid) == 3, f"devid row should stay 3 columns: {devid}"
    assert devid[1] == "int" and devid[2] == "设备id", f"devid drifted: {devid}"


# --- Issue #7: cross-page continuation table merge & header dedup ----------
#
# R4.15.1 §5.3 is a 4-column field table (字段名 | 中文名称 | 字段类型 | 是否必填)
# that spans page 6 → 7 → 8. Each continuation page re-emits the same header
# row at the *same* column x coordinates (84.5 / 229.6 / 379.5 / 501.9), so #4's
# per-page rebuild produces three separate tables that each re-emit the header.
# #7 merges continuation pages whose header tokens AND column x grid match the
# previous table into one table with a single header / |---| separator.
#
# AC1: the §5.3 table header appears exactly once in the output (one |---|).
# AC2: continuation rows stay continuous — the last page's rows (uuid,
#      triageResult) appear in the same merged table as the first page's rows
#      (seq, name), no half-row truncation.
# AC3: §5.4 (page 8 foot → page 9) re-uses the *same* header text but a
#      *different* column x grid (40.7 / 114.4 / 236.8 / 359.1 — an indented
#      optional-field table). It must NOT be merged into §5.3: it stays a
#      separate table with its own header. Header-text equality alone would
#      wrongly merge them, so the column-x-grid check is the guardrail.


def _r4151_alert_tables(tables):
    """All 4-col 字段名|中文名称|字段类型|是否必填 table fragments (pre- or post-merge)."""
    out = []
    for t in tables:
        data = _data_rows(t)
        if not data:
            continue
        h = data[0]
        if (
            len(h) >= 4
            and h[0].startswith("字段名")
            and "中文名称" in h[1]
            and "字段类型" in h[2]
            and "必填" in h[3]
        ):
            out.append(t)
    return out


def _r4151_s53_table(tables):
    """The §5.3 continuation table: the alert table holding `seq` (page-6 head)."""
    for t in _r4151_alert_tables(tables):
        if any(r and r[0] == "seq" for r in _data_rows(t)):
            return t
    return None


def test_r4151_cross_page_header_emitted_once(r4151_pdf):
    """AC1: §5.3 header appears exactly once across the page-6/7/8 span.

    Before #7 the same `字段名|中文名称|字段类型|是否必填` header is re-emitted
    on each continuation page (3 times). After #7 the continuation pages are
    merged into one table with a single header row and a single |---|.
    """
    md = convert_pdf_to_markdown(r4151_pdf)
    tables = _parse_tables(_table_restore_section(md))
    target = _r4151_s53_table(tables)
    assert target is not None, "§5.3 alert field table (with `seq` row) not rebuilt"
    headers = [
        r for r in target
        if not all(_SEP_CELL.match(c) for c in r) and r[0].startswith("字段名")
    ]
    assert len(headers) == 1, (
        f"§5.3 header should appear once after merge, got {len(headers)}"
    )
    assert _has_separator(target), "no |---| separator on the merged §5.3 table"


def test_r4151_cross_page_rows_continuous(r4151_pdf):
    """AC2: continuation rows land in the same merged table, no truncation.

    `seq`/`name` live on page 6; `uuid`/`triageResult` live on page 8. After
    #7 they all appear in a single §5.3 table — the page-8 tail is not split
    off into its own table with a re-emitted header.
    """
    md = convert_pdf_to_markdown(r4151_pdf)
    tables = _parse_tables(_table_restore_section(md))
    target = _r4151_s53_table(tables)
    assert target is not None, "§5.3 alert field table not rebuilt"
    rows = _data_rows(target)
    field0 = [r[0] for r in rows if r]
    assert "seq" in field0, "page-6 head row `seq` missing from merged table"
    assert "name" in field0, "page-6 row `name` missing from merged table"
    assert "uuid" in field0, "page-8 tail row `uuid` missing — half-row truncation"
    assert "triageResult" in field0, (
        "page-8 tail row `triageResult` missing — half-row truncation"
    )
    # Exactly one |---| separator ⇒ no re-emitted header mid-table.
    seps = [r for r in target if all(_SEP_CELL.match(c) for c in r)]
    assert len(seps) == 1, (
        f"merged §5.3 should have one separator, got {len(seps)} — header re-emitted"
    )


def test_r4151_independent_table_not_merged(r4151_pdf):
    """AC3: §5.4 (same header text, different column x grid) stays separate.

    §5.4's optional-field table re-uses 字段名|中文名称|字段类型|是否必填 but sits
    at a different x grid (page-8 foot, indented). Header-text equality alone
    would merge it into §5.3; the column-x-grid guardrail keeps it distinct.
    `attackerIp` is a §5.4-only row that must NOT appear inside the §5.3 table.
    """
    md = convert_pdf_to_markdown(r4151_pdf)
    tables = _parse_tables(_table_restore_section(md))
    target = _r4151_s53_table(tables)
    assert target is not None, "§5.3 alert field table not rebuilt"
    s53_field0 = [r[0] for r in _data_rows(target) if r]
    assert "attackerIp" not in s53_field0, (
        "§5.4 row `attackerIp` leaked into §5.3 — independent tables wrongly merged"
    )
    assert "victimIp" not in s53_field0, (
        "§5.4 row `victimIp` leaked into §5.3 — independent tables wrongly merged"
    )
    # §5.4 still rebuilt as its own table somewhere in the output.
    has_54 = any(
        any(r and r[0] == "attackerIp" for r in _data_rows(t))
        for t in tables
    )
    assert has_54, "§5.4 optional-field table was dropped (should stay separate)"
