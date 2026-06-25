"""
Retrieval-Augmented Generation (RAG) module for GUIDA.

Loads a JSON knowledge base of ISR lab facts, embeds each entry using the
Ollama embedding API at startup, then retrieves the top-k most relevant
entries at query time via cosine similarity.

No training required. The knowledge base is a plain JSON file — add new
facts by editing data/isr_knowledge.json and restarting the server.
"""
import json
import logging
import math
import os
import time
from pathlib import Path
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
_OLLAMA_EMBED_URL = f"{_OLLAMA_BASE_URL}/api/embeddings"
_EMBED_MODEL = "nomic-embed-text"
_DEFAULT_KB_PATH = Path(__file__).resolve().parents[3] / "data" / "isr_knowledge.json"


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed(text: str) -> Optional[List[float]]:
    try:
        resp = requests.post(
            _OLLAMA_EMBED_URL,
            json={"model": _EMBED_MODEL, "prompt": text},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception as exc:
        logger.warning(f"Embedding request failed: {exc}")
        return None


class KnowledgeRetriever:
    """
    Offline RAG retriever backed by a JSON knowledge base.

    Usage:
        retriever = KnowledgeRetriever()
        context = retriever.retrieve("Where is the bathroom?", top_k=2)
        # context is a plain string ready to inject into a system prompt
    """

    def __init__(self, kb_path: Path = _DEFAULT_KB_PATH):
        self._entries: List[dict] = []
        self._embeddings: List[List[float]] = []
        self._ready = False
        self._load_and_embed(kb_path)

    def _load_and_embed(self, kb_path: Path) -> None:
        if not kb_path.exists():
            logger.warning(f"Knowledge base not found at {kb_path}. RAG disabled.")
            return

        with open(kb_path, encoding="utf-8") as f:
            entries = json.load(f)

        logger.info(f"Embedding {len(entries)} knowledge base entries (one-time startup cost)...")
        t0 = time.perf_counter()

        embedded = []
        for entry in entries:
            vec = _embed(entry["text"])
            if vec is not None:
                embedded.append((entry, vec))
            else:
                logger.warning(f"Skipped entry '{entry.get('id')}' (embedding failed)")

        self._entries    = [e for e, _ in embedded]
        self._embeddings = [v for _, v in embedded]
        self._ready      = len(self._entries) > 0

        elapsed = time.perf_counter() - t0
        logger.info(f"RAG ready: {len(self._entries)}/{len(entries)} entries embedded in {elapsed:.1f}s")

    def retrieve(self, query: str, top_k: int = 2) -> str:
        """
        Return the top_k most relevant knowledge base entries as a formatted
        string suitable for injecting into a system prompt.

        Returns an empty string if RAG is disabled or no relevant entries found.
        """
        if not self._ready:
            return ""

        query_vec = _embed(query)
        if query_vec is None:
            return ""

        scores = [
            (_cosine_similarity(query_vec, entry_vec), entry)
            for entry_vec, entry in zip(self._embeddings, self._entries)
        ]
        scores.sort(key=lambda x: x[0], reverse=True)

        # Only inject entries that are actually relevant (threshold 0.6)
        relevant = [entry for score, entry in scores[:top_k] if score >= 0.6]

        if not relevant:
            return ""

        lines = ["[Building knowledge that may be relevant to this query:]"]
        for entry in relevant:
            lines.append(f"- {entry['text']}")

        return "\n".join(lines)

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def entry_count(self) -> int:
        return len(self._entries)
