# corpuskit

Turn the PDFs you actually have into a clean, **traceable** knowledge base.

Built for Chinese documents, where the hard part is almost never the embedding
model — it is everything upstream of it.

## The pipeline

```
字符层   look-alike codepoints (⻆ vs 角)           → cjkfold ✅
抽取层   positions, running headers, tables        → this package ✅
分块层   中文没有空格，按 token 切会切碎语义         → 🚧
检索层   混合打分、去重、来源可溯                    → 🚧
```

`corpuskit` depends on [`cjkfold`](https://github.com/cdcailf/cjkfold) for the
character layer and does not duplicate it.

## Why positions are the whole game

Header/footer removal and column detection are **layout** questions. So is
"where exactly did this sentence come from?" — the answer a knowledge base has
to be able to give. None of them can be answered once coordinates are thrown
away.

So `extract` captures a bounding box for every block, and everything downstream
keeps it.

## ② Extraction

```python
from corpuskit import extract_pdf, extract_tables

doc = extract_pdf("report.pdf")          # every block, with coordinates
tables = extract_tables("report.pdf")    # rows of cells, structure intact
```

Tables are fetched separately on purpose: flattened into the ordinary text
stream, a table loses the row/column relationship that made it readable.

## Character cleanup

```python
from corpuskit import normalize

normalize("颜\u200b色\x07值")     # '颜色值'   — zero-width and control chars
normalize("\u2ec6\u2f8a")          # '角色'     — look-alike radicals
```

## Running headers and footers

The subtle part is that a footer usually carries a page number:

```
请务必阅读正文后免责条款部分 2
请务必阅读正文后免责条款部分 3
```

Exact matching never fires on those, so candidates are compared **after digits
are stripped**.

The second subtlety is the first page, which often carries extra text and
therefore appears only once:

```
国海证券研究所 请务必阅读正文后免责条款部分     ← page 1
请务必阅读正文后免责条款部分 2                ← pages 2+
```

No frequency threshold can catch that. A short candidate inside the header /
footer band that *contains* a known key is treated as boilerplate too. A long
repeated paragraph is never touched, so real content that happens to repeat
across pages survives.

```python
from corpuskit import extract_pdf, strip_boilerplate, normalize_document

doc = normalize_document(strip_boilerplate(extract_pdf("report.pdf")))
```

Measured on a real 15-page broker research report: 455 blocks in, **27 running
header/footer blocks removed**, no body text harmed.

## Install

`cjkfold` is not on PyPI yet, so install it from a sibling checkout first:

```bash
git clone https://github.com/cdcailf/cjkfold ../cjkfold
uv venv .venv --python 3.11
uv pip install -e ../cjkfold
uv pip install -e ".[dev]"
```

## Tests

```bash
.venv/bin/python -m pytest
```

Tests generate their own PDFs and build `Document` objects directly, so they
need no fixture files and no Chinese font.

## Roadmap

- [x] Extraction: PDF → blocks with coordinates
- [x] Character cleanup (via `cjkfold`)
- [x] Running header/footer detection and removal
- [ ] Multi-column detection and reading order
- [ ] Table extraction wired into the block model
- [ ] Chinese-aware chunking (split at 。！？, then merge to size)
- [ ] Hybrid retrieval: lexical + exact n-gram + optional vectors
- [ ] De-duplication and source attribution

## License

MIT
