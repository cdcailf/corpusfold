"""Chinese-aware chunking.

The usual mistake is to cut to a size first and hunt for a boundary afterwards.
By then the sentence is already in half. The order has to be the other way
round::

    split into sentences  ->  merge up to a target size  ->  never across a paragraph

Chinese has no spaces, so sentence-final punctuation is the only reliable
semantic boundary the text offers.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import cjkfold

from .clean import is_toc_entry
from .model import Block, Document

# Split after a Chinese sentence-final mark, after an English period/question
# mark that is followed by whitespace (so "3.5" stays in one piece), or at a
# paragraph break.
_BOUNDARY = re.compile(r"(?<=[。！？；])|(?<=[.!?])(?=\s)|\n+")

# CJK characters take no space when concatenated; Latin ones do.
_NEEDS_SPACE = re.compile(r"[0-9A-Za-z)\]}>,.;:!?\"']$")


@dataclass
class Chunk:
    """A retrievable passage, carrying a pointer back to where it came from."""

    text: str
    source: str
    ordinal: int
    page: int
    pages: tuple[int, ...] = field(default_factory=tuple)
    fingerprint: str = ""

    @property
    def label(self) -> str:
        """Human-readable provenance, e.g. ``report.pdf p.3``."""
        if len(self.pages) > 1:
            return f"{self.source} p.{self.pages[0]}-{self.pages[-1]}"
        return f"{self.source} p.{self.page}"


def split_sentences(text: str) -> list[str]:
    """Split a run of text into sentences."""
    return [part.strip() for part in _BOUNDARY.split(text) if part and part.strip()]


def fingerprint(text: str) -> str:
    """Stable identity for a passage, used to drop exact duplicates.

    Normalised first, so two passages that differ only in look-alike glyphs or
    whitespace collapse to one.
    """
    normalized = re.sub(r"\s+", "", cjkfold.fold(text))
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def chunk_document(
    document: Document,
    *,
    target: int = 400,
    hard_max: int = 800,
    overlap: int = 1,
) -> list[Chunk]:
    """Break a document into overlapping passages.

    ``target`` is the size to aim for, measured at paragraph boundaries;
    ``hard_max`` the point at which a chunk is closed mid-paragraph;
    ``overlap`` how many trailing sentences are repeated at the start of the
    next chunk so an answer cannot fall into the gap between two chunks.

    A chunk may contain several short paragraphs. What must never happen is
    stopping *inside* one — hence the check at both levels: sentences guard the
    hard maximum, paragraph ends are where the target is applied.
    """
    blocks = reading_order(document)
    if not blocks:
        return []

    # Contents pages are dropped: they match queries better than the text they
    # point at, and add nothing but noise to a retrieved passage.
    blocks = [block for block in blocks if not is_toc_entry(block.text)]
    if not blocks:
        return []

    chunks: list[Chunk] = []
    pending: list[tuple[str, int]] = []  # sentences not yet published
    carry: list[tuple[str, int]] = []  # tail copied from the previous chunk

    def size(items: list[tuple[str, int]]) -> int:
        return sum(len(text) for text, _ in items)

    def current_size() -> int:
        return size(pending) + size(carry)

    def flush() -> None:
        nonlocal carry
        if not pending:
            return
        chunks.append(_build(document, len(chunks), carry + pending))
        carry = pending[-overlap:] if overlap > 0 else []
        pending.clear()

    for block in blocks:
        for sentence in split_sentences(block.text):
            pending.append((sentence, block.page))
            if current_size() >= hard_max:
                flush()

        # End of a paragraph — close here if we have reached the target size.
        if current_size() >= target:
            flush()

    flush()
    return chunks


def reading_order(document: Document) -> list[Block]:
    """Blocks in page order, then top-to-bottom, left-to-right.

    Deliberately simple: it does not yet reconstruct columns. Multi-column
    layouts are handled at the extraction layer, not here.
    """
    ordered: list[Block] = []
    for page in document.pages:
        ordered.extend(sorted(page.blocks, key=lambda b: (round(b.y0, 1), b.x0)))
    return ordered


def _build(document: Document, ordinal: int, items: list[tuple[str, int]]) -> Chunk:
    text = _join(text for text, _ in items)
    pages = tuple(sorted({page for _, page in items}))
    return Chunk(
        text=text,
        source=document.source,
        ordinal=ordinal,
        page=pages[0],
        pages=pages,
        fingerprint=fingerprint(text),
    )


def _join(parts) -> str:
    """Concatenate sentences, inserting a space only between Latin runs."""
    result = ""
    for part in parts:
        if result and _NEEDS_SPACE.search(result):
            result += " "
        result += part
    return result
