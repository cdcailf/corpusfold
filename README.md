# corpusfold

Turn the PDFs you actually have into a clean, **traceable** knowledge base.

Built for Chinese documents, where the hard part is almost never the embedding
model — it is everything upstream of it.

```python
from corpusfold import extract_pdf, strip_boilerplate, normalize_document, chunk_document, Index

doc = normalize_document(strip_boilerplate(extract_pdf("report.pdf")))
index = Index(chunk_document(doc))

for hit in index.search("近两月上市公司数量和平均涨幅", limit=3):
    print(hit.score, hit.label)   # report.pdf p.5
    print(hit.chunk.text[:80])
```

## The pipeline

```
字符层   look-alike codepoints (⻆ vs 角)      → cjkfold ✅
抽取层   positions, tables, running headers   → ✅
版面层   分栏、阅读顺序                        → ✅
分块层   中文没有空格，标点才是语义边界        → ✅
检索层   bigram BM25 + 精确命中 + 可选向量     → ✅
```

`corpusfold` depends on [`cjkfold`](https://github.com/cdcailf/cjkfold) for the
character layer and does not duplicate it.

## Six things that decide whether this works

### 1. Positions, not just text

Header/footer removal, column detection, and "where did this sentence come
from?" are all **layout** questions. None can be answered once coordinates are
thrown away, so extraction captures a bounding box for every block and
everything downstream keeps it.

### 2. A footer's page number defeats exact matching

```
请务必阅读正文后免责条款部分 2
请务必阅读正文后免责条款部分 3
```

Never equal, so naive dedup never fires — candidates are compared **after
digits are stripped**. And the first page carries extra text, so it appears
exactly once:

```
国海证券研究所 请务必阅读正文后免责条款部分     ← page 1
请务必阅读正文后免责条款部分 2                ← pages 2+
```

No frequency threshold catches that. A short candidate inside the header band
that *contains* a known key is treated as boilerplate too — while a long
paragraph repeating on every page is left alone.

### 3. A contents page outranks the body it points at

```
3、 风险提示 ............................... 8
```

A contents page contains exactly the words a reader would search for and none
of the substance, so **it wins**. Dot-leader entries are dropped at chunk time.
Ordinary prose ellipsis `……` is unaffected.

### 4. A full-width element bridges the gutter

A two-column page read positionally interleaves the columns. But a title or a
wide table **spans** the gutter — include it in column detection and the page
projection is welded solid, so no gutter is ever found. Full-width blocks are
excluded from detection and hoisted to the top of the page.

### 5. A table is not prose

Flattened into the text stream, a table's column headers drift away from its
values. Tables are extracted as structured blocks, and the text inside their
bounding box is **dropped** — otherwise the same numbers are indexed twice and
a fragment can outrank the row it belongs to.

A table is atomic: splitting it mid-table scatters the headers. Only a table too
large to read as one passage is sliced — and then **every slice repeats the
header**, so a slice read alone still says what its numbers mean.

### 6. Chunk *after* finding boundaries, not before

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
hit = index.search("紫色独角兽协议编号")[0]
hit.chunk.text                   # the passage
hit.label                        # 'report.pdf p.3-4' — provenance, always
hit.lexical, hit.exact, hit.dense  # components, kept separate
```

- **Character bigrams, not words.** Chinese has no spaces and a tokenizer is a
  heavy dependency with failure modes of its own.
- **Lexical first, exact-match bonus on top.** Dense scores are bad at literal
  tokens; `cjkfold`'s character n-gram overlap puts them back.
- **Dense is optional and off by default.** Pass any object with
  `encode(texts) -> list[list[float]]` as `embedder=`. `OpenAIEmbedder` talks to
  any OpenAI-compatible endpoint over urllib, so enabling it adds **no**
  dependency. A chunk with no literal overlap can still be retrieved on the
  dense score alone.

Identical passages collapse before results are returned.

## Measured on a real document

A 15-page broker research report (dense Chinese, multi-column, heavy tables):

| Stage | Result |
|---|---|
| Extract | 15 pages, 455 raw blocks, **17 tables** |
| Structure | table interiors de-duplicated → 326 blocks |
| Boilerplate | 27 running header/footer blocks removed |
| Columns | 5 of 15 pages detected as multi-column |
| Chunk | **52 chunks, median 411 chars, max 775** — inside the hard maximum |
| Retrieve | top hit for each query was body text, with page provenance |

## Install

```bash
pip install corpusfold
```

Working on it from a checkout instead:

```bash
uv venv .venv --python 3.11
uv pip install -e ".[dev]"
```

## Command line

No code required:

```bash
corpusfold inspect 研报.pdf                      # 流水线对这份文档做了什么
corpusfold build 研报.pdf -o index.json           # 建索引
corpusfold search "近两月上市公司数量和平均涨幅" -i index.json
```

`inspect` — the fastest way to judge whether this is worth your time:

```
研报.pdf
  页数        15
  原始块      326
  表格        17 个
  页眉页脚    删掉 27 块
  多栏页      5 / 15
  分块        52 个，中位 411 字，最大 775 字
  预览
    [研报.pdf p.1] 2023 年01 月15 日专题研究新股研究…
```

`search` — every hit says where it came from:

```
1. 1.068   研报.pdf p.5-6
   资料来源：Wind，国海证券研究所…上市首日平均涨幅12.10%，上市以来平均涨幅8.31%…
```

## Tests

```bash
.venv/bin/python -m pytest
```

64 tests. They generate their own PDFs and build `Document` objects directly —
no fixture files, no Chinese font, no network.

## Roadmap

- [x] Extraction: PDF → blocks with coordinates
- [x] Character cleanup (via `cjkfold`)
- [x] Running header/footer detection and removal
- [x] Contents pages kept out of the index
- [x] Multi-column detection and reading order
- [x] Tables as structured blocks, de-duplicated and sliced
- [x] Chinese-aware chunking with overlap and provenance
- [x] Hybrid retrieval: bigram BM25 + exact n-gram bonus + optional dense layer
- [x] Command line: `inspect` / `build` / `search`
- [ ] Section headings as breadcrumbs on each chunk
- [ ] OCR path for scanned pages

## License

MIT
