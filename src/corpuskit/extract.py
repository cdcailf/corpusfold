"""PDF -> positioned blocks.

Deliberately thin on text, careful about structure. The interesting work
(boilerplate, columns, cleaning) needs coordinates, so this layer's job is to
capture them faithfully — and to keep tables *as tables*, because a table
flattened into the prose stream loses the row that gives its numbers meaning.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

from .model import Block, Document, Page

Rect = tuple[float, float, float, float]


def extract_pdf(path: str | Path) -> Document:
    """Read every page, with text blocks and detected tables."""
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

    table_blocks, table_rects = _read_tables(number, page)

    for x0, y0, x1, y1, text, _block_no, block_type in page.get_text("blocks"):
        # block_type 1 is a raster image; it carries no text worth keeping.
        if block_type != 0 or not text.strip():
            continue
        # Text inside a detected table is already carried by the table block.
        # Keeping both would index the same numbers twice and let a fragment
        # outrank the row it belongs to.
        if any(_centre_inside((x0, y0, x1, y1), box) for box in table_rects):
            continue
        result.blocks.append(Block(text=text, page=number, x0=x0, y0=y0, x1=x1, y1=y1))

    result.blocks.extend(table_blocks)
    return result


def _read_tables(number: int, page: "pymupdf.Page") -> tuple[list[Block], list[Rect]]:
    """Detected tables, as blocks plus the boxes they occupy."""
    try:
        found = page.find_tables().tables
    except Exception:  # noqa: BLE001 - a malformed page must not kill the run
        return [], []

    blocks: list[Block] = []
    boxes: list[Rect] = []
    for table in found:
        rows = _clean_rows(table.extract())
        if not rows:
            continue
        x0, y0, x1, y1 = table.bbox
        boxes.append((x0, y0, x1, y1))
        blocks.append(
            Block(
                text=rows_to_text(rows),
                page=number,
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                kind="table",
                table=rows,
            )
        )
    return blocks, boxes


def _clean_rows(raw) -> list[list[str]]:
    """Collapse whitespace inside cells and drop rows that are entirely empty."""
    rows: list[list[str]] = []
    for row in raw or []:
        cells = [" ".join((cell or "").split()) for cell in row]
        if any(cells):
            rows.append(cells)
    return rows


def rows_to_text(rows: list[list[str]]) -> str:
    """Render a table as delimited rows.

    A pipe keeps the cells of a row on one line, so a chunk that starts mid-way
    through a table still shows every value next to its column header.
    """
    return "\n".join(" | ".join(cells) for cells in rows)


def split_rows(rows: list[list[str]], budget: int) -> list[list[list[str]]]:
    """Group a table's rows into slices of at most *budget* characters.

    Every slice repeats the header, so a slice read on its own still says what
    its numbers mean. A long table is a useful passage; a four-thousand
    character one is a context bomb that buries every other result.
    """
    if len(rows) < 2:
        return [rows] if rows else []

    def row_size(cells: list[str]) -> int:
        # +1 for the newline rows_to_text will place after this row, so the
        # budget accounts for the rendered slice rather than just its cells.
        return len(" | ".join(cells)) + 1

    header, body = rows[0], rows[1:]
    header_size = row_size(header)

    slices: list[list[list[str]]] = []
    current: list[list[str]] = []
    size = header_size
    for row in body:
        if current and size + row_size(row) > budget:
            slices.append([header, *current])
            current, size = [], header_size
        current.append(row)
        size += row_size(row)
    if current:
        slices.append([header, *current])
    return slices


def _centre_inside(box: Rect, outer: Rect) -> bool:
    centre_x = (box[0] + box[2]) / 2
    centre_y = (box[1] + box[3]) / 2
    return outer[0] <= centre_x <= outer[2] and outer[1] <= centre_y <= outer[3]


def extract_tables(path: str | Path) -> list[list[list[str]]]:
    """Every table in the document, as rows of cells, in page order.

    ``extract_pdf`` already folds tables into its blocks; this is for callers
    that want the raw matrices and nothing else.
    """
    tables: list[list[list[str]]] = []
    with pymupdf.open(Path(path)) as pdf:
        for page in pdf:
            for table in page.find_tables().tables:
                rows = _clean_rows(table.extract())
                if rows:
                    tables.append(rows)
    return tables
