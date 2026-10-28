"""Path resolution and MCP server wiring. No network, no embedding model."""
from __future__ import annotations

import asyncio

import pytest

from storyteller import config


@pytest.fixture(autouse=True)
def _fresh_config(monkeypatch):
    monkeypatch.setattr(config, "_cached", None)
    yield
    monkeypatch.setattr(config, "_cached", None)


def test_home_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_HOME", str(tmp_path))
    assert config.home_dir() == tmp_path.resolve()


def test_home_falls_back_to_user_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("STORYTELLER_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    assert config.home_dir() == (tmp_path / "user" / ".storyteller").resolve()


def test_empty_home_uses_bundled_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_HOME", str(tmp_path))
    cfg = config.get_config()
    assert cfg.home == tmp_path.resolve()
    assert cfg.books_dir == (tmp_path / "books").resolve()
    assert cfg.chroma_path.is_relative_to(tmp_path.resolve())
    assert cfg.rules_file == (config.DEFAULTS_DIR / "rules.yaml").resolve()


def test_home_overrides_win(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_HOME", str(tmp_path))
    (tmp_path / "rules.yaml").write_text("role: x\nrules: []\n", encoding="utf-8")
    (tmp_path / "styles" / "bn").mkdir(parents=True)
    (tmp_path / "styles" / "bn" / "mine.md").write_text("---\nname: mine\n---\nbody\n", encoding="utf-8")
    from storyteller.style import list_styles

    assert config.get_config().rules_file == (tmp_path / "rules.yaml").resolve()
    names = list_styles()
    assert "mine" in names and "emotional" in names


def test_mcp_tools_registered():
    from storyteller.mcp_server import mcp

    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"library_info", "ingest_books", "search_sources", "prepare_post", "save_post", "generate_post"} <= names


def test_save_post_writes_files(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_HOME", str(tmp_path))
    from storyteller.mcp_server import save_post

    out = save_post("পরীক্ষা", "**শিরোনাম**\n\nলেখা।")
    txt = next((tmp_path / "output" / "copy").glob("*.txt"))
    assert str(txt) in out
    assert txt.read_text(encoding="utf-8").startswith("শিরোনাম")


def test_styles_are_per_language(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_HOME", str(tmp_path))
    from storyteller.style import list_styles, load_style

    assert {"emotional", "dramatic", "reflective"} <= set(list_styles("en"))
    assert load_style("emotional", "en").examples[0].startswith("Two hundred thousand miles")
    assert "হৃদয়" in load_style("emotional", "bn").emotion


def test_language_from_config(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        (config.DEFAULTS_DIR / "config.yaml").read_text(encoding="utf-8")
        .replace("language: bn", "language: en")
        .replace("  lang: ben ", "  # lang: ben ")
        .replace("  scripts: [bn] ", "  # scripts: [bn] "),
        encoding="utf-8",
    )
    cfg = config.get_config()
    assert cfg.language == "en"
    assert cfg.rules_file.name == "rules-en.yaml"
    assert cfg.ocr.lang == "eng"
    assert cfg.lang_filter.scripts == ["en"]
    with pytest.raises(ValueError):
        cfg.lang("fr")


def test_english_prompt_and_references(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_HOME", str(tmp_path))
    from storyteller.generate import _append_references
    from storyteller.prompts import build_messages, deterministic_references
    from storyteller.retrieve import RetrievedChunk
    from storyteller.style import load_style

    chunk = RetrievedChunk("text", "Some Book", "some-book.pdf", 12, "ocr", 0.9)
    system, user = (m["content"] for m in build_messages("Badr", [chunk], load_style("reflective", "en"), "en"))
    assert system.startswith("You are a historian")
    assert "--- Writing style ---" in system
    assert "[Source 1: Some Book, page 12]" in user
    refs = deterministic_references([chunk], "en")
    assert refs == "References:\n- Some Book, page 12 (OCR)"
    assert _append_references("Post body.", refs, "en").endswith(refs)
    assert deterministic_references([chunk], "bn").startswith("তথ্যসূত্র:")
