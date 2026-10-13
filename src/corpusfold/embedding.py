"""Optional dense (vector) retrieval.

Off unless you hand an ``embedder`` to :class:`~corpusfold.Index`. The default
install stays dependency-free and offline; turning the dense layer on is a
deliberate act, not something that happens because a dependency appeared.

Anything with ``encode(texts) -> list[list[float]]`` qualifies — a hosted API,
a local model, or a stub in a test. Only the shape matters.
"""
from __future__ import annotations

import json
import math
import os
import urllib.request
from typing import Protocol, Sequence


class Embedder(Protocol):
    """The whole interface the index needs: turn text into vectors."""

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        ...


class OpenAIEmbedder:
    """Embeddings from any OpenAI-compatible endpoint.

    Talks over urllib rather than an SDK, so enabling the dense layer does not
    change the dependency footprint — which is the point of keeping it optional.
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        *,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("CORPUSKIT_EMBEDDING_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = json.dumps({"model": self.model, "input": list(texts)}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read())
        ordered = sorted(body.get("data", []), key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in ordered]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity, floored at zero: a negative match is no match.

    Flooring matters for combining scores — without it an anti-correlated
    passage would *subtract* from the lexical evidence.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, dot / (norm_a * norm_b))
