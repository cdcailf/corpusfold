"""Character cleaning and boilerplate logic, with hand-built documents.

Building the Document objects directly keeps these tests at the level the code
actually reasons about — pages, blocks, bands — with no PDF involved.
"""
from __future__ import annotations

import pytest

from corpusfold import (
    Block,
    Document,
    Page,
    boilerplate_key,
    find_boilerplate,
    is_toc_entry,
    normalize,
    normalize_document,
    strip_boilerplate,
)

RADICAL_HORN = "\u2ec6"  # ⻆ looks like 角
KANGXI_COLOR = "\u2f8a"  # ⾊ looks like 色

FOOTER = "请务必阅读正文后免责条款部分"


def _page(number: int, blocks: list[Block]) -> Page:
    return Page(number=number, width=595.0, height=842.0, blocks=blocks)


def _doc_with_running_footer(pages: int, *, first_page_prefix: str = "") -> Document:
    made = []
    for number in range(1, pages + 1):
        prefix = first_page_prefix if number == 1 else ""
        made.append(
            _page(
                number,
                [
                    Block(text=f"{prefix}{FOOTER} {number}", page=number, x0=40, y0=795, x1=550, y1=812),
                    Block(text=f"第 {number} 段的正文内容。", page=number, x0=40, y0=400, x1=550, y1=430),
                ],
            )
        )
    return Document(source="synthetic", pages=made)


# --- character cleaning ---------------------------------------------------

def test_folds_lookalike_glyphs():
    assert normalize(f"{RADICAL_HORN}{KANGXI_COLOR}") == "角色"


def test_strips_zero_width_and_control_characters():
    assert normalize("颜\u200b色\x07值\ufeff") == "颜色值"


def test_collapses_ideographic_and_regular_spaces():
    assert normalize("颜\u3000色\t\t值") == "颜 色 值"


def test_normalize_document_drops_blocks_that_become_empty():
    doc = Document(
        source="synthetic",
        pages=[_page(1, [Block(text="\u200b", page=1, x0=0, y0=0, x1=1, y1=1)])],
    )
    assert normalize_document(doc).block_count == 0


# --- boilerplate ----------------------------------------------------------

def test_key_ignores_page_numbers():
    assert boilerplate_key(f"{FOOTER} 2") == boilerplate_key(f"{FOOTER} 37")


def test_finds_a_footer_repeated_across_pages():
    doc = _doc_with_running_footer(pages=8)
    assert FOOTER in find_boilerplate(doc)


def test_removes_the_footer_from_every_page():
    stripped = strip_boilerplate(_doc_with_running_footer(pages=8))
    assert not any("免责条款" in block.text for block in stripped.blocks())
    assert sum("正文内容" in block.text for block in stripped.blocks()) == 8


def test_first_page_footer_with_extra_text_is_also_removed():
    """The first page commonly adds the company name; frequency alone misses it."""
    doc = _doc_with_running_footer(pages=8, first_page_prefix="国海证券研究所 ")

    stripped = strip_boilerplate(doc)

    assert not any("免责条款" in block.text for block in stripped.blocks())


def test_a_long_paragraph_is_never_boilerplate():
    """Repeated *body* text must survive — only short running text is stripped."""
    paragraph = "这是一段足够长的正文，用来确认出现在每一页中间的长文本不会被当成页眉页脚删掉。" * 2
    doc = Document(
        source="synthetic",
        pages=[
            _page(n, [Block(text=paragraph, page=n, x0=40, y0=400, x1=550, y1=460)])
            for n in range(1, 6)
        ],
    )

    assert find_boilerplate(doc) == set()
    assert strip_boilerplate(doc).block_count == 5


def test_no_detected_boilerplate_returns_the_same_document():
    doc = Document(
        source="synthetic",
        pages=[_page(1, [Block(text="只有一页。", page=1, x0=40, y0=400, x1=100, y1=420)])],
    )
    assert strip_boilerplate(doc) is doc


# --- contents pages -------------------------------------------------------

def test_recognises_a_contents_entry():
    assert is_toc_entry("3、 风险提示 .............................. 8")
    assert is_toc_entry("图1：涛涛车业主营业务收入结构 ........ 5")
    assert is_toc_entry("1.1、 本周上市公司 ..........")


def test_ordinary_prose_is_not_a_contents_entry():
    assert not is_toc_entry("这里用了省略号……但那是正常行文。")
    assert not is_toc_entry("公司的产能正在扩张，订单已经排到了下个季度。")
    assert not is_toc_entry("")


def test_a_dot_run_inside_a_sentence_is_not_a_contents_entry():
    assert not is_toc_entry("等等……还有别的例子 1234")
    assert not is_toc_entry("这一段结尾是数字 2023，但没有引导点")


# --- rebuilds must not lose fields ----------------------------------------

def test_normalize_document_preserves_every_block_field():
    """Rebuilding blocks by hand once dropped ``table`` without a sound.

    The failure is silent: the table quietly stops being sliced, and the only
    symptom is a chunk far larger than the hard maximum.
    """
    block = Block(
        text="项目 收入",
        page=1,
        x0=1,
        y0=2,
        x1=3,
        y1=4,
        kind="table",
        table=[["项目", "收入"], ["甲", "100"]],
    )
    doc = Document(source="synthetic", pages=[_page(1, [block])])

    result = normalize_document(doc).pages[0].blocks[0]

    assert result.kind == "table"
    assert result.table == [["项目", "收入"], ["甲", "100"]]
    assert result.x0 == 1 and result.y1 == 4
