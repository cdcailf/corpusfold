"""The command line: inspect, build, search — including the failure paths."""
from __future__ import annotations

import json

import pymupdf
import pytest

from corpusfold import cli


@pytest.fixture
def sample_pdf(tmp_path):
    path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "The unicorn protocol numbers each request.")
    page.insert_text((72, 140), "A second sentence about the unicorn protocol.")
    doc.save(path)
    doc.close()
    return path


def test_inspect_reports_what_the_pipeline_did(capsys, sample_pdf):
    assert cli.main(["inspect", str(sample_pdf)]) == 0

    out = capsys.readouterr().out
    assert "页数" in out
    assert "分块" in out
    assert "sample.pdf" in out


def test_build_then_search_round_trip(capsys, tmp_path, sample_pdf):
    index_path = tmp_path / "index.json"
    assert cli.main(["build", str(sample_pdf), "-o", str(index_path)]) == 0
    assert index_path.exists()

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["version"] == cli.INDEX_VERSION
    assert payload["chunks"]
    assert payload["sources"] == [str(sample_pdf)]

    capsys.readouterr()
    assert cli.main(["search", "unicorn protocol", "-i", str(index_path)]) == 0

    out = capsys.readouterr().out
    assert "unicorn" in out
    assert "sample.pdf p.1" in out, "the hit must show where it came from"


def test_search_says_so_when_nothing_matches(capsys, tmp_path, sample_pdf):
    index_path = tmp_path / "index.json"
    cli.main(["build", str(sample_pdf), "-o", str(index_path)])
    capsys.readouterr()

    assert cli.main(["search", "量子计算机", "-i", str(index_path)]) == 1
    assert "没有匹配" in capsys.readouterr().out


def test_building_from_a_missing_file_fails_cleanly(capsys, tmp_path):
    code = cli.main(["build", str(tmp_path / "nope.pdf"), "-o", str(tmp_path / "i.json")])
    assert code == 1
    assert "找不到" in capsys.readouterr().err


def test_searching_a_missing_index_fails_cleanly(capsys, tmp_path):
    assert cli.main(["search", "甲", "-i", str(tmp_path / "nope.json")]) == 1
    assert "找不到索引" in capsys.readouterr().err


def test_searching_an_empty_index_fails_cleanly(capsys, tmp_path):
    index_path = tmp_path / "empty.json"
    index_path.write_text(json.dumps({"version": 1, "sources": [], "chunks": []}), encoding="utf-8")

    assert cli.main(["search", "甲", "-i", str(index_path)]) == 1
    assert "没有块" in capsys.readouterr().err


def test_a_chunk_survives_the_json_round_trip(tmp_path, sample_pdf):
    """The index on disk must rebuild the same passages, provenance included."""
    index_path = tmp_path / "index.json"
    cli.main(["build", str(sample_pdf), "-o", str(index_path)])

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    rebuilt = [cli.chunk_from_dict(item) for item in payload["chunks"]]

    assert rebuilt[0].text == payload["chunks"][0]["text"]
    assert rebuilt[0].pages == tuple(payload["chunks"][0]["pages"])
    assert rebuilt[0].label == "sample.pdf p.1"
    assert rebuilt[0].fingerprint == payload["chunks"][0]["fingerprint"]
