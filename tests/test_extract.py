"""Extraction and boilerplate removal, against a PDF this test generates itself.

No Chinese font is required: the layout behaviour (positions, bands, repeated
running heads) is language-independent. Chinese behaviour is covered in
``test_clean.py`` with plain strings.
"""
from __future__ import annotations

import pymupdf
import pytest

from corpuskit import extract_pdf, find_boilerplate, strip_boilerplate


@pytest.fixture
def sample_pdf(tmp_path):
    """Three pages, each with a running header, a body line, and a footer."""
    path = tmp_path / "sample.pdf"
    pdf = pymupdf.open()
    for number in range(1, 4):
        page = pdf.new_page()  # A4
        page.insert_text((72, 60), f"Header line {number}")
        page.insert_text((72, 400), f"Body paragraph on page {number}")
        page.insert_text((72, 780), f"Confidential - page {number}")
    pdf.save(path)
    pdf.close()
    return path


def test_reads_every_page(sample_pdf):
    doc = extract_pdf(sample_pdf)
    assert doc.page_count == 3
    assert {block.page for block in doc.blocks()} == {1, 2, 3}
    assert doc.block_count >= 9


def test_blocks_keep_their_coordinates(sample_pdf):
    doc = extract_pdf(sample_pdf)
    for block in doc.blocks():
        assert block.x1 > block.x0
        assert block.y1 > block.y0
        assert 0 <= block.y0 <= 842


def test_page_size_is_captured(sample_pdf):
    doc = extract_pdf(sample_pdf)
    first = doc.pages[0]
    assert first.width == pytest.approx(595.3, abs=1)
    assert first.height == pytest.approx(841.9, abs=1)


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_pdf(tmp_path / "does-not-exist.pdf")


def test_running_header_and_footer_are_removed(sample_pdf):
    doc = extract_pdf(sample_pdf)

    stripped = strip_boilerplate(doc)

    remaining = [block.text for block in stripped.blocks()]
    assert not any("Header line" in text for text in remaining)
    assert not any("Confidential" in text for text in remaining)
    # ...and the actual content survived.
    assert sum("Body paragraph" in text for text in remaining) == 3


def test_boilerplate_detection_needs_most_of_the_pages(sample_pdf):
    """A line appearing once is content, not a running head."""
    doc = extract_pdf(sample_pdf)
    keys = find_boilerplate(doc)

    assert "Headerline" in keys
    assert "Confidential-page" in keys
    assert not any("Bodyparagraph" in key for key in keys)


def test_boilerplate_removal_is_a_copy(sample_pdf):
    doc = extract_pdf(sample_pdf)
    before = doc.block_count

    strip_boilerplate(doc)

    assert doc.block_count == before, "the original document must not be mutated"
