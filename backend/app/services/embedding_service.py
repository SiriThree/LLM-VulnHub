import math
import warnings
from functools import lru_cache

from fastembed import TextEmbedding

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_embedding_model() -> TextEmbedding:
    settings = get_settings()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*now uses mean pooling instead of CLS embedding.*")
        return TextEmbedding(
            model_name=settings.embedding_model,
            cache_dir=settings.embedding_cache_dir,
        )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = get_embedding_model().embed([text or "" for text in texts])
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
