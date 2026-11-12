
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def model():
    from fastembed import TextEmbedding

    return TextEmbedding(
        model_name=settings.embedding_model,
        threads=2,
        providers=["CPUExecutionProvider"],
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    vectors = list(model().embed(texts))

    return [vector.tolist() for vector in vectors]


def embed_query(text: str) -> list[float]:
    vectors = list(model().query_embed(text))

    if not vectors:
        raise RuntimeError("Embedding model returned no query vector")

    return vectors[0].tolist()
