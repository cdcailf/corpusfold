"""Command line: build an index, search it, and see what the pipeline did.

    corpusfold inspect report.pdf
    corpusfold build report.pdf -o index.json
    corpusfold search "近两月上市公司数量" -i index.json

Deliberately argparse rather than a CLI framework. The package's whole claim is
that it works without dragging in dependencies, and the command surface is
three verbs — a framework would cost more than it saves.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import asdict
from pathlib import Path

from .chunk import Chunk, chunk_document
from .clean import normalize_document, strip_boilerplate
from .extract import extract_pdf
from .layout import detect_columns
from .search import Index

INDEX_VERSION = 1
DEFAULT_INDEX = "corpusfold-index.json"


def load_document(path: Path) -> tuple[list, dict]:
    """Extract, strip and clean, plus the facts worth reporting afterwards."""
    raw = extract_pdf(path)
    stripped = strip_boilerplate(raw)
    cleaned = normalize_document(stripped)

    facts = {
        "pages": raw.page_count,
        "raw_blocks": raw.block_count,
        "tables": sum(1 for page in raw.pages for block in page.blocks if block.kind == "table"),
        "boilerplate_removed": raw.block_count - stripped.block_count,
        "column_pages": sum(1 for page in raw.pages if len(detect_columns(page)) > 1),
        "blocks": cleaned.block_count,
    }
    return chunk_document(cleaned), facts


def chunk_to_dict(chunk: Chunk) -> dict:
    data = asdict(chunk)
    data["pages"] = list(chunk.pages)
    return data


def chunk_from_dict(data: dict) -> Chunk:
    return Chunk(
        text=data["text"],
        source=data["source"],
        ordinal=data["ordinal"],
        page=data["page"],
        pages=tuple(data["pages"]),
        fingerprint=data.get("fingerprint", ""),
    )


# --- commands -------------------------------------------------------------

def cmd_inspect(args) -> int:
    """Show what the pipeline did to a document — the quickest way to judge it."""
    for name in args.files:
        path = Path(name)
        if not path.exists():
            print(f"找不到文件：{name}", file=sys.stderr)
            return 1

        chunks, facts = load_document(path)
        sizes = [len(chunk.text) for chunk in chunks] or [0]

        print(f"{path.name}")
        print(f"  页数        {facts['pages']}")
        print(f"  原始块      {facts['raw_blocks']}")
        print(f"  表格        {facts['tables']} 个")
        print(f"  页眉页脚    删掉 {facts['boilerplate_removed']} 块")
        print(f"  多栏页      {facts['column_pages']} / {facts['pages']}")
        print(
            f"  分块        {len(chunks)} 个，"
            f"中位 {int(statistics.median(sizes))} 字，最大 {max(sizes)} 字"
        )
        if args.preview and chunks:
            print("  预览")
            for chunk in chunks[: args.preview]:
                head = chunk.text[:56].replace("\n", " ")
                print(f"    [{chunk.label}] {head}…")
        print()
    return 0


def cmd_build(args) -> int:
    chunks: list[Chunk] = []
    sources: list[str] = []

    for name in args.files:
        path = Path(name)
        if not path.exists():
            print(f"找不到文件：{name}", file=sys.stderr)
            return 1
        found, _ = load_document(path)
        chunks.extend(found)
        sources.append(str(path))

    payload = {
        "version": INDEX_VERSION,
        "sources": sources,
        "chunks": [chunk_to_dict(chunk) for chunk in chunks],
    }
    out = Path(args.out)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(chunks)} 个块 → {out}")
    return 0


def cmd_search(args) -> int:
    path = Path(args.index)
    if not path.exists():
        print(f"找不到索引：{args.index}（先用 corpusfold build 建一个）", file=sys.stderr)
        return 1

    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks = [chunk_from_dict(item) for item in payload.get("chunks", [])]
    if not chunks:
        print("索引里没有块。", file=sys.stderr)
        return 1

    hits = Index(chunks).search(args.query, limit=args.limit)
    if not hits:
        print("没有匹配的段落。")
        return 1

    for rank, hit in enumerate(hits, start=1):
        print(f"{rank}. {hit.score:.3f}   {hit.label}")
        body = hit.chunk.text if args.full else hit.chunk.text[: args.width]
        print("   " + body.replace("\n", "\n   "))
        print()
    return 0


# --- entry point ----------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="corpusfold",
        description="把中文 PDF 变成能查、且答案带出处的知识库。",
        epilog="例子：corpusfold inspect 研报.pdf",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="看看流水线对一份文档做了什么")
    inspect.add_argument("files", nargs="+", help="PDF 路径")
    inspect.add_argument("--preview", type=int, default=3, help="预览几个块（0 表示不预览）")
    inspect.set_defaults(func=cmd_inspect)

    build = sub.add_parser("build", help="建一个可检索的索引")
    build.add_argument("files", nargs="+", help="PDF 路径，可以给多个")
    build.add_argument("-o", "--out", default=DEFAULT_INDEX, help=f"输出文件（默认 {DEFAULT_INDEX}）")
    build.set_defaults(func=cmd_build)

    search = sub.add_parser("search", help="在索引里查")
    search.add_argument("query", help="查询词")
    search.add_argument("-i", "--index", default=DEFAULT_INDEX, help=f"索引文件（默认 {DEFAULT_INDEX}）")
    search.add_argument("-n", "--limit", type=int, default=5, help="返回几条（默认 5）")
    search.add_argument("--width", type=int, default=200, help="每条显示多少字")
    search.add_argument("--full", action="store_true", help="显示完整段落")
    search.set_defaults(func=cmd_search)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
