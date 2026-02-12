"""
Memory module — in-memory storage for conversation context and tool results.
Uses FAISS + Ollama embeddings for semantic retrieval.

Resets when the server restarts (no persistence to disk).
This is the second step in the agent loop:
  perception → memory → decision → action
"""

import numpy as np
import faiss
import requests
import logging
from typing import List, Optional, Literal
from pydantic import BaseModel
from datetime import datetime

log = logging.getLogger("email-assistant.memory")

EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"


class MemoryItem(BaseModel):
    text: str
    type: Literal["tool_output", "user_query", "perception", "plan"] = "tool_output"
    timestamp: Optional[str] = None
    tool_name: Optional[str] = None
    user_query: Optional[str] = None
    tags: List[str] = []
    session_id: Optional[str] = None

    def __init__(self, **data):
        if "timestamp" not in data or data["timestamp"] is None:
            data["timestamp"] = datetime.now().isoformat()
        super().__init__(**data)


class MemoryManager:
    """
    In-memory semantic memory using FAISS + Ollama embeddings.
    Stores tool outputs, user queries, and other context items.
    Supports semantic retrieval with optional filters.
    """

    def __init__(self):
        self.index = None
        self.data: List[MemoryItem] = []
        self.embeddings: List[np.ndarray] = []

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding from Ollama's nomic-embed-text model."""
        response = requests.post(
            EMBED_URL,
            json={"model": EMBED_MODEL, "prompt": text[:512]},  # cap input length
        )
        response.raise_for_status()
        return np.array(response.json()["embedding"], dtype=np.float32)

    def add(self, item: MemoryItem):
        """Add an item to memory with its embedding."""
        try:
            emb = self._get_embedding(item.text)
            self.embeddings.append(emb)
            self.data.append(item)

            if self.index is None:
                self.index = faiss.IndexFlatL2(len(emb))
            self.index.add(np.stack([emb]))

            log.info("Memory added: type=%s, tool=%s, text=%s",
                     item.type, item.tool_name, item.text[:80])
        except Exception as e:
            log.warning("Failed to add to memory: %s", e)

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        session_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
    ) -> List[MemoryItem]:
        """Retrieve the most relevant memories for a query."""
        if not self.index or len(self.data) == 0:
            return []

        try:
            query_vec = self._get_embedding(query).reshape(1, -1)
            k = min(top_k * 2, len(self.data))  # overfetch to allow filtering
            D, I = self.index.search(query_vec, k)

            results = []
            for idx in I[0]:
                if idx >= len(self.data):
                    continue
                item = self.data[idx]

                if type_filter and item.type != type_filter:
                    continue
                if session_filter and item.session_id != session_filter:
                    continue

                results.append(item)
                if len(results) >= top_k:
                    break

            log.info("Memory retrieved %d items for: %s", len(results), query[:60])
            return results
        except Exception as e:
            log.warning("Memory retrieval failed: %s", e)
            return []

    def clear(self):
        """Clear all memory."""
        self.index = None
        self.data = []
        self.embeddings = []
        log.info("Memory cleared")
