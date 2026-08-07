"""Wireframe-free field-table reconstruction from structured TextItems.

Issue #4 — row cluster & column alignment slice.

A *field table* (字段表) is the security-vendor convention of listing log
fields as ``字段 | 字段名称 | 说明`` (or 4-column variants) with **no ruling
lines** — pdf-inspector's rect/line table detectors cannot see it, so the
body Markdown comes out garbled. This module rebuilds such tables from
``TextItem`` coordinates:

1. cluster items into rows by ``page + y`` (within ``_Y_TOL``);
2. detect a field-table header row (an item containing ``字段``);
3. on the same page, collect following data rows (≥2 items) until a y-gap
   or the next header;
4. derive column boundaries from the **X-coordinate histogram valleys** of
   the data items (not the header x-starts — the 说明 header is often
   right-aligned while its data starts further left, so header-x alignment
   would drift);
5. assign each data item to a column by x, preserving empty cells (no
   left-shift), and render a standard Markdown table with a ``|---|``
   separator row.

Scope: single page, single-row header, uneven column widths. Multi-row
headers (#6) and cross-page continuation (#7) are deferred — a field table
that spans a page break is only rebuilt up to the page boundary here.
"""
from __future__ import annotations

from typing import Any

_Y_TOL = 3.0
# A y-gap larger than this ends a table (normal row spacing is ~18–32pt).
_GAP_THRESHOLD = 40.0


# --- row clustering --------------------------------------------------------


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


# --- column boundaries from X-histogram valleys ----------------------------


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
    # gaps between consecutive sorted x values
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


# --- table extraction ------------------------------------------------------


def _collect_table_rows(
    rows: list[tuple[int, list[Any]]], start: int
) -> tuple[list[list[Any]], int]:
    """Collect header + data rows for one table starting at ``start``.

    Returns the table rows (header first) and the index just past the table.
    Data rows must have ≥2 items (single-item lines are continuation text,
    handled by #6/#7) and sit within ``_GAP_THRESHOLD`` of the previous
    accepted row, on the same page as the header.
    """
    page, header = rows[start]
    table = [header]
    prev_y = header[0].y
    j = start + 1
    while j < len(rows):
        p, r = rows[j]
        if p != page:
            break
        if len(r) < 2:
            j += 1
            continue
        if _is_field_header(r):
            break
        if abs(r[0].y - prev_y) > _GAP_THRESHOLD:
            break
        table.append(r)
        prev_y = r[0].y
        j += 1
    return table, j


def _render_table(table: list[list[Any]]) -> str:
    header = table[0]
    k = len(header)
    data_rows = table[1:]
    if not data_rows:
        return ""
    data_xs = [it.x for r in data_rows for it in r]
    boundaries = _column_boundaries(data_xs, k)

    def to_cells(r: list[Any]) -> list[str]:
        cells = [""] * k
        for it in r:
            c = _assign_column(it.x, boundaries)
            if c >= k:
                c = k - 1
            cells[c] = (cells[c] + " " + it.text).strip() if cells[c] else it.text
        return cells

    lines = []
    lines.append("| " + " | ".join(it.text for it in header) + " |")
    lines.append("|" + "|".join("---" for _ in range(k)) + "|")
    for r in data_rows:
        lines.append("| " + " | ".join(to_cells(r)) + " |")
    return "\n".join(lines)


# --- public seam -----------------------------------------------------------


def rebuild_field_tables(text_items: list[Any]) -> list[str]:
    """Rebuild wireframe-free field tables into Markdown table strings.

    Returns one Markdown table per detected field-table region (header +
    data), in reading order. Empty list when no field tables are found
    (e.g. the public nexo fixture has none).
    """
    rows = _cluster_rows(text_items)
    tables: list[str] = []
    i = 0
    while i < len(rows):
        if _is_field_header(rows[i][1]):
            table, nxt = _collect_table_rows(rows, i)
            md = _render_table(table)
            if md:
                tables.append(md)
            i = max(nxt, i + 1)
        else:
            i += 1
    return tables
