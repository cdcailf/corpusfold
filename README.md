# corpuskit

Turn the PDFs you actually have into a clean, **traceable** knowledge base.

Built for Chinese documents, where the hard part is almost never the embedding
model — it is everything upstream of it.

```python
from corpuskit import extract_pdf, strip_boilerplate, normalize_document, chunk_document, Index

doc = normalize_document(strip_boilerplate(extract_pdf("report.pdf")))
index = Index(chunk_document(doc))

for hit in index.search("近两月上市公司数量和平均涨幅", limit=3):
    print(hit.score, hit.label)   # report.pdf p.5
    print(hit.chunk.text)
```

## The pipeline

```
字符层   look-alike codepoints (⻆ vs 角)      → cjkfold ✅
抽取层   positions, running headers, tables   → ✅
分块层   中文没有空格，标点才是语义边界        → ✅
检索层   bigram BM25 + 精确命中 + 来源可溯     → ✅
```

`corpuskit` depends on [`cjkfold`](https://github.com/cdcailf/cjkfold) for the
character layer and does not duplicate it.

## Four things that decide whether this works

### 1. Positions, not just text

Header/footer removal and column detection are **layout** questions. So is
"where did this sentence come from?" — the answer a knowledge base has to give.
None of them can be answered once coordinates are thrown away, so `extract`
captures a bounding box for every block and everything downstream keeps it.

### 2. A footer's page number defeats exact matching

```
请务必阅读正文后免责条款部分 2
请务必阅读正文后免责条款部分 3
```

Those are never equal, so naive de-duplication never fires. Candidates are
compared **after digits are stripped**.

And the first page usually carries extra text, so it appears exactly once:

```
国海证券研究所 请务必阅读正文后免责条款部分     ← page 1
请务必阅读正文后免责条款部分 2                ← pages 2+
```

No frequency threshold catches that. A short candidate inside the header/footer
band that *contains* a known key is treated as boilerplate too — while a long
paragraph that repeats on every page is left alone.

### 3. A contents page outranks the body it points at

A table of contents contains exactly the words a reader would search for and
none of the substance:

```
3、 风险提示 ............................... 8
```

Left in the index, it **wins**. Contents entries (a run of dot leaders, usually
running to a page number) are therefore dropped at chunking time. Ordinary
prose ellipsis `……` is not affected.

### 4. Chunk *after* finding boundaries, not before

The common mistake is to cut to 500 characters and hunt for a boundary
afterwards — by then the sentence is already in half. The order is reversed:

```
split into sentences  →  merge up to a target size  →  never stop mid-paragraph
```

Chinese has no spaces, so sentence-final punctuation is the only reliable
semantic boundary the text offers. Neighbouring chunks repeat their last
sentence, so an answer cannot fall into the gap between two.

## Retrieval

```python
index = Index(chunks)
hits = index.search("紫色独角兽协议编号", limit=5)
hits[0].chunk.text     # the passage
hits[0].label          # 'report.pdf p.3-4'  — provenance, always
hits[0].lexical, hits[0].exact   # the two components, kept separate
```

Two decisions worth naming:

- **Character bigrams, not words.** Chinese has no spaces and a tokenizer is a
  heavy dependency with failure modes of its own. Indexing character bigrams
  needs none.
- **Lexical first, exact-match bonus on top.** Dense scores are bad at literal
  tokens; `cjkfold`'s character n-gram overlap puts them back. Both components
  are returned, so you can see which one did the work.

Identical passages collapse before results are returned — a real document
repeats itself, and two identical hits push out answers that differ.

## Measured on a real document

A 15-page broker research report (dense Chinese, multi-column, heavy tables):

| Stage | Result |
|---|---|
| Extract | 15 pages, 455 blocks |
| Boilerplate | 27 running header/footer blocks removed |
| Chunk | 32 chunks, median 472 chars, none over the hard max |
| Retrieve | top hit for each query was body text, with page provenance |

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

44 tests. They generate their own PDFs and build `Document` objects directly —
no fixture files, no Chinese font required.

## Roadmap

- [x] Extraction: PDF → blocks with coordinates
- [x] Character cleanup (via `cjkfold`)
- [x] Running header/footer detection and removal
- [x] Contents pages kept out of the index
- [x] Chinese-aware chunking with overlap and provenance
- [x] Hybrid retrieval: bigram BM25 + exact n-gram bonus, de-duplicated
- [ ] Multi-column detection and reading order
- [ ] Table extraction wired into the block model
- [ ] Optional dense/vector layer, with reranking
- [ ] Section headings as breadcrumbs on each chunk

## License

MIT
