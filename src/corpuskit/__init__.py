"""corpuskit — turn messy Chinese documents into a clean, traceable knowledge base.

    >>> from corpuskit import extract_pdf, strip_boilerplate, normalize_document, chunk_document
    >>> doc = normalize_document(strip_boilerplate(extract_pdf("report.pdf")))
    >>> chunks = chunk_document(doc)
"""
from .chunk import Chunk, chunk_document, fingerprint, reading_order, split_sentences
from .clean import (
    boilerplate_key,
    find_boilerplate,
    is_toc_entry,
    normalize,
    normalize_document,
    strip_boilerplate,
)
from .extract import extract_pdf, extract_tables
from .model import Block, Document, Page
from .search import Hit, Index, bigrams, index_text

__version__ = "0.1.0"

__all__ = [
    "Block",
    "Chunk",
    "Document",
    "Hit",
    "Index",
    "Page",
    "bigrams",
    "boilerplate_key",
    "chunk_document",
    "extract_pdf",
    "extract_tables",
    "find_boilerplate",
    "fingerprint",
    "index_text",
    "is_toc_entry",
    "normalize",
    "normalize_document",
    "reading_order",
    "split_sentences",
    "strip_boilerplate",
]
