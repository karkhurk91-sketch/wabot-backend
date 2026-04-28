import os
import uuid
import numpy as np
from fastembed import TextEmbedding
from sentence_transformers import CrossEncoder
import chromadb
from sqlalchemy import text
from modules.common.database import sync_engine
from modules.common.logger import get_logger

logger = get_logger(__name__)

_client_cache = {}
_embedding_model = None
_reranker = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5")
    return _embedding_model

def get_reranker():
    global _reranker
    if _reranker is None:
        # Lightweight cross-encoder (fast, accurate enough for reranking)
        _reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    return _reranker

def get_chroma_client(org_id: str, persist_dir: str = "./chroma_db"):
    if org_id not in _client_cache:
        store_path = os.path.join(persist_dir, str(org_id))
        os.makedirs(store_path, exist_ok=True)
        _client_cache[org_id] = chromadb.PersistentClient(path=store_path)
    return _client_cache[org_id]

def index_document(doc_id: uuid.UUID, org_id: str, file_path: str, file_type: str):
    logger.info(f"Indexing {file_path} for org {org_id}")
    try:
        # Read file content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Split into chunks
        chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
        if not chunks:
            chunks = [content[:1000]]
        # Embed and store in ChromaDB
        model = get_embedding_model()
        embeddings = list(model.embed(chunks))
        client = get_chroma_client(org_id)
        collection = client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        collection.add(
            documents=chunks,
            embeddings=[e.tolist() for e in embeddings],
            ids=ids,
            metadatas=[{"doc_id": str(doc_id), "org_id": str(org_id), "chunk": i} for i in range(len(chunks))]        )
        # Also store the full content in the knowledge_documents table for keyword search
        with sync_engine.connect() as conn:
            conn.execute(
                text("UPDATE knowledge_documents SET content = :content WHERE id = :doc_id"),
                {"content": content, "doc_id": doc_id}
            )
            conn.commit()
        logger.info(f"Indexed {len(chunks)} chunks and stored text for doc {doc_id}")
    except Exception as e:
        logger.error(f"Indexing failed: {e}")

def hybrid_search(org_id: str, query: str, k: int = 10):
    """
    Returns up to `k` text chunks by combining vector search (ChromaDB)
    and keyword search (PostgreSQL full‑text). Results from both sources are merged.
    """
    chunks = []
    # 1. Vector search (semantic)
    try:
        model = get_embedding_model()
        query_embedding = list(model.embed([query]))[0].tolist()
        client = get_chroma_client(org_id)
        collection = client.get_collection("documents")
        vector_results = collection.query(query_embeddings=[query_embedding], n_results=k)
        if vector_results and vector_results['documents']:
            chunks.extend(vector_results['documents'][0])
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
    # 2. Keyword search (BM25 style via PostgreSQL full‑text)
    try:
        with sync_engine.connect() as conn:
            keyword_results = conn.execute(
                text("""
                    SELECT content
                    FROM knowledge_documents
                    WHERE organization_id = :org_id
                      AND to_tsvector('english', content) @@ plainto_tsquery('english', :query)
                    ORDER BY ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) DESC
                    LIMIT :k
                """),
                {"org_id": org_id, "query": query, "k": k}
            ).fetchall()
            chunks.extend([row.content for row in keyword_results])
    except Exception as e:
        logger.error(f"Keyword search failed: {e}")
    # Deduplicate (by content) while preserving order
    seen = set()
    unique_chunks = []
    for chunk in chunks:
        if chunk not in seen:
            seen.add(chunk)
            unique_chunks.append(chunk)
    return unique_chunks[:k]

def search_knowledge(org_id: str, query: str, k: int = 3) -> list:
    """
    Hybrid search + reranking. Fetches more candidates (k*3) then reranks.
    """
    # Get more candidates first (3x the required k)
    candidates = hybrid_search(org_id, query, k=k*3)
    if not candidates:
        return []
    # Rerank using cross-encoder
    reranker = get_reranker()
    pairs = [[query, doc] for doc in candidates]
    scores = reranker.predict(pairs)
    # Sort by score descending
    scored = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    # Return top k
    return [doc for doc, _ in scored[:k]]