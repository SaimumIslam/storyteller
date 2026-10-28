"""Ingest pipeline: PDF/TXT -> chunks -> embeddings -> ChromaDB."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

import chromadb
import pdfplumber
from chromadb.config import Settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from .config import BookOverride, Config, get_config
from .ocr import ocr_pdf_page
from .textnorm import (
    char_ratios,
    dominant_lang,
    is_low_content,
    looks_like_back_matter,
    looks_like_cover_page,
    looks_like_front_matter,
    looks_like_index_page,
    normalize_bangla,
)

SUPPORTED_EXT = {".pdf", ".txt"}


# ---------- state ----------

def _load_state(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(path: Path, state: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- extraction ----------

def _clean(text: str) -> str:
    return normalize_bangla(text)


def _extract_pdf(path: Path, cfg: Config) -> list[tuple[int | None, str, str]]:
    """Returns list of (page_num, text, method)."""
    force_ocr = path.name in cfg.ocr.force_ocr_files
    override: BookOverride = cfg.book_overrides.get(path.name, BookOverride())
    pages: list[tuple[int | None, str, str]] = []

    dropped_front = dropped_back = dropped_explicit = 0
    dropped_index = dropped_short = dropped_cover = 0
    dropped_front_auto = dropped_back_auto = 0

    bp = cfg.boilerplate

    with pdfplumber.open(str(path)) as pdf:
        total = len(pdf.pages)
        front_cutoff = override.front_skip_pages
        back_cutoff = total - override.back_skip_pages
        skip_set = set(override.skip_pages)

        front_zone_end = max(int(total * bp.front_zone_ratio), 1)
        back_zone_start = total - max(int(total * bp.back_zone_ratio), 1) + 1

        in_front_matter = True
        content_seen_once = False

        for idx, page in enumerate(pdf.pages, start=1):
            if idx <= front_cutoff:
                dropped_front += 1
                continue
            if idx > back_cutoff:
                dropped_back += 1
                continue
            if idx in skip_set:
                dropped_explicit += 1
                continue

            text = "" if force_ocr else (page.extract_text() or "")
            text = _clean(text)
            method = "text"

            need_ocr = (force_ocr or len(text) < cfg.ocr.min_chars_per_page) and cfg.ocr.enabled
            if need_ocr:
                try:
                    ocr_text = ocr_pdf_page(path, idx, lang=cfg.ocr.lang, dpi=cfg.ocr.dpi)
                    if len(ocr_text) > len(text):
                        text = _clean(ocr_text)
                        method = "ocr"
                except Exception as e:
                    print(f"  [warn] OCR failed on {path.name} page {idx}: {e}")

            if not text:
                dropped_short += 1
                continue

            if bp.drop_cover_page and idx <= 3 and looks_like_cover_page(text):
                dropped_cover += 1
                continue

            if bp.drop_front_matter and in_front_matter and idx <= front_zone_end:
                hit = looks_like_front_matter(text)
                if hit:
                    dropped_front_auto += 1
                    continue

            if bp.drop_back_matter and idx >= back_zone_start:
                hit = looks_like_back_matter(text)
                if hit:
                    dropped_back_auto += 1
                    continue

            if is_low_content(text, bp.min_page_chars):
                dropped_short += 1
                continue
            if bp.drop_index_pages and looks_like_index_page(text):
                dropped_index += 1
                continue

            if not content_seen_once:
                content_seen_once = True
                in_front_matter = False

            pages.append((idx, text, method))

        print(
            f"  pages: {total}, kept: {len(pages)} | dropped: "
            f"front_cfg={dropped_front}, back_cfg={dropped_back}, explicit={dropped_explicit}, "
            f"cover={dropped_cover}, front_auto={dropped_front_auto}, back_auto={dropped_back_auto}, "
            f"index={dropped_index}, short={dropped_short}"
        )
    return pages


def _extract_txt(path: Path) -> list[tuple[int | None, str, str]]:
    text = _clean(path.read_text(encoding="utf-8", errors="ignore"))
    if not text:
        return []
    return [(None, text, "text")]


# ---------- chunking ----------

def _splitter(cfg: Config) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        separators=["\n\n", "\n", "।", ".", "!", "?", " ", ""],
        length_function=len,
    )


def _chunk_pages(
    pages: list[tuple[int | None, str, str]],
    splitter: RecursiveCharacterTextSplitter,
    cfg: Config,
) -> list[tuple[int | None, str, str, str, float]]:
    """Returns list of (page_num, chunk_text, method, lang, bn_ratio)."""
    lf = cfg.lang_filter
    out: list[tuple[int | None, str, str, str, float]] = []
    dropped_lang = 0
    for page_num, text, method in pages:
        for chunk in splitter.split_text(text):
            chunk = chunk.strip()
            if not chunk:
                continue
            ratios = char_ratios(chunk)
            bn = ratios["bn"]
            lang = dominant_lang(chunk)
            if lf.enabled and sum(ratios.get(sc, 0.0) for sc in lf.scripts) < lf.min_ratio:
                dropped_lang += 1
                continue
            out.append((page_num, chunk, method, lang, bn))
    if dropped_lang:
        print(f"  dropped {dropped_lang} chunks not in {'/'.join(lf.scripts)} script (lang_filter)")
    return out


# ---------- chroma ----------

def _get_collection(cfg: Config):
    client = chromadb.PersistentClient(
        path=str(cfg.chroma_path),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=cfg.collection,
        metadata={"hnsw:space": "cosine"},
    )


# ---------- main ----------

def ingest_all() -> None:
    cfg = get_config()
    cfg.books_dir.mkdir(parents=True, exist_ok=True)
    cfg.chroma_path.mkdir(parents=True, exist_ok=True)

    state = _load_state(cfg.state_file)
    collection = _get_collection(cfg)
    splitter = _splitter(cfg)

    files = sorted([p for p in cfg.books_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXT])
    if not files:
        print(f"No .pdf or .txt files found in {cfg.books_dir}")
        return

    embedder: SentenceTransformer | None = None
    new_count = 0

    for path in files:
        digest = _sha256(path)
        if digest in state:
            print(f"skip (already ingested): {path.name}")
            continue

        print(f"ingest: {path.name}")
        if path.suffix.lower() == ".pdf":
            pages = _extract_pdf(path, cfg)
        else:
            pages = _extract_txt(path)

        if not pages:
            print(f"  [warn] no text extracted from {path.name}")
            continue

        chunks = _chunk_pages(pages, splitter, cfg)
        if not chunks:
            print(f"  [warn] no chunks produced for {path.name}")
            continue

        if embedder is None:
            print(f"  loading embedder: {cfg.embedding_model}")
            embedder = SentenceTransformer(cfg.embedding_model)

        texts = [c[1] for c in chunks]
        ids = [f"{digest}:{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "book_title": path.stem,
                "source_file": path.name,
                "page": (c[0] if c[0] is not None else -1),
                "chunk_idx": i,
                "extraction_method": c[2],
                "lang": c[3],
                "bn_ratio": round(c[4], 3),
                "file_hash": digest,
            }
            for i, c in enumerate(chunks)
        ]

        print(f"  embedding {len(texts)} chunks...")
        embeddings = embedder.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
        ).tolist()

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        state[digest] = path.name
        _save_state(cfg.state_file, state)
        new_count += 1
        print(f"  done: {len(chunks)} chunks stored.")

    print(f"\nIngest complete. New files: {new_count}. Total tracked: {len(state)}.")


def list_books() -> Iterable[str]:
    cfg = get_config()
    state = _load_state(cfg.state_file)
    return state.values()
