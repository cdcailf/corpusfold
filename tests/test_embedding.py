"""The optional dense layer, wired up with a stub that never touches a network."""
from __future__ import annotations

from corpusfold import Chunk, Index, cosine, fingerprint


class StubEmbedder:
    """Deterministic vectors from a lookup table, keyed by exact text.

    The point of the dense layer is that its scores are *independent* of the
    lexical ones, so a stub with hand-picked vectors tests the wiring better
    than a real model would: you can point every vector wherever you like.
    """

    def __init__(self, table: dict[str, list[float]]) -> None:
        self.table = table
        self.calls: list[list[str]] = []

    def encode(self, texts):
        self.calls.append(list(texts))
        return [list(self.table.get(text, [0.0, 0.0])) for text in texts]


def _chunk(text: str, ordinal: int = 0) -> Chunk:
    return Chunk(
        text=text,
        source="doc.pdf",
        ordinal=ordinal,
        page=1,
        pages=(1,),
        fingerprint=fingerprint(text),
    )


# --- cosine ---------------------------------------------------------------

def test_cosine_of_identical_vectors_is_one():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_floors_negative_similarity():
    """Without the floor, an anti-correlated passage would subtract evidence."""
    assert cosine([1.0, 0.0], [-1.0, 0.0]) == 0.0


def test_cosine_of_a_zero_vector_is_zero():
    assert cosine([1.0, 0.0], [0.0, 0.0]) == 0.0


def test_cosine_of_mismatched_dimensions_is_zero():
    assert cosine([1.0], [1.0, 2.0]) == 0.0


# --- the index ------------------------------------------------------------

def test_without_an_embedder_the_dense_component_is_zero():
    hit = Index([_chunk("紫色独角兽协议的编号规则。")]).search("编号规则")[0]
    assert hit.dense == 0.0


def test_a_chunk_with_no_literal_overlap_can_still_be_retrieved():
    """The whole reason the dense layer exists: no shared characters, still right."""
    chunks = [_chunk("那件事的细节我记不清了。", 0), _chunk("另一段完全无关的话。", 1)]
    embedder = StubEmbedder(
        {
            "那件事的细节我记不清了。": [0.0, 1.0],
            "另一段完全无关的话。": [1.0, 0.0],
            "紫色独角兽": [0.0, 1.0],
        }
    )

    hits = Index(chunks, embedder=embedder).search("紫色独角兽")

    assert hits, "the dense match should have kept this result alive"
    assert hits[0].chunk.ordinal == 0
    assert hits[0].lexical == 0.0
    assert hits[0].dense > 0.0


def test_dense_weight_zero_disables_the_vector_component():
    chunks = [_chunk("甲。", 0)]
    embedder = StubEmbedder({"甲。": [1.0], "乙": [1.0]})

    hits = Index(chunks, embedder=embedder).search("乙", dense_weight=0.0)

    assert hits == [], "with no lexical overlap and no dense weight there is nothing to rank"


def test_embedding_the_chunks_happens_once_at_construction():
    chunks = [_chunk("甲。", 0), _chunk("乙。", 1)]
    embedder = StubEmbedder({})

    Index(chunks, embedder=embedder)

    assert len(embedder.calls) == 1
    assert len(embedder.calls[0]) == 2


def test_a_bare_index_never_calls_an_embedder():
    embedder = StubEmbedder({})
    index = Index([_chunk("甲。", 0)])
    index.search("甲")

    assert embedder.calls == []
