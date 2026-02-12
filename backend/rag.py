"""
RAG module — FAISS-based document indexer for email attachments.

Chunks text, embeds via Ollama (nomic-embed-text), stores in FAISS.
Index is persisted to disk so documents survive server restarts.

Used by:
  - mcp_tools.py: auto-indexes attachments when get_email_attachments is called
  - mcp_tools.py: search_indexed_documents tool for RAG queries
"""

import json
import logging
import numpy as np
import faiss
import requests
from pathlib import Path
from typing import List

log = logging.getLogger("email-assistant.rag")

# Ollama embedding config
EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

# Chunking config
CHUNK_SIZE = 512
CHUNK_OVERLAP = 40

# Persist FAISS index inside backend/rag_index/
INDEX_DIR = Path(__file__).parent / "rag_index"
INDEX_DIR.mkdir(exist_ok=True)
INDEX_FILE = INDEX_DIR / "index.bin"
METADATA_FILE = INDEX_DIR / "metadata.json"


def _clean_text(text: str) -> str:
    """Remove non-printable and problematic characters from text."""
    import re
    # Keep only printable ASCII + common Unicode letters/punctuation
    text = re.sub(r'[^\x20-\x7E\n\r\t]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r' +', ' ', text)
    return text.strip()


def _get_embedding(text: str) -> np.ndarray:
    """Get embedding from Ollama's nomic-embed-text model."""
    # Clean and cap input length to avoid Ollama 500 errors
    clean = _clean_text(text)[:2000]
    response = requests.post(EMBED_URL, json={"model": EMBED_MODEL, "prompt": clean})
    response.raise_for_status()
    return np.array(response.json()["embedding"], dtype=np.float32)


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping word-based chunks."""
    # Clean text before chunking
    text = _clean_text(text)
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i : i + size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def index_document(title: str, content: str) -> dict:
    """
    Chunk a document, embed via Ollama, and store in FAISS (persisted to disk).
    Skips if a document with the same title is already indexed.

    Args:
        title: Document identifier (e.g. filename or email subject)
        content: Full text content of the document

    Returns:
        {"status": "indexed"|"already_indexed"|"empty", "title": ..., "chunks": int}
    """
    # Load existing index and metadata
    if INDEX_FILE.exists() and METADATA_FILE.exists():
        index = faiss.read_index(str(INDEX_FILE))
        metadata = json.loads(METADATA_FILE.read_text())
    else:
        index = None
        metadata = []

    # Check for duplicate
    if any(m.get("title") == title for m in metadata):
        log.info("Document '%s' already indexed, skipping", title)
        return {"status": "already_indexed", "title": title, "chunks": 0}

    # Chunk the document
    chunks = chunk_text(content)
    if not chunks:
        return {"status": "empty", "title": title, "chunks": 0}

    log.info("Indexing document '%s': %d chunks", title, len(chunks))

    # Embed each chunk
    embeddings = []
    for chunk in chunks:
        emb = _get_embedding(chunk)
        embeddings.append(emb)

    # Add to FAISS index
    stacked = np.stack(embeddings)
    if index is None:
        index = faiss.IndexFlatL2(stacked.shape[1])
    index.add(stacked)

    # Add metadata for each chunk
    for i, chunk in enumerate(chunks):
        metadata.append({
            "title": title,
            "chunk": chunk,
            "chunk_id": f"{title}_{i}",
        })

    # Save to disk
    faiss.write_index(index, str(INDEX_FILE))
    METADATA_FILE.write_text(json.dumps(metadata, indent=2))

    log.info("Indexed '%s': %d chunks saved to disk", title, len(chunks))
    return {"status": "indexed", "title": title, "chunks": len(chunks)}


def search_documents(query: str, top_k: int = 5) -> List[dict]:
    """
    Search indexed documents for relevant chunks using semantic similarity.

    Args:
        query: Natural language search query
        top_k: Number of results to return

    Returns:
        List of dicts with title, chunk text, and chunk_id
    """
    if not INDEX_FILE.exists() or not METADATA_FILE.exists():
        log.info("No RAG index found — nothing to search")
        return []

    try:
        index = faiss.read_index(str(INDEX_FILE))
        metadata = json.loads(METADATA_FILE.read_text())

        query_vec = _get_embedding(query).reshape(1, -1)
        k = min(top_k, index.ntotal)
        D, I = index.search(query_vec, k)

        results = []
        for idx in I[0]:
            if idx < len(metadata):
                data = metadata[idx]
                results.append({
                    "title": data["title"],
                    "chunk": data["chunk"],
                    "chunk_id": data["chunk_id"],
                })

        log.info("RAG search for '%s': found %d chunks", query[:60], len(results))
        return results

    except Exception as e:
        log.error("RAG search failed: %s", e)
        return []
