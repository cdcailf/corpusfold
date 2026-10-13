"""Page layout: which column a block belongs to, and in what order to read it.

Without this, a two-column page reads *across* the gutter: the first line of
the left column, then the first line of the right one. Every word is present
and the meaning is gone.

The subtlety is full-width elements. A title or a wide table spans the gutter,
so if it takes part in column detection it bridges the two columns and no
gutter is ever found. They are therefore excluded from detection and hoisted to
the top of the page instead.
"""
from __future__ import annotations

from .model import Block, Document, Page

# A block wider than this share of the page spans it (title, wide table), and
# takes no part in column detection.
FULL_WIDTH = 0.72

# The narrowest vertical strip, in points, that can separate two columns.
MIN_GUTTER = 24.0

# A column narrower than this share of the page cannot hold body text.
MIN_COLUMN = 0.12


def is_full_width(block: Block, page: Page) -> bool:
    """True for titles and wide tables — anything spanning the whole page."""
    if page.width <= 0:
        return True
    return (block.x1 - block.x0) >= page.width * FULL_WIDTH


def content_bounds(page: Page) -> tuple[float, float] | None:
    """The left and right edges of the text area, ignoring full-width blocks."""
    blocks = [b for b in page.blocks if not is_full_width(b, page)]
    if not blocks:
        return None
    return min(b.x0 for b in blocks), max(b.x1 for b in blocks)


def detect_columns(page: Page, *, step: float = 4.0) -> list[tuple[float, float]]:
    """Return the x-ranges of the page's columns, left to right.

    A single range covering the text area means no columns were found, which is
    the right answer for a single-column page.
    """
    bounds = content_bounds(page)
    if bounds is None:
        return []
    left, right = bounds
    if right - left <= 0:
        return [(left, right)]

    blocks = [b for b in page.blocks if not is_full_width(b, page)]
    last = int(right / step) + 1
    covered = [False] * (last + 2)
    for block in blocks:
        start = max(0, int(block.x0 / step))
        end = min(last, int(block.x1 / step))
        for i in range(start, end + 1):
            covered[i] = True

    # Rows of x that no block touches, strictly inside the text area, are
    # candidate gutters.
    gutters: list[tuple[float, float]] = []
    run: int | None = None
    for i in range(int(left / step), last + 1):
        if covered[i]:
            if run is not None:
                gutters.append((run * step, i * step))
                run = None
        elif run is None:
            run = i

    gutters = [(a, b) for a, b in gutters if b - a >= MIN_GUTTER]
    if not gutters:
        return [(left, right)]

    edges = [left, *[(a + b) / 2 for a, b in gutters], right]
    columns = [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]
    columns = [c for c in columns if c[1] - c[0] >= page.width * MIN_COLUMN]

    return columns if len(columns) > 1 else [(left, right)]


def page_order(page: Page) -> list[Block]:
    """One page's blocks in reading order.

    Full-width blocks come first, then each column top to bottom. A full-width
    block sitting *between* two columns is a known limitation: it is hoisted to
    the top of the page rather than left in place.
    """
    if not page.blocks:
        return []

    columns = detect_columns(page)
    if len(columns) <= 1:
        return by_position(page.blocks)

    ordered = by_position([b for b in page.blocks if is_full_width(b, page)])
    for left, right in columns:
        inside = [
            b
            for b in page.blocks
            if not is_full_width(b, page) and left <= (b.x0 + b.x1) / 2 <= right
        ]
        ordered.extend(by_position(inside))
    return ordered


def reading_order(document: Document) -> list[Block]:
    """Every block in the document, in the order a person would read them."""
    ordered: list[Block] = []
    for page in document.pages:
        ordered.extend(page_order(page))
    return ordered


def by_position(blocks: list[Block]) -> list[Block]:
    """Sort top-to-bottom, then left-to-right."""
    return sorted(blocks, key=lambda b: (round(b.y0, 1), b.x0))
