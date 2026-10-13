"""corpuskit — turn messy Chinese documents into a clean, traceable knowledge base.

    >>> from corpuskit import extract_pdf, strip_boilerplate, normalize_document, chunk_document
    >>> doc = normalize_document(strip_boilerplate(extract_pdf("report.pdf")))
    >>> chunks = chunk_document(doc)
"""
from .chunk import Chunk, chunk_document, fingerprint, split_sentences
from .clean import (
    boilerplate_key,
    find_boilerplate,
    is_toc_entry,
    normalize,
    normalize_document,
    strip_boilerplate,
)
from .embedding import Embedder, OpenAIEmbedder, cosine
from .extract import extract_pdf, extract_tables, rows_to_text, split_rows
from .layout import by_position, detect_columns, is_full_width, page_order, reading_order
from .model import Block, Document, Page
from .search import Hit, Index, bigrams, index_text

__version__ = "0.1.0"

__all__ = [
    "Block",
    "Chunk",
    "Document",
    "Embedder",
    "Hit",
    "Index",
    "OpenAIEmbedder",
    "Page",
    "bigrams",
    "boilerplate_key",
    "by_position",
    "chunk_document",
    "cosine",
    "detect_columns",
    "extract_pdf",
    "extract_tables",
    "find_boilerplate",
    "fingerprint",
    "index_text",
    "is_full_width",
    "is_toc_entry",
    "normalize",
    "normalize_document",
    "page_order",
    "reading_order",
    "rows_to_text",
    "split_rows",
    "split_sentences",
    "strip_boilerplate",
]
