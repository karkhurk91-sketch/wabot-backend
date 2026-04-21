import os
import uuid
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.utils import embedding_functions
from modules.common.logger import get_logger
from modules.common.database import AsyncSessionLocal
from modules.common.models import KnowledgeDocument
from sqlalchemy import select

logger = get_logger(__name__)

# Global clients per organization
_clients = {}
_collections = {}

def get_chroma_client(org_id: str, persist_dir: str = "./chroma_db"):
    """Get or create a ChromaDB client and collection for an organization."""
    if org_id not in _clients:
        store_path = os.path.join(persist_dir, str(org_id))
        os.makedirs(store_path, exist_ok=True)
        _clients[org_id] = chromadb.PersistentClient(path=store_path)
        # Use a SentenceTransformer embedding function
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        _collections[org_id] = _clients[org_id].get_or_create_collection(
            name="documents",
            embedding_function=embedding_fn
        )
    return _clients[org_id], _collections[org_id]

def index_document(doc_id: uuid.UUID, org_id: str, file_path: str, file_type: str):
    """Index a document into ChromaDB (synchronous)."""
    logger.info(f"Indexing document {doc_id} for org {org_id}, file: {file_path}")
    try:
        # Read file content based on extension
        content = ""
        if file_type == "txt":
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        elif file_type == "pdf":
            # Use pypdf for PDF extraction
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            content = "\n".join([page.extract_text() for page in reader.pages])
        elif file_type == "csv":
            import csv
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = [", ".join(row) for row in reader]
                content = "\n".join(rows)
        else:
            logger.warning(f"Unsupported file type: {file_type}")
            return

        # Split into chunks (simple split by paragraphs or length)
        chunks = []
        chunk_size = 1000
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i+chunk_size]
            chunks.append(chunk)

        # Add to ChromaDB
        _, collection = get_chroma_client(org_id)
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        collection.add(
            documents=chunks,
            ids=ids,
            metadatas=[{"doc_id": str(doc_id), "org_id": str(org_id), "chunk": i} for i in range(len(chunks))]
        )
        logger.info(f"Indexed {len(chunks)} chunks for doc {doc_id}")
    except Exception as e:
        logger.error(f"Failed to index document {doc_id}: {e}")

def search_knowledge(org_id: str, query: str, k: int = 3):
    """Search the knowledge base for relevant chunks."""
    try:
        _, collection = get_chroma_client(org_id)
        results = collection.query(query_texts=[query], n_results=k)
        if results and results['documents']:
            return results['documents'][0]
        return []
    except Exception as e:
        logger.error(f"Search failed for org {org_id}: {e}")
        return []