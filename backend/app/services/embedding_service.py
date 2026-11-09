from functools import lru_cache
from app.config import settings

@lru_cache
def model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.embedding_model)

def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = model().encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return vectors.tolist()

def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
