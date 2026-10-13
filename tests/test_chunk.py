"""Chunking: sentence boundaries, merging, overlap, provenance."""
from __future__ import annotations

from corpusfold import Block, Chunk, Document, Page, chunk_document, rows_to_text, split_sentences


def _page(number: int, texts: list) -> Page:
    blocks = []
    for i, item in enumerate(texts):
        if isinstance(item, Block):
            blocks.append(item)
        else:
            blocks.append(
                Block(text=item, page=number, x0=40, y0=100 + i * 60, x1=550, y1=140 + i * 60)
            )
    return Page(number=number, width=595.0, height=842.0, blocks=blocks)


def _doc(*pages: Page) -> Document:
    return Document(source="synthetic.pdf", pages=list(pages))


# --- sentence splitting ---------------------------------------------------

def test_splits_on_chinese_sentence_endings():
    assert split_sentences("第一句。第二句！第三句？") == ["第一句。", "第二句！", "第三句？"]


def test_splits_on_semicolons_and_paragraph_breaks():
    assert split_sentences("甲；乙\n\n丙") == ["甲；", "乙", "丙"]


def test_decimal_points_do_not_split():
    assert split_sentences("涨幅约 3.5% 左右。") == ["涨幅约 3.5% 左右。"]


def test_english_sentences_split_on_period_plus_space():
    assert split_sentences("First one. Second one.") == ["First one.", "Second one."]


# --- chunking -------------------------------------------------------------

def test_a_short_document_becomes_one_chunk():
    doc = _doc(_page(1, ["只有一小段文字。"]))
    chunks = chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].text == "只有一小段文字。"


def test_chunks_respect_the_hard_maximum():
    long_text = "这是一句用来测试分块上限的话。" * 40
    chunks = chunk_document(_doc(_page(1, [long_text])), target=200, hard_max=300)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 400 for chunk in chunks)  # hard_max + one sentence


def test_neighbouring_chunks_overlap_by_one_sentence():
    text = "".join(f"这是第{i}句话，用来把文本堆到足够长。" for i in range(30))
    chunks = chunk_document(_doc(_page(1, [text])), target=150, hard_max=200, overlap=1)

    assert len(chunks) >= 3
    first_tail = chunks[0].text[-12:]
    assert first_tail in chunks[1].text, "the last sentence should reappear in the next chunk"


def test_chunks_remember_which_pages_they_came_from():
    doc = _doc(
        _page(1, ["第一页的内容，讲了一件事情。"]),
        _page(2, ["第二页的内容，继续讲这件事情。"]),
    )
    chunks = chunk_document(doc, target=30, hard_max=40)

    assert chunks, "expected at least one chunk"
    assert all(chunk.source == "synthetic.pdf" for chunk in chunks)
    assert all(chunk.page >= 1 for chunk in chunks)
    assert all(chunk.label.startswith("synthetic.pdf p.") for chunk in chunks)


def test_ordinals_are_sequential():
    text = "".join(f"第{i}句内容。".replace("i", str(i)) for i in range(40))
    chunks = chunk_document(_doc(_page(1, [text])), target=60, hard_max=80)
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))


def test_fingerprints_ignore_lookalike_glyphs():
    plain = _doc(_page(1, ["颜色值。"]))
    lookalike = _doc(_page(1, ["颜\u2f8a值。"]))  # ⾊ U+2F8A, not 色 U+8272
    assert chunk_document(plain)[0].fingerprint == chunk_document(lookalike)[0].fingerprint


def test_empty_document_yields_no_chunks():
    assert chunk_document(Document(source="empty.pdf", pages=[])) == []


def test_contents_entries_are_left_out_of_chunks():
    """A contents page outranks the body it points at, so it is not indexed."""
    doc = _doc(
        _page(
            1,
            [
                "3、 风险提示 .............................. 8",
                "4、 重点公司 .............................. 9",
                "这是正文的内容，讲的是某家公司的产能扩张情况。",
            ],
        )
    )

    chunks = chunk_document(doc)

    assert len(chunks) == 1
    assert "风险提示" not in chunks[0].text
    assert "产能扩张" in chunks[0].text


def test_a_document_of_only_contents_entries_yields_no_chunks():
    doc = _doc(_page(1, ["1、 第一节 ............ 1", "2、 第二节 ............ 3", "3、 第三节 ............ 7"]))
    assert chunk_document(doc) == []


# --- tables ---------------------------------------------------------------

def _table(rows, y=300):
    return Block(
        text=rows_to_text(rows),
        page=1,
        x0=40,
        y0=y,
        x1=550,
        y1=y + 120,
        kind="table",
        table=rows,
    )


def test_a_table_stays_whole_in_its_own_chunk():
    """Splitting a table scatters its column headers away from its values."""
    doc = _doc(
        _page(
            1,
            [
                "前面是一段背景说明，讲的是公司所处的行业情况，以及它过去几年的位置。",
                _table([["项目", "2023", "2022"], ["收入", "100", "80"]]),
                "后面是一段结论，讲的是对未来的展望，以及需要注意的风险。",
            ],
        )
    )

    chunks = chunk_document(doc, target=20, hard_max=30)

    holding = [c for c in chunks if "收入 | 100 | 80" in c.text]
    assert len(holding) == 1, "the table should appear in exactly one chunk"
    assert "项目 | 2023 | 2022" in holding[0].text, "its header row came along"


def test_a_table_chunk_does_not_absorb_the_surrounding_prose():
    doc = _doc(
        _page(
            1,
            [
                "前面这段正文很长，长到足以让下一个块和它重叠起来，所以这里要写足够多的字才行。",
                _table([["指标", "甲", "乙"], ["毛利率", "30", "25"]]),
                "后面这段正文也同样写得很长，目的是确认表格块的两端都是干净的，没有被粘连。",
            ],
        )
    )

    chunks = chunk_document(doc, target=20, hard_max=30)

    table_chunk = next(c for c in chunks if "毛利率" in c.text)
    assert "前面这段正文" not in table_chunk.text
    assert "后面这段正文" not in table_chunk.text


def test_a_huge_table_is_sliced_with_the_header_repeated():
    """A 60-row table must not become one four-thousand-character chunk."""
    rows = [["代码", "简称", "市值"]] + [
        [f"{i:06d}", f"公司{i}", str(i * 10)] for i in range(60)
    ]
    block = Block(
        text=rows_to_text(rows),
        page=1,
        x0=40,
        y0=100,
        x1=550,
        y1=700,
        kind="table",
        table=rows,
    )
    doc = _doc(_page(1, [block]))

    chunks = chunk_document(doc, target=50, hard_max=120)

    assert len(chunks) > 1, "a large table should not stay as one giant chunk"
    for chunk in chunks:
        assert chunk.text.startswith("代码 | 简称 | 市值"), "every slice keeps the header"
        assert len(chunk.text) <= 120


# --- provenance labels ----------------------------------------------------

def test_label_shows_the_file_name_not_the_whole_path():
    """An absolute path in a result list pushes everything else off the line."""
    chunk = Chunk(
        text="甲",
        source="/Users/someone/a/very/long/path/研报.pdf",
        ordinal=0,
        page=3,
        pages=(3,),
    )
    assert chunk.label == "研报.pdf p.3"
    assert chunk.source == "/Users/someone/a/very/long/path/研报.pdf"


def test_label_spans_a_page_range():
    chunk = Chunk(text="甲", source="/tmp/a.pdf", ordinal=0, page=3, pages=(3, 4))
    assert chunk.label == "a.pdf p.3-4"
