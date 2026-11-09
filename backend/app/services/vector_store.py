from functools import lru_cache
from app.config import settings
import uuid

@lru_cache
def client():
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError('qdrant-client is required for vector operations') from exc
    return QdrantClient(path=settings.qdrant_path)

def _models():
    try:
        from qdrant_client import models
    except ImportError as exc:
        raise RuntimeError('qdrant-client is required for vector operations') from exc
    return models

def ensure_collection():
    q=client(); models=_models()
    if not q.collection_exists(settings.qdrant_collection):
        q.create_collection(collection_name=settings.qdrant_collection,
            vectors_config=models.VectorParams(size=384,distance=models.Distance.COSINE))

def upsert_chunks(document_id: str, filename: str, chunks: list[dict]):
    from app.services.embedding_service import embed_texts
    models=_models(); ensure_collection()
    vectors=embed_texts([c['text'] for c in chunks]); points=[]
    for c,vector in zip(chunks,vectors):
        points.append(models.PointStruct(id=str(uuid.uuid4()),vector=vector,payload={
          'document_id':document_id,'document_name':filename,'chunk_id':c['chunk_id'],
          'text':c['text'],'metadata':c.get('metadata',{})}))
    client().upsert(collection_name=settings.qdrant_collection,points=points,wait=True)

def search_chunks(query: str, limit: int|None=None):
    from app.services.embedding_service import embed_query
    ensure_collection(); vector=embed_query(query)
    response=client().query_points(collection_name=settings.qdrant_collection,query=vector,
        limit=limit or settings.top_k,with_payload=True)
    return [{'score':p.score,**(p.payload or {})} for p in response.points]

def delete_document_vectors(document_id: str):
    models=_models(); q=client()
    if q.collection_exists(settings.qdrant_collection):
        q.delete(collection_name=settings.qdrant_collection,points_selector=models.FilterSelector(
          filter=models.Filter(must=[models.FieldCondition(key='document_id',match=models.MatchValue(value=document_id))])),wait=True)
