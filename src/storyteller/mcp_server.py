"""MCP server: expose the library to AI clients (Claude Code, Claude Desktop, Cursor, ...).

Two ways to write a post:
  - prepare_post + save_post: the client's own model writes the post from the
    retrieved sources. No OpenRouter key needed.
  - generate_post: the server writes it via OpenRouter (needs OPENROUTER_API_KEY).
"""
from __future__ import annotations

import contextlib
import io
import sys
from collections.abc import Callable
from typing import TypeVar

from mcp.server.fastmcp import FastMCP

from .config import get_config

T = TypeVar("T")

mcp = FastMCP("storyteller")


def _quiet(fn: Callable[[], T]) -> tuple[T, str]:
    """Run fn with stdout captured; stdout carries the MCP protocol and must stay clean."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn()
    log = buf.getvalue()
    if log:
        print(log, file=sys.stderr, end="")
    return result, log


@mcp.tool()
def library_info() -> str:
    """Show where books, index and output live, which books are ingested, and available styles.
    Call this first to orient yourself."""
    from .config import SUPPORTED_LANGUAGES
    from .ingest import list_books
    from .style import list_styles

    cfg = get_config()
    titles = list(list_books())
    styles = "; ".join(f"{lang}: {', '.join(list_styles(lang)) or '(none)'}" for lang in SUPPORTED_LANGUAGES)
    lines = [
        f"default language: {cfg.language} (supported: {', '.join(SUPPORTED_LANGUAGES)})",
        f"home: {cfg.home}",
        f"books folder (drop .pdf/.txt here): {cfg.books_dir}",
        f"posts: {cfg.output_dir}",
        f"facebook-ready copies: {cfg.copy_dir}",
        f"openrouter key: {'set' if cfg.openrouter_api_key else 'not set (generate_post unavailable; use prepare_post)'}",
        f"styles: {styles}",
        f"ingested books ({len(titles)}):",
        *[f"  - {t}" for t in titles],
    ]
    if not titles:
        lines.append("  (none yet: add files to the books folder, then call ingest_books)")
    return "\n".join(lines)


@mcp.tool()
def ingest_books() -> str:
    """Ingest new .pdf/.txt files from the books folder into the search index.
    Already-ingested files are skipped. The first run downloads the bge-m3 embedding
    model (~2 GB) and OCR of scanned PDFs can take many minutes; for big libraries,
    prefer running `storyteller ingest` in a terminal."""
    from .ingest import ingest_all

    _, log = _quiet(ingest_all)
    return log.strip() or "Ingest finished."


@mcp.tool()
def search_sources(topic: str, k: int = 6) -> str:
    """Return the top-k passages from the ingested books for a topic (Bangla or English),
    with book title and page for citation."""
    from .retrieve import retrieve

    chunks, _ = _quiet(lambda: retrieve(topic, k=k))
    if not chunks:
        return "No passages found. Check library_info: books may not be ingested yet."
    parts = []
    for i, c in enumerate(chunks, start=1):
        page = f", page {c.page}" if c.page else ""
        parts.append(f"[{i}] {c.book_title}{page} (score={c.score:.3f})\n{c.text}")
    return "\n\n---\n\n".join(parts)


@mcp.tool()
def prepare_post(
    topic: str,
    style: str | None = None,
    length: str | None = None,
    k: int | None = None,
    language: str | None = None,
) -> str:
    """Retrieve sources for a topic and return the full writing brief (rules, style,
    examples, sources, reference list). Write the post yourself by following the
    brief exactly, using only facts from the sources, then call save_post.
    length: short | medium | long. style: a style name for that language from library_info.
    language: bn (Bangla) | en (English); omit to use the configured default."""
    from .prompts import build_messages, deterministic_references
    from .retrieve import retrieve
    from .style import LENGTH_PRESETS, default_style, load_style

    if length and length not in LENGTH_PRESETS:
        return f"Invalid length. Choose one of: {', '.join(LENGTH_PRESETS)}"
    language = get_config().lang(language)
    if style:
        st = load_style(style, language)
        if length:
            st.length = length
    else:
        st = default_style(length=length)

    chunks, _ = _quiet(lambda: retrieve(topic, k=k))
    if not chunks:
        return "No passages found for this topic. Do not write a post; tell the user the books don't cover it."

    system, user = (m["content"] for m in build_messages(topic, chunks, style=st, language=language))
    refs = deterministic_references(chunks, language)
    return (
        "# Writing brief (follow as your instructions)\n\n"
        f"{system}\n\n# Task\n\n{user}\n\n"
        "# Reference list\n\nEnd the post with this exact block:\n\n"
        f"{refs}"
    )


@mcp.tool()
def save_post(topic: str, body: str, model: str = "mcp-client") -> str:
    """Save a finished post: a markdown archive and a plain .txt copy ready to paste on Facebook.
    model: name of the model that wrote the post, recorded in the archive header."""
    from .generate import _write_output

    md_path, txt_path = _write_output(topic, body, get_config(), model)
    return f"archive (.md): {md_path}\ncopy (.txt): {txt_path}"


@mcp.tool()
def generate_post(
    topic: str,
    style: str | None = None,
    length: str | None = None,
    k: int | None = None,
    model: str | None = None,
    language: str | None = None,
) -> str:
    """Generate and save a post on the server via OpenRouter (needs OPENROUTER_API_KEY).
    Prefer prepare_post + save_post when you can write the post yourself.
    language: bn | en; omit to use the configured default."""
    from .generate import generate_post as _generate

    (body, md_path, txt_path, _), _ = _quiet(
        lambda: _generate(
            topic=topic, model=model, k=k, style_name=style, length=length, with_image=False, language=language
        )
    )
    return f"{body}\n\n---\narchive (.md): {md_path}\ncopy (.txt): {txt_path}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
