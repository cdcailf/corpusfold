"""The shapes that travel through the pipeline.

Every piece of text keeps its coordinates all the way from extraction to the
final answer. Header/footer removal and column detection are *layout* questions;
they cannot be answered once the positions are gone, and neither can "where did
this sentence come from?", which a knowledge base has to be able to answer.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Block:
    """A positioned run of content on a page.

    ``kind`` is ``"text"`` for prose and ``"table"`` for a detected table,
    whose cells are also available as ``table``.
    """

    text: str
    page: int  # 1-based
    x0: float
    y0: float
    x1: float
    y1: float
    kind: str = "text"  # text | table
    table: list[list[str]] | None = None

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def flat(self) -> str:
        """Text with runs of whitespace collapsed — for matching, not display."""
        return " ".join(self.text.split())


@dataclass
class Page:
    number: int
    width: float
    height: float
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Document:
    source: str
    pages: list[Page] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def block_count(self) -> int:
        return sum(len(page.blocks) for page in self.pages)

    def blocks(self):
        """Every block, in page order."""
        for page in self.pages:
            yield from page.blocks
