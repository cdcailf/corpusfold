"""Chunking: sentence boundaries, merging, overlap, provenance."""
from __future__ import annotations

from corpuskit import Block, Document, Page, chunk_document, split_sentences


def _page(number: int, texts: list[str]) -> Page:
    return Page(
        number=number,
        width=595.0,
        height=842.0,
        blocks=[
            Block(text=text, page=number, x0=40, y0=100 + i * 60, x1=550, y1=140 + i * 60)
            for i, text in enumerate(texts)
        ],
    )


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
