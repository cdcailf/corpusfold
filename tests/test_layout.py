"""Layout: column detection and reading order."""
from __future__ import annotations

from corpuskit import Block, Document, Page, detect_columns, is_full_width, page_order, reading_order

WIDTH = 600.0
HEIGHT = 800.0


def _block(text, x0, y0, x1=None, page=1, y1=None):
    return Block(
        text=text,
        page=page,
        x0=x0,
        y0=y0,
        x1=x1 if x1 is not None else x0 + 240,
        y1=y1 if y1 is not None else y0 + 20,
    )


def _page(number, blocks):
    return Page(number=number, width=WIDTH, height=HEIGHT, blocks=blocks)


def _two_columns(extra=None):
    return _page(
        1,
        [
            *(extra or []),
            _block("left one", 40, 100, 280),
            _block("left two", 40, 200, 280),
            _block("right one", 320, 100, 560),
            _block("right two", 320, 200, 560),
        ],
    )


def test_a_single_column_page_keeps_position_order():
    page = _page(1, [_block("first", 40, 100, 560), _block("second", 40, 200, 560)])
    assert [b.text for b in page_order(page)] == ["first", "second"]


def test_two_columns_are_detected():
    columns = detect_columns(_two_columns())
    assert len(columns) == 2
    assert columns[0][0] < columns[1][0]
    assert columns[0][1] <= columns[1][0]


def test_two_column_page_reads_the_left_column_first():
    """Position order alone would interleave the two columns."""
    order = [b.text for b in page_order(_two_columns())]
    assert order == ["left one", "left two", "right one", "right two"]


def test_a_full_width_title_does_not_bridge_the_gutter():
    page = _two_columns(extra=[_block("a wide title", 40, 40, 560)])
    assert is_full_width(page.blocks[0], page)

    order = [b.text for b in page_order(page)]

    assert order[0] == "a wide title"
    assert order[1:] == ["left one", "left two", "right one", "right two"]


def test_narrow_gaps_do_not_manufacture_columns():
    """A small hole between blocks is not a gutter."""
    page = _page(
        1,
        [
            _block("a", 40, 100, 280),
            _block("b", 296, 100, 560),
            _block("c", 40, 200, 280),
            _block("d", 296, 200, 560),
        ],
    )
    assert len(detect_columns(page)) == 1


def test_reading_order_crosses_pages_in_order():
    doc = Document(
        source="two.pdf",
        pages=[
            _page(1, [_block("page one line", 40, 100, 560, page=1)]),
            _page(2, [_block("page two line", 40, 100, 560, page=2)]),
        ],
    )
    assert [b.text for b in reading_order(doc)] == ["page one line", "page two line"]


def test_an_empty_page_yields_nothing():
    assert page_order(Page(number=1, width=WIDTH, height=HEIGHT, blocks=[])) == []
