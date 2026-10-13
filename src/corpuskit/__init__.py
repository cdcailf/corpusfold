"""corpuskit — turn messy Chinese documents into a clean, traceable knowledge base.

    >>> from corpuskit import extract_pdf, strip_boilerplate, normalize_document
    >>> doc = normalize_document(strip_boilerplate(extract_pdf("report.pdf")))
"""
from .clean import (
    boilerplate_key,
    find_boilerplate,
    normalize,
    normalize_document,
    strip_boilerplate,
)
from .extract import extract_pdf, extract_tables
from .model import Block, Document, Page

__version__ = "0.1.0"

__all__ = [
    "Block",
    "Document",
    "Page",
    "boilerplate_key",
    "extract_pdf",
    "extract_tables",
    "find_boilerplate",
    "normalize",
    "normalize_document",
    "strip_boilerplate",
]
