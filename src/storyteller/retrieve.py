"""Retrieval: topic -> top-k chunks from ChromaDB."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from .config import Config, get_config
from .textnorm import normalize_bangla


@dataclass
class RetrievedChunk:
    text: str
    book_title: str
    source_file: str
    page: int | None
    extraction_method: str
    score: float

    def cite(self) -> str:
        page = f"পৃ. {self.page}" if self.page and self.page > 0 else ""
        return f"{self.book_title}{(', ' + page) if page else ''}"


_embedder: SentenceTransformer | None = None


def _get_embedder(cfg: Config) -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(cfg.embedding_model)
    return _embedder


def _get_collection(cfg: Config):
    client = chromadb.PersistentClient(
        path=str(cfg.chroma_path),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=cfg.collection,
        metadata={"hnsw:space": "cosine"},
    )


def retrieve(topic: str, k: int | None = None) -> list[RetrievedChunk]:
    cfg = get_config()
    k = k if k is not None else cfg.retrieval_k

    embedder = _get_embedder(cfg)
    topic_norm = normalize_bangla(topic)
    query_emb = embedder.encode([topic_norm], normalize_embeddings=True).tolist()

    collection = _get_collection(cfg)
    res: dict[str, Any] = collection.query(
        query_embeddings=query_emb,
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    chunks: list[RetrievedChunk] = []
    for doc, meta, dist in zip(docs, metas, dists):
        page_val = meta.get("page")
        page = int(page_val) if isinstance(page_val, (int, float)) and page_val and page_val > 0 else None
        chunks.append(
            RetrievedChunk(
                text=doc,
                book_title=str(meta.get("book_title", "Unknown")),
                source_file=str(meta.get("source_file", "")),
                page=page,
                extraction_method=str(meta.get("extraction_method", "text")),
                score=1.0 - float(dist),
            )
        )
    return chunks
