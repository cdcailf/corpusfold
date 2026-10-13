"""Retrieval over chunks.

Two decisions worth naming up front:

1. **Character bigrams, not words.** Chinese has no spaces, and a tokenizer is
   a heavy dependency with failure modes of its own. Indexing character bigrams
   needs no tokenizer and reaches word-like retrieval quality for Chinese.
2. **Lexical first, exact-match bonus on top.** Dense scores are bad at literal
   tokens; ``cjkfold``'s character n-gram overlap puts them back.

Every hit carries its :class:`~corpusfold.chunk.Chunk`, so the caller can always
say which document and page an answer came from.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

import cjkfold

from .chunk import Chunk, fingerprint
from .embedding import Embedder, cosine

# Standard BM25 constants: term-frequency saturation and length normalisation.
K1 = 1.5
B = 0.75

# Everything that is not a letter, digit or ideograph separates terms.
_SEPARATOR = re.compile(r"[\W_]+", re.UNICODE)


@dataclass
class Hit:
    """A chunk that matched, with the components of its score kept separate."""

    chunk: Chunk
    score: float
    lexical: float
    exact: float
    dense: float = 0.0

    @property
    def label(self) -> str:
        return self.chunk.label


def index_text(text: str) -> str:
    """Normalised form used for both indexing and matching.

    Folding happens before anything else so that a query and a document that
    differ only in look-alike glyphs still match.
    """
    return _SEPARATOR.sub("", cjkfold.fold(text).lower())


def bigrams(text: str) -> list[str]:
    normalized = index_text(text)
    if len(normalized) < 2:
        return [normalized] if normalized else []
    return [normalized[i : i + 2] for i in range(len(normalized) - 1)]


class Index:
    """An in-memory BM25 index over character bigrams."""

    def __init__(self, chunks: list[Chunk], *, embedder: Embedder | None = None) -> None:
        self._chunks = list(chunks)
        self._embedder = embedder
        self._vectors: list[list[float]] = []
        if embedder is not None and self._chunks:
            self._vectors = list(embedder.encode([chunk.text for chunk in self._chunks]))

        self._tf = [Counter(bigrams(chunk.text)) for chunk in self._chunks]
        self._length = [sum(tf.values()) for tf in self._tf]
        self._avg_length = (sum(self._length) / len(self._length)) if self._length else 0.0

        self._document_frequency: Counter[str] = Counter()
        for tf in self._tf:
            self._document_frequency.update(tf.keys())

    def __len__(self) -> int:
        return len(self._chunks)

    @property
    def chunks(self) -> list[Chunk]:
        return list(self._chunks)

    def _idf(self, term: str) -> float:
        total = len(self._chunks)
        df = self._document_frequency.get(term, 0)
        return math.log(1 + (total - df + 0.5) / (df + 0.5))

    def _bm25(self, position: int, terms: set[str]) -> float:
        tf = self._tf[position]
        length = self._length[position]
        average = self._avg_length or 1.0
        score = 0.0
        for term in terms:
            frequency = tf.get(term, 0)
            if not frequency:
                continue
            denominator = frequency + K1 * (1 - B + B * length / average)
            score += self._idf(term) * frequency * (K1 + 1) / denominator
        return score

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        dedupe: bool = True,
        exact_cap: float = 0.25,
        dense_weight: float = 0.5,
    ) -> list[Hit]:
        """Rank chunks against *query*, best first.

        ``dense_weight`` matters only when the index was built with an
        ``embedder``; with none, every dense component is zero and the ranking
        is purely lexical.
        """
        if not self._chunks or not query.strip():
            return []

        query_vector = None
        if self._embedder is not None and self._vectors and dense_weight:
            query_vector = self._embedder.encode([query])[0]

        terms = set(bigrams(query))
        raw = (
            [self._bm25(position, terms) for position in range(len(self._chunks))]
            if terms
            else [0.0] * len(self._chunks)
        )
        top = max(raw) or 1.0  # lexical scores are unbounded, so scale to 0..1

        hits: list[Hit] = []
        for position, value in enumerate(raw):
            chunk = self._chunks[position]
            lexical = value / top
            exact = cjkfold.exact_boost(query, chunk.text, cap=exact_cap)
            dense = cosine(query_vector, self._vectors[position]) if query_vector else 0.0
            # A chunk with no lexical overlap can still be the right answer when
            # the dense layer scores it, so the cut-off is on the total.
            score = lexical + exact + dense_weight * dense
            if score <= 0:
                continue
            hits.append(Hit(chunk=chunk, score=score, lexical=lexical, exact=exact, dense=dense))

        hits.sort(key=lambda hit: hit.score, reverse=True)

        if dedupe:
            hits = _dedupe(hits)

        return hits[:limit]


def _dedupe(hits: list[Hit]) -> list[Hit]:
    """Drop chunks whose text is identical to one already kept.

    A real document repeats itself — a quoted paragraph, a table restated later.
    Two identical hits push out answers that are actually different.
    """
    seen: set[str] = set()
    unique: list[Hit] = []
    for hit in hits:
        key = hit.chunk.fingerprint or fingerprint(hit.chunk.text)
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return unique
