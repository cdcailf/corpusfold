"""Cleaning: characters first, then layout boilerplate.

Two separate problems live here:

1. **Characters** — look-alike codepoints, zero-width junk, control characters.
   Handled by ``cjkfold`` plus a small table.
2. **Boilerplate** — running headers and footers. These are a *layout* problem,
   so this module needs the coordinates that :mod:`corpuskit.extract` preserved.

The subtle part is that footers usually carry a page number::

    请务必阅读正文后免责条款部分 2
    请务必阅读正文后免责条款部分 3

Exact-match deduplication never fires on those. Candidates are therefore
compared after digits are stripped.
"""
from __future__ import annotations

import re
from collections import Counter

import cjkfold

from .model import Block, Document, Page

# Control characters that survive PDF extraction. Newline and tab are kept —
# they carry structure we still want.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Zero-width and bidi controls: invisible, and they break exact matching.
_ZERO_WIDTH = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
_DIGITS = re.compile(r"\d+")
# A contents-page entry: a run of dot leaders, usually running to a page number.
# Deliberately does not match "……" (U+2026), which is ordinary prose.
_TOC_ENTRY = re.compile(r"[.．]{4,}\s*\d*\s*$")


def is_toc_entry(text: str) -> bool:
    """True for a contents line such as ``3、 风险提示 ............ 8``.

    A contents page is a retrieval trap: it contains exactly the words a reader
    would search for and none of the substance, so it ranks *above* the body it
    points at. Callers that build a search index should skip these.
    """
    return bool(_TOC_ENTRY.search(text.strip()))


def normalize(text: str) -> str:
    """Character-level cleanup for a single run of text."""
    text = cjkfold.fold(text)  # look-alike glyphs -> their ideograph
    text = _ZERO_WIDTH.sub("", text)
    text = _CONTROL.sub("", text)
    text = re.sub(r"[ \t\u3000]+", " ", text)  # incl. the ideographic space
    return text.strip()


def boilerplate_key(text: str) -> str:
    """The comparison key for a header/footer candidate.

    Digits are removed so that a footer which carries a page number still
    compares equal across pages.
    """
    return re.sub(r"\s+", "", _DIGITS.sub("", normalize(text)))


def find_boilerplate(
    document: Document,
    *,
    band: float = 0.12,
    min_ratio: float = 0.4,
    max_chars: int = 80,
) -> set[str]:
    """Keys of short texts that repeat in the top or bottom band of many pages.

    ``band`` is the fraction of page height treated as header/footer territory,
    ``min_ratio`` the share of pages a key must appear on to count, and
    ``max_chars`` guards against classifying a real paragraph (or a table that
    happens to sit at the top of the page) as boilerplate.
    """
    counts: Counter[str] = Counter()

    for page in document.pages:
        top_edge = page.height * band
        bottom_edge = page.height * (1 - band)
        for block in page.blocks:
            in_band = block.y1 <= top_edge or block.y0 >= bottom_edge
            if not in_band:
                continue
            key = boilerplate_key(block.text)
            if key and len(key) <= max_chars:
                counts[key] += 1

    threshold = max(2, round(document.page_count * min_ratio))
    return {key for key, seen in counts.items() if seen >= threshold}


def strip_boilerplate(
    document: Document,
    keys: set[str] | None = None,
    *,
    band: float = 0.12,
    max_chars: int = 80,
) -> Document:
    """Return a copy of *document* with header/footer blocks removed.

    Safe to call with the result of :func:`find_boilerplate`, or with ``None``
    to detect and strip in one step.

    A first-page footer routinely carries extra text that later pages drop —
    ``国海证券研究所 请务必阅读正文后免责条款部分`` vs ``请务必阅读正文后免责条款部分 2`` —
    so it never equals a detected key and only appears once, which no frequency
    threshold can catch. A short candidate inside the header/footer band that
    *contains* a known key is therefore treated as boilerplate too.
    """
    if keys is None:
        keys = find_boilerplate(document)

    if not keys:
        return document

    def is_boilerplate(block: Block, page: Page) -> bool:
        key = boilerplate_key(block.text)
        if not key:
            return False
        if key in keys:
            return True
        # Only inside the band, and only if it is a short superset of a key.
        in_band = block.y1 <= page.height * band or block.y0 >= page.height * (1 - band)
        if not in_band or len(key) > max_chars * 2:
            return False
        return any(known in key for known in keys)

    pages = []
    for page in document.pages:
        kept = [block for block in page.blocks if not is_boilerplate(block, page)]
        pages.append(
            type(page)(number=page.number, width=page.width, height=page.height, blocks=kept)
        )

    return type(document)(source=document.source, pages=pages, metadata=document.metadata)


def normalize_document(document: Document) -> Document:
    """Apply :func:`normalize` to every block, dropping any that become empty."""
    pages = []
    for page in document.pages:
        kept = []
        for block in page.blocks:
            text = normalize(block.text)
            if text:
                kept.append(
                    Block(
                        text=text,
                        page=block.page,
                        x0=block.x0,
                        y0=block.y0,
                        x1=block.x1,
                        y1=block.y1,
                        kind=block.kind,
                    )
                )
        pages.append(
            type(page)(number=page.number, width=page.width, height=page.height, blocks=kept)
        )
    return type(document)(source=document.source, pages=pages, metadata=document.metadata)
