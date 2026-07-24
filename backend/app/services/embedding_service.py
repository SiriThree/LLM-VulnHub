from __future__ import annotations

import hashlib
import math
import re
import warnings
from collections import Counter
from functools import lru_cache

from app.core.config import get_settings

try:
    from fastembed import TextEmbedding
except ImportError:  # pragma: no cover - used only when optional dependency is missing locally.
    TextEmbedding = None


TOKEN_RE = re.compile(r"[A-Za-z0-9_\-\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


@lru_cache(maxsize=1)
def get_embedding_model() -> TextEmbedding | None:
    if TextEmbedding is None:
        return None

    settings = get_settings()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*now uses mean pooling instead of CLS embedding.*")
        return TextEmbedding(
            model_name=settings.embedding_model,
            cache_dir=settings.embedding_cache_dir,
        )


def _hash_embed_text(text: str) -> list[float]:
    dim = get_settings().embedding_dim
    vector = [0.0] * dim
    counts = Counter(tokenize(text))
    for token, count in counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1 if digest[4] % 2 == 0 else -1
        vector[idx] += sign * (1 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    model = get_embedding_model()
    if model is None:
        return [_hash_embed_text(text) for text in texts]

    vectors = model.embed([text or "" for text in texts])
    return [[round(float(value), 7) for value in vector] for vector in vectors]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return max(0.0, min(1.0, dot / (na * nb)))
