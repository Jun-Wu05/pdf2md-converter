"""Issue #8 — zero-loss degraded representation for uncertain field tables.

When a field table's data rows do not have a unique modal column count, the
normal X-grid renderer would have to choose one equally plausible grid and may
shift or combine cells. The fallback emits definition-list lines instead: all
original cell texts remain present and ordered, without a Markdown table
separator that implies false structural confidence.
"""
from types import SimpleNamespace

from pdf2md_full.tables import rebuild_field_tables


def _item(text: str, x: float, y: float) -> SimpleNamespace:
    return SimpleNamespace(text=text, x=x, y=y, page=1)


def test_ambiguous_column_count_degrades_to_definition_list():
    """AC1/AC2: tied 2- vs 3-cell rows avoid `|---|` and preserve every cell."""
    items = [
        _item("字段", 10, 100),
        _item("名称", 100, 100),
        _item("说明", 200, 100),
        _item("alpha", 10, 80),
        _item("阿尔法", 100, 80),
        _item("beta", 10, 60),
        _item("贝塔", 100, 60),
        _item("第二行说明", 200, 60),
    ]

    tables = rebuild_field_tables(items)

    assert tables == [
        "alpha — 名称: 阿尔法\nbeta — 名称: 贝塔; 说明: 第二行说明"
    ]
    assert "|---|" not in tables[0]


def test_stable_column_count_keeps_standard_markdown_table():
    """Regression: a unique modal column count remains on the #4 table path."""
    items = [
        _item("字段", 10, 100),
        _item("名称", 100, 100),
        _item("说明", 200, 100),
        _item("alpha", 10, 80),
        _item("阿尔法", 100, 80),
        _item("第一行说明", 200, 80),
        _item("beta", 10, 60),
        _item("贝塔", 100, 60),
        _item("第二行说明", 200, 60),
        _item("gamma", 10, 40),
        _item("伽马", 100, 40),
        _item("第三行说明", 200, 40),
    ]

    tables = rebuild_field_tables(items)

    assert len(tables) == 1
    assert "| 字段 | 名称 | 说明 |" in tables[0]
    assert "|---|---|---|" in tables[0]
    assert "| beta | 贝塔 | 第二行说明 |" in tables[0]


def test_degraded_rows_keep_source_order_and_pair_field_with_details():
    """AC3: every original cell stays with its row; no fabricated grid shifts it."""
    items = [
        _item("字段", 10, 100),
        _item("类型", 100, 100),
        _item("说明", 200, 100),
        _item("key", 10, 80),
        _item("string", 100, 80),
        _item("other", 10, 60),
        _item("integer", 100, 60),
        _item("计数说明", 200, 60),
    ]

    rendered = rebuild_field_tables(items)[0]

    assert rendered.splitlines() == [
        "key — 类型: string",
        "other — 类型: integer; 说明: 计数说明",
    ]
    for text in ("key", "string", "other", "integer", "计数说明"):
        assert text in rendered
