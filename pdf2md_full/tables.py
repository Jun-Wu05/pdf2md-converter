"""Wireframe-free field-table reconstruction from structured TextItems.

Issues #4 + #6 — row cluster, column alignment, and multi-row header merge.

A *field table* (字段表) is the security-vendor convention of listing log
fields as ``字段 | 字段名称 | 说明`` (or 4–5-column variants) with **no ruling
lines** — pdf-inspector's rect/line table detectors cannot see it, so the
body Markdown comes out garbled. This module rebuilds such tables from
``TextItem`` coordinates.

Two layout sub-types are handled:

1. **Single-row header, uneven widths** (#4, e.g. R4.15.1 / 微步 / SecIPS):
   the header sits on one y; data rows follow at a regular y-spacing. Columns
   are derived from the X-histogram valleys of the data items.

2. **Vertical-per-char header & cells** (#6, e.g. syslog日志对接): the header
   *and* each data cell's Chinese text are split into vertically stacked
   fragments whose y-ranges overlap with neighbouring data rows. A single
   y-gap threshold cannot separate "wrap continuation" from "new data row"
   (微步's 15.6pt row spacing overlaps syslog's 7–15pt vertical-fragment
   gaps), so clustering is **column-first**: items are bucketed by X into
   columns, fragments within a column are merged by y, and data-row
   boundaries are anchored on the leftmost (field-name) column.

Scope: field tables are rebuilt on a page basis, with same-grid continuation
pages merged by #7. When the single-row path has no unique modal column count,
#8 emits a zero-loss definition list instead of inventing a Markdown grid.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_Y_TOL = 3.0
# A y-gap larger than this ends a table (normal row spacing is ~18–32pt).
_GAP_THRESHOLD = 40.0
# Items whose x-centres fall within this many points are treated as the same
# column. Column centres are derived from the data-item x histogram, so this
# only needs to absorb per-item x jitter, not separate columns.
_X_COL_TOL = 18.0


# --- physical-row clustering (#4) ------------------------------------------


def _cluster_rows(items: list[Any]) -> list[tuple[int, list[Any]]]:
    """Group items by page, then by y within ``_Y_TOL``; rows top→bottom."""
    by_page: dict[int, list[Any]] = {}
    for it in items:
        by_page.setdefault(it.page, []).append(it)
    rows: list[tuple[int, list[Any]]] = []
    for page in sorted(by_page):
        its = sorted(by_page[page], key=lambda i: (-i.y, i.x))
        anchor = None
        cur: list[Any] | None = None
        for it in its:
            if cur is None or abs(it.y - anchor) > _Y_TOL:
                cur = [it]
                anchor = it.y
                rows.append((page, cur))
            else:
                cur.append(it)
    for _, r in rows:
        r.sort(key=lambda i: i.x)
    return rows


# --- header detection ------------------------------------------------------


def _is_field_header(row: list[Any]) -> bool:
    """A field-table header: ≥2 items, one of which contains ``字段``."""
    if len(row) < 2:
        return False
    return any("字段" in it.text for it in row)


# --- column boundaries from X-histogram valleys (#4) -----------------------


def _column_boundaries(data_xs: list[float], k: int) -> list[float]:
    """Return ``k-1`` x boundaries that split data x's into ``k`` columns.

    Boundaries are placed at the ``k-1`` largest gaps between sorted data
    x's — the histogram valleys. Falls back to evenly spaced boundaries
    when the data is degenerate (fewer distinct x's than columns).
    """
    if k <= 1 or not data_xs:
        return []
    xs = sorted(data_xs)
    if len(xs) == 1:
        return []
    gaps = sorted(
        range(len(xs) - 1),
        key=lambda i: xs[i + 1] - xs[i],
        reverse=True,
    )
    split_idx = sorted(gaps[: k - 1])
    boundaries = [(xs[i] + xs[i + 1]) / 2 for i in split_idx]
    return sorted(boundaries)


def _assign_column(x: float, boundaries: list[float]) -> int:
    col = 0
    for b in boundaries:
        if x >= b:
            col += 1
        else:
            break
    return col


def _cluster_x_centres(xs: list[float]) -> list[float]:
    """Cluster x coordinates into column centres by merging values within
    ``_X_COL_TOL`` — the data-driven column grid for vertical-per-char
    tables (#6). Clusters are sorted ascending; each cluster's centre is the
    mean of its members."""
    if not xs:
        return []
    vals = sorted(xs)
    clusters: list[list[float]] = [[vals[0]]]
    for v in vals[1:]:
        if v - clusters[-1][-1] <= _X_COL_TOL:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [sum(c) / len(c) for c in clusters]


def _nearest_column(x: float, centres: list[float], tol: float = _X_COL_TOL) -> int:
    """Assign ``x`` to the nearest column centre, falling back to the nearest
    column when no centre is within ``tol`` (preserves far-right 示例 columns
    whose centre sits beyond the data x range)."""
    best, bestd = 0, float("inf")
    for i, c in enumerate(centres):
        d = abs(x - c)
        if d < bestd:
            bestd, best = d, i
    return best


# --- table extraction (#4 path: single-row header) ------------------------


def _collect_table_rows(
    rows: list[tuple[int, list[Any]]], start: int
) -> tuple[list[list[Any]], int]:
    """Collect header + data rows for one table starting at ``start``.

    Returns the table rows (header first) and the index just past the table.
    Data rows must have ≥2 items (single-item lines are continuation text)
    and sit within ``_GAP_THRESHOLD`` of the previous accepted row, on the
    same page as the header.
    """
    page, header = rows[start]
    table = [header]
    prev_y = header[0].y
    j = start + 1
    while j < len(rows):
        p, r = rows[j]
        if p != page:
            break
        if _is_field_header(r):
            break
        if len(r) < 2:
            j += 1
            continue
        if abs(r[0].y - prev_y) > _GAP_THRESHOLD:
            break
        table.append(r)
        prev_y = r[0].y
        j += 1
    return table, j


def _render_table(
    table: list[list[Any]],
) -> tuple[list[str], list[str], list[list[str]], int, list[float]]:
    """Build a structured single-row-header table.

    Returns ``(header_render, header_cells, data_rows, ncols, header_xs)``:
    the header row as rendered cells, the normalised header (continuation
    match key), the data rows as cell rows, the column count, and the sorted
    per-column x grid used by #7 to decide continuation (same header AND same
    column grid) vs an independent table.
    """
    header = table[0]
    data_rows_raw = table[1:]
    if not data_rows_raw:
        return [], [], [], 0, []
    # Column count comes from the DATA rows' x spread, not the header item
    # count: vertical-per-char headers (#6) and right-aligned headers (#4)
    # would otherwise force the wrong column count.
    k = _infer_column_count(data_rows_raw)
    if k < 2:
        k = max(2, len(header))
    data_xs = [it.x for r in data_rows_raw for it in r]
    boundaries = _column_boundaries(data_xs, k)

    def to_cells(r: list[Any]) -> list[str]:
        cells = [""] * k
        for it in sorted(r, key=lambda i: (i.x, -i.y)):
            c = _assign_column(it.x, boundaries)
            if c >= k:
                c = k - 1
            cells[c] = (cells[c] + " " + it.text).strip() if cells[c] else it.text
        return cells

    header_render = [it.text for it in header]
    data_rows = [to_cells(r) for r in data_rows_raw]
    header_xs = sorted(it.x for it in header)
    return header_render, _header_cells(header_render), data_rows, k, header_xs


# --- column inference ------------------------------------------------------


def _infer_column_count(data_rows: list[list[Any]]) -> int:
    """Estimate the column count from data-row item counts and x clusters.

    Most data rows carry one item per column, so the modal item count is a
    strong signal. A few rows wrap (fewer items) or split a cell (more), so
    the mode is taken over rows with ≥2 items; ties round up to favour the
    wider table (avoids collapsing a 5-column table to the 2-item wrap row).
    """
    counts = [len(r) for r in data_rows if len(r) >= 2]
    if not counts:
        return 0
    from collections import Counter

    freq = Counter(counts)
    best = max(freq.values())
    candidates = sorted(c for c, n in freq.items() if n == best)
    return candidates[-1]


def _needs_degraded_representation(table: list[list[Any]]) -> bool:
    """Return true only when this table has no stable column-count inference.

    A unique modal data-row item count is the #4 path's primary confidence
    signal. A tie between two or more equally common column counts means the
    layout has no defensible two-dimensional interpretation: choosing either
    count would necessarily combine or shift cells. This deliberately does
    *not* flag occasional wrapped rows, empty cells, uneven widths, or #6's
    column-first layouts.
    """
    data_rows = table[1:]
    counts = [len(r) for r in data_rows if len(r) >= 2]
    if len(counts) < 2:
        return True

    from collections import Counter

    frequencies = Counter(counts)
    best = max(frequencies.values())
    return sum(count == best for count in frequencies.values()) > 1


def _render_degraded_definition_list(table: list[list[Any]]) -> str:
    """Render a low-confidence table as zero-loss field definition entries.

    Each data row keeps its TextItems in original x order. The first item is
    the field key; subsequent cells are paired with the matching header label,
    or a stable positional label when the row has more cells than the header.
    Unlike a Markdown table, this representation never manufactures empty
    cells or chooses a disputed column grid.
    """
    header = table[0]
    labels = [it.text for it in header]
    lines: list[str] = []
    for row in table[1:]:
        cells = [it.text for it in sorted(row, key=lambda it: it.x) if it.text]
        if not cells:
            continue
        field = cells[0]
        details = []
        for index, value in enumerate(cells[1:], start=1):
            label = labels[index] if index < len(labels) and labels[index] else f"列{index + 1}"
            details.append(f"{label}: {value}")
        lines.append(f"{field} — {'; '.join(details)}" if details else field)
    return "\n".join(lines)


# --- column-first rebuild (#6: vertical-per-char) --------------------------


def _column_first_table(
    rows: list[tuple[int, list[Any]]], start: int
) -> tuple[list[str], list[str], list[list[str]], int, list[float], int]:
    """Rebuild a vertical-per-char field table starting at ``start``.

    Returns ``(header_render, header_cells, data_rows, ncols, header_xs,
    next_index)`` where ``header_xs`` is the sorted column-centre x list used
    by #7 to match cross-page continuations.

    1. Gather header fragment rows (contiguous physical rows above the first
       data row that carry 字段 / 名称 / 类型 tokens).
    2. Gather data rows: rows on the same page within ``_GAP_THRESHOLD``,
       stopping at the next field header or a large y-gap.
    3. Derive column centres from the data items' x clusters.
    4. Within each column, merge vertical fragments by y into cells, anchored
       on the leftmost column's y to delimit data rows.
    """
    page = rows[start][0]
    # Header fragments: walk forward while rows look like header fragments.
    header_rows: list[list[Any]] = []
    j = start
    while j < len(rows) and rows[j][0] == page:
        r = rows[j][1]
        if j == start:
            header_rows.append(r)
            j += 1
            continue
        if _is_header_fragment(r, header_rows):
            header_rows.append(r)
            j += 1
            continue
        break
    if not header_rows:
        return [], [], [], 0, [], j
    # Data rows.
    data_rows: list[list[Any]] = []
    prev_y = header_rows[-1][0].y
    while j < len(rows):
        p, r = rows[j]
        if p != page:
            break
        if _is_field_header(r):
            break
        if len(r) < 1:
            j += 1
            continue
        if abs(r[0].y - prev_y) > _GAP_THRESHOLD:
            break
        data_rows.append(r)
        prev_y = r[0].y
        j += 1
    if not data_rows:
        return [], [], [], 0, [], j

    all_items = [it for r in header_rows + data_rows for it in r]
    # Column count and centres come from clustering the DATA items' x
    # coordinates — vertical-per-char headers split tokens across rows, so
    # the per-row item count is unreliable; the x grid is stable.
    data_items = [it for r in data_rows for it in r]
    centres = _cluster_x_centres([it.x for it in data_items])
    k = len(centres)
    if k < 2:
        centres = _cluster_x_centres([it.x for it in all_items])
        k = max(2, len(centres))
    header_cells_raw = _header_cells_column_first(header_rows, centres, k)
    data_cells = _rows_column_first(data_rows, centres, k)

    # Flatten multi-row header fragments into a single header row.
    header_line = _merge_header(header_cells_raw, k)

    # Header x-fingerprint for #7 continuation match: the column centres are
    # the stable grid for vertical-per-char tables (header items span rows).
    header_xs = sorted(centres)
    return header_line, _header_cells(header_line), data_cells, k, header_xs, j


def _is_header_fragment(row: list[Any], prior: list[list[Any]]) -> bool:
    """A header-fragment row: short (≤3 items), and either carries a 字段
    token or a 名称/类型/说明/示例 token when a 字段 header was already
    seen. Whitespace inside a token is ignored so vertically-split ``字 段``
    fragments match ``字段``."""
    if len(row) > 3 or not row:
        return False
    texts = {it.text for it in row}
    norm = {t.replace(" ", "").replace("　", "") for t in texts}
    if any("字段" in t for t in norm):
        return True
    if prior and any("字段" in it.text.replace(" ", "") for r in prior for it in r):
        return any(t in texts or t in norm for t in
                   ("名称", "类型", "说明", "示例", "名", "类", "段", "字", "称", "型", "说", "明", "示", "例"))
    return False


def _row_cells_column_first(
    rows: list[list[Any]],
    centres: list[float],
    k: int,
    anchor_first: bool,
) -> list[str]:
    """Collapse a band of physical rows into one cell-row, merging vertical
    fragments within each column top→bottom."""
    cells = [""] * k
    items = sorted(
        [it for r in rows for it in r], key=lambda i: (i.x, -i.y)
    )
    for it in items:
        c = _nearest_column(it.x, centres)
        if c >= k:
            c = k - 1
        cells[c] = (cells[c] + it.text) if cells[c] else it.text
    return cells


def _header_cells_column_first(
    rows: list[list[Any]],
    centres: list[float],
    k: int,
) -> list[list[str]]:
    """Bucket header fragment items by nearest column centre, merging
    fragments within a column top→bottom. Returns one cell-row per physical
    fragment row (caller flattens)."""
    out: list[list[str]] = []
    for r in rows:
        cells = [""] * k
        for it in sorted(r, key=lambda i: (i.x, -i.y)):
            c = _nearest_column(it.x, centres)
            if c >= k:
                c = k - 1
            cells[c] = (cells[c] + it.text) if cells[c] else it.text
        out.append(cells)
    return out


def _rows_column_first(
    data_rows: list[list[Any]],
    centres: list[float],
    k: int,
) -> list[list[str]]:
    """Group physical data rows into logical data rows, anchored on the
    leftmost column's y to delimit rows (so vertical fragments of one data
    row are never merged with the next)."""
    if not data_rows:
        return []
    # Bucket every item by column.
    col_items: list[list[Any]] = [[] for _ in range(k)]
    for r in data_rows:
        for it in r:
            c = _nearest_column(it.x, centres)
            if c >= k:
                c = k - 1
            col_items[c].append(it)
    for c in range(k):
        col_items[c].sort(key=lambda i: (-i.y, i.x))

    # Anchor rows on column 0 (the field-name column). Each col-0 item starts
    # a new logical row; other columns' items attach to the row whose y-band
    # contains them.
    anchors = sorted(col_items[0], key=lambda i: -i.y) if col_items[0] else []
    if not anchors:
        # Degenerate: no leftmost items — fall back to one row per physical row.
        return [_row_cells_column_first([r], centres, k, anchor_first=False) for r in data_rows]

    row_ys = [a.y for a in anchors]
    bands = _y_bands(row_ys)

    def row_of(y: float) -> int:
        for idx, (lo, hi) in enumerate(bands):
            if lo <= y <= hi:
                return idx
        # Above the top anchor → first row; below the bottom → last row.
        if y > row_ys[0]:
            return 0
        return len(row_ys) - 1

    out = [[""] * k for _ in anchors]
    # Place anchor column items.
    for i, a in enumerate(anchors):
        out[i][0] = a.text
    # Place every other column's items into the matching row, merging
    # vertical fragments within the row top→bottom.
    for c in range(1, k):
        for it in col_items[c]:
            ri = row_of(it.y)
            out[ri][c] = (out[ri][c] + it.text) if out[ri][c] else it.text
    return out


def _y_bands(ys: list[float]) -> list[tuple[float, float]]:
    """Partition the y-axis into one band per anchor: each band spans from
    the midpoint with the row above to the midpoint with the row below."""
    bands: list[tuple[float, float]] = []
    for i, y in enumerate(ys):
        lo = (y + ys[i + 1]) / 2 if i + 1 < len(ys) else y - _GAP_THRESHOLD
        hi = (y + ys[i - 1]) / 2 if i > 0 else y + _GAP_THRESHOLD
        # ys are sorted descending, so hi (toward previous/above) > lo.
        bands.append((lo, hi))
    return bands


def _merge_header(header_cells: list[list[str]], k: int) -> list[str]:
    """Flatten header fragment cells into a single header row.

    Vertical-per-char headers stack tokens across fragments (e.g. 字段 / 名称
    / 类型). Concatenate per-column, keeping the first non-empty token of
    each column and appending the rest without spaces for CJK runs."""
    merged = [""] * k
    for cells in header_cells:
        for c in range(k):
            if c < len(cells) and cells[c]:
                merged[c] = (merged[c] + cells[c]) if merged[c] else cells[c]
    return merged


# --- public seam -----------------------------------------------------------


def rebuild_field_tables(text_items: list[Any]) -> list["FieldTable"]:
    """Rebuild wireframe-free field tables into structured table objects.

    Returns one :class:`FieldTable` per detected field-table region (header +
    data cells), in reading order. Empty list when no field tables are found
    (e.g. the public nexo fixture has none). Rendering to ``| ... |`` Markdown
    is the caller's job (:meth:`FieldTable.render`), so callers and tests can
    read cells directly instead of re-parsing a rendered string.

    Single-row-header tables (#4) use the y-clustered path; vertical-per-char
    tables (#6) use the column-first path. The dispatch heuristic checks
    whether the rows following a field header seed still look like header
    fragments rather than data.

    Cross-page continuation (#7): when a rebuilt table's header tokens AND
    column x-grid match the previously emitted table, the continuation is a
    re-emit of the same table on the next page — its data rows are appended
    and its header dropped, so the merged output has a single header / |---|.
    Tables with the same header text but a different column grid (e.g. §5.4's
    indented optional-field table) stay independent.

    Degraded fallback (#8): a single-row table without a unique modal column
    count is emitted as a definition list rather than a speculative Markdown
    grid. The degraded table still participates in ordering but has no x-grid,
    so it cannot be merged into a structured cross-page continuation.
    """
    rows = _cluster_rows(text_items)
    built: list[FieldTable] = []
    i = 0
    while i < len(rows):
        if _is_field_header(rows[i][1]):
            # Peek: is this a vertical-per-char header (#6) or single-row (#4)?
            if _is_vertical_table(rows, i):
                hr, hc, dr, k, hx, nxt = _column_first_table(rows, i)
                if dr:
                    built.append(FieldTable(hr, hc, dr, k, hx, rows[i][0]))
                i = max(nxt, i + 1)
            else:
                table, nxt = _collect_table_rows(rows, i)
                if _needs_degraded_representation(table):
                    md = _render_degraded_definition_list(table)
                    if md:
                        built.append(
                            FieldTable([], [], [], 0, [], rows[i][0], pre_rendered=md)
                        )
                else:
                    hr, hc, dr, k, hx = _render_table(table)
                    if dr:
                        built.append(FieldTable(hr, hc, dr, k, hx, rows[i][0]))
                i = max(nxt, i + 1)
        else:
            i += 1
    return _merge_continuations(built)


@dataclass
class FieldTable:
    """One rebuilt field table, carried structurally for #7 to merge.

    ``header_cells`` is the normalised header (the continuation match key),
    ``data_rows`` the structured cell rows, ``ncols`` the column count, and
    ``header_xs`` the per-column x grid — all carried so cross-page
    continuation compares and joins cells directly instead of re-parsing a
    rendered string. ``page`` is the page the table starts on. Degraded
    definition-list tables carry no grid and are ``pre_rendered`` (they cannot
    be merged into a continuation).
    """

    header_render: list[str]
    header_cells: list[str]
    data_rows: list[list[str]]
    ncols: int
    header_xs: list[float]
    page: int
    pre_rendered: str | None = None

    def render(self) -> str:
        """Render the model to ``| ... |`` Markdown (degraded: passthrough)."""
        if self.pre_rendered is not None:
            return self.pre_rendered
        return _render_table_markdown(self.header_render, self.data_rows, self.ncols)


def _render_table_markdown(
    header_render: list[str], data_rows: list[list[str]], ncols: int
) -> str:
    """Render a structured table model to a ``| ... |`` Markdown table."""
    lines = ["| " + " | ".join(header_render) + " |"]
    lines.append("|" + "|".join("---" for _ in range(ncols)) + "|")
    for r in data_rows:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


# Two header x-grids within this many points, column-for-column, count as the
# same grid — absorbs per-item x jitter across pages without merging tables
# whose columns are genuinely at different x positions (e.g. an indented
# optional-field table shifted ~40pt right vs the main table).
_GRID_TOL = 12.0


def _merge_continuations(built: list[FieldTable]) -> list[FieldTable]:
    """Fold cross-page continuation tables into their predecessor.

    A table is a continuation of the previous one when (a) it starts on a
    later page, (b) its normalised header cells equal the previous table's,
    and (c) its header column x-grid matches column-for-column within
    ``_GRID_TOL``. Condition (c) is the guardrail that keeps an independent
    table which merely re-uses the same header words at a different indent
    from being folded in. The continuation's data rows are appended after the
    previous table's last data row; its header and ``|---|`` separator are
    dropped. All comparison and joining happens on the structured model; the
    caller renders the surviving tables.
    """
    if not built:
        return []
    out: list[FieldTable] = [built[0]]
    last = built[0]
    for t in built[1:]:
        if t.page > last.page and _is_continuation(t, last):
            last.data_rows.extend(t.data_rows)
        else:
            out.append(t)
            last = t
    return out


def _is_continuation(cur: FieldTable, prev: FieldTable) -> bool:
    """Continuation when header cells match AND column x-grids match."""
    if cur.header_cells != prev.header_cells:
        return False
    return _grid_matches(cur.header_xs, prev.header_xs)


def _grid_matches(a: list[float], b: list[float]) -> bool:
    """Column-for-column x-grid equality within ``_GRID_TOL``.

    Different column counts ⇒ not the same grid. Equal header text with a
    different column count (a 4-col table vs a 3-col table) is also not a
    continuation — the grids cannot line up.
    """
    if not a or not b or len(a) != len(b):
        return False
    return all(abs(x - y) <= _GRID_TOL for x, y in zip(a, b))


def _header_cells(raw_header: list[str]) -> list[str]:
    """Normalise a raw header cell list for continuation matching.

    Drops trailing empty cells (the header row may be padded to the data
    column count with empty trailing cells, e.g. ``字段名 | … | 是否必填 |``)
    and strips inter-cell whitespace so ``字段名`` vs ``字段名 `` don't
    break equality.
    """
    cells = [c.strip() for c in raw_header]
    while cells and not cells[-1]:
        cells.pop()
    return cells


def _is_vertical_table(
    rows: list[tuple[int, list[Any]]], start: int
) -> bool:
    """Dispatch heuristic: a field header at ``start`` is a vertical-per-char
    table (#6) when the seed row carries the ``字段`` token in **two or more
    distinct x columns** — the signature of a vertically-stacked multi-column
    header (``字段 | 字段`` laid out as ``字段名称`` / ``字段类型``). A
    single ``字段`` token (e.g. ``英文字段 | 说明``) is a regular #4 table
    whose header happens to wrap, so it stays on the single-row path."""
    seed = rows[start][1]
    field_xs = sorted({it.x for it in seed if "字段" in it.text})
    if len(field_xs) < 2:
        return False
    page = rows[start][0]
    j = start + 1
    fragment_count = 1
    while j < len(rows) and rows[j][0] == page:
        r = rows[j][1]
        if _is_header_fragment(r, [seed]):
            fragment_count += 1
            j += 1
            continue
        break
    return fragment_count >= 2
