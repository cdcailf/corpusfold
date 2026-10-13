"""Retrieval: ranking, look-alike tolerance, de-duplication, provenance."""
from __future__ import annotations

from corpuskit import Chunk, Index, fingerprint


def _chunk(text: str, ordinal: int = 0, page: int = 1, source: str = "doc.pdf") -> Chunk:
    return Chunk(
        text=text,
        source=source,
        ordinal=ordinal,
        page=page,
        pages=(page,),
        fingerprint=fingerprint(text),
    )


def test_ranks_the_matching_chunk_first():
    chunks = [
        _chunk("本文讨论的是半导体行业的产能问题。", 0),
        _chunk("紫色独角兽协议的编号规则如下。", 1),
        _chunk("公司财务报表附注说明。", 2),
    ]

    hits = Index(chunks).search("紫色独角兽协议")

    assert hits[0].chunk.ordinal == 1
    assert hits[0].score > 0


def test_an_unrelated_query_finds_nothing():
    assert Index([_chunk("半导体产能。")]).search("量子计算机") == []


def test_a_lookalike_glyph_in_the_document_still_matches():
    """A normally-typed query must reach a passage that used ⻆ instead of 角."""
    passage = "\u2ec6色表的编号规则如下。"  # ⻆色表...
    chunks = [_chunk(passage, 0), _chunk("完全无关的另一段文字。", 1)]

    hits = Index(chunks).search("角色表的编号")

    assert hits, "the folded query should have matched"
    assert hits[0].chunk.ordinal == 0


def test_exact_match_earns_a_bonus():
    chunks = [_chunk("紫色独角兽协议编号规则。", 0), _chunk("紫色很漂亮。", 1)]

    top = Index(chunks).search("紫色独角兽协议编号")[0]

    assert top.chunk.ordinal == 0
    assert top.exact > 0, "verbatim overlap should add to the lexical score"


def test_duplicate_passages_collapse():
    text = "同一段文字在文档里重复出现了两次。"
    hits = Index([_chunk(text, 0), _chunk(text, 1)]).search("重复出现")
    assert len(hits) == 1


def test_dedupe_can_be_turned_off():
    text = "同一段文字在文档里重复出现了两次。"
    hits = Index([_chunk(text, 0), _chunk(text, 1)]).search("重复出现", dedupe=False)
    assert len(hits) == 2


def test_hits_carry_provenance():
    hit = Index([_chunk("紫色独角兽协议的编号规则。", 0, page=3)]).search("编号规则")[0]
    assert hit.chunk.source == "doc.pdf"
    assert hit.label == "doc.pdf p.3"


def test_multipage_chunks_label_their_range():
    from corpuskit import fingerprint as fp

    chunk = Chunk(text="跨页的一段。", source="doc.pdf", ordinal=0, page=2, pages=(2, 3), fingerprint=fp("跨页的一段。"))
    assert Index([chunk]).search("跨页")[0].label == "doc.pdf p.2-3"


def test_limit_is_respected():
    chunks = [_chunk(f"紫色独角兽协议的第 {i} 号编号规则。", i) for i in range(10)]
    assert len(Index(chunks).search("紫色独角兽协议编号", limit=3)) == 3


def test_empty_query_finds_nothing():
    index = Index([_chunk("有内容的一句话。")])
    assert index.search("") == []
    assert index.search("   ") == []


def test_empty_index_finds_nothing():
    assert Index([]).search("任何查询") == []
