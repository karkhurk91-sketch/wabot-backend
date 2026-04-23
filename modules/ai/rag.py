import os
import uuid
import numpy as np
from fastembed import TextEmbedding
import chromadb
from modules.common.logger import get_logger

logger = get_logger(__name__)

_client_cache = {}
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        # Lightweight ONNX model (~50 MB)
        _embedding_model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5")
    return _embedding_model

def get_chroma_client(org_id: str, persist_dir: str = "./chroma_db"):
    if org_id not in _client_cache:
        store_path = os.path.join(persist_dir, str(org_id))
        os.makedirs(store_path, exist_ok=True)
        _client_cache[org_id] = chromadb.PersistentClient(path=store_path)
    return _client_cache[org_id]

def index_document(doc_id: uuid.UUID, org_id: str, file_path: str, file_type: str):
    logger.info(f"Indexing {file_path} for org {org_id}")
    try:
        # Read file content (simplified – only text files for now)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Split into chunks (simple by paragraphs)
        chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
        if not chunks:
            chunks = [content[:1000]]
        # Embed and store
        model = get_embedding_model()
        embeddings = list(model.embed(chunks))  # list of numpy arrays
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
            metadatas=[{"doc_id": str(doc_id), "org_id": org_id, "chunk": i} for i in range(len(chunks))]
        )
        logger.info(f"Indexed {len(chunks)} chunks")
    except Exception as e:
        logger.error(f"Indexing failed: {e}")

def search_knowledge(org_id: str, query: str, k: int = 3):
    try:
        model = get_embedding_model()
        query_embedding = list(model.embed([query]))[0].tolist()
        client = get_chroma_client(org_id)
        collection = client.get_collection("documents")
        results = collection.query(query_embeddings=[query_embedding], n_results=k)
        if results and results['documents']:
            return results['documents'][0]
        return []
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []