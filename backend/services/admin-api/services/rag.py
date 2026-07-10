"""
Qube Admin API — RAG Engine (in-memory)
Simple retrieval-augmented generation document store.
Designed to be replaced with a real vector DB in a future phase.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


class RAGEngine:
    """In-memory RAG document store with basic keyword search."""

    def __init__(self) -> None:
        # List of {"id", "text", "source", "language", "chunks", "created_at"}
        self._docs: list[dict] = []

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def add_texts(
        self,
        texts: list[str],
        source: str = "manual",
        language: str = "auto",
    ) -> int:
        """Ingest a list of text chunks. Returns number of chunks added."""
        added = 0
        for text in texts:
            if not text or not text.strip():
                continue
            doc_id = str(uuid.uuid4())
            self._docs.append(
                {
                    "id": doc_id,
                    "text": text,
                    "source": source,
                    "language": language,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            added += 1
        return added

    async def delete_document(self, doc_id: str) -> bool:
        before = len(self._docs)
        self._docs = [d for d in self._docs if d["id"] != doc_id]
        return len(self._docs) < before

    def delete_by_source(self, source: str) -> int:
        before = len(self._docs)
        self._docs = [d for d in self._docs if d["source"] != source]
        return before - len(self._docs)

    def clear(self) -> None:
        self._docs.clear()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        total_bytes = sum(len(d["text"].encode()) for d in self._docs)
        by_lang: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for d in self._docs:
            by_lang[d["language"]] = by_lang.get(d["language"], 0) + 1
            by_source[d["source"]] = by_source.get(d["source"], 0) + 1
        return {
            "doc_count": len(self._docs),
            "index_size_bytes": total_bytes,
            "last_updated": self._docs[-1]["created_at"] if self._docs else None,
            "by_language": by_lang,
            "by_source": by_source,
        }

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        language: str | None = None,
    ) -> list[dict]:
        """Simple keyword search (to be replaced with embeddings)."""
        query_lower = query.lower()
        scored: list[tuple[float, dict]] = []
        for doc in self._docs:
            if language and doc["language"] not in (language, "auto", "unknown"):
                continue
            text_lower = doc["text"].lower()
            # Score = count of query tokens found in text
            tokens = query_lower.split()
            score = sum(text_lower.count(tok) for tok in tokens)
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": d["id"],
                "source": d["source"],
                "language": d["language"],
                "score": s,
                "text": d["text"][:500],
            }
            for s, d in scored[:top_k]
        ]

    async def search_documents(
        self,
        query: str = "",
        language: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List documents, optionally filtered."""
        results = self._docs
        if language:
            results = [d for d in results if d["language"] == language]
        if query:
            q = query.lower()
            results = [d for d in results if q in d["text"].lower() or q in d["source"].lower()]
        return [
            {
                "id": d["id"],
                "source": d["source"],
                "language": d["language"],
                "created_at": d["created_at"],
                "preview": d["text"][:200],
            }
            for d in results[-limit:]
        ]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_engine: RAGEngine | None = None


def get_rag_engine() -> RAGEngine:
    global _engine
    if _engine is None:
        _engine = RAGEngine()
    return _engine
