"""PDF -> positioned blocks.

Deliberately thin. The interesting work (boilerplate, columns, cleaning) needs
coordinates, so this layer's only job is to capture them faithfully.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

from .model import Block, Document, Page


def extract_pdf(path: str | Path) -> Document:
    """Read every text block on every page, with its bounding box."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    with pymupdf.open(path) as pdf:
        pages = [_read_page(number, page) for number, page in enumerate(pdf, start=1)]
        metadata = {k: v for k, v in (pdf.metadata or {}).items() if v}

    return Document(source=str(path), pages=pages, metadata=metadata)


def _read_page(number: int, page: "pymupdf.Page") -> Page:
    rect = page.rect
    result = Page(number=number, width=rect.width, height=rect.height)

    for x0, y0, x1, y1, text, _block_no, block_type in page.get_text("blocks"):
        # block_type 1 is a raster image; it carries no text worth keeping here.
        if block_type != 0 or not text.strip():
            continue
        result.blocks.append(
            Block(text=text, page=number, x0=x0, y0=y0, x1=x1, y1=y1)
        )

    return result


def extract_tables(path: str | Path) -> list[list[list[str]]]:
    """Tables as rows of cells, per page order.

    Separate from :func:`extract_pdf` on purpose: a table flattened into the
    ordinary text stream loses the row/column relationship that makes it
    readable, so callers that care about tables ask for them explicitly.
    """
    tables: list[list[list[str]]] = []
    with pymupdf.open(Path(path)) as pdf:
        for page in pdf:
            for table in page.find_tables().tables:
                rows = [
                    [" ".join((cell or "").split()) for cell in row]
                    for row in table.extract()
                ]
                if rows:
                    tables.append(rows)
    return tables
