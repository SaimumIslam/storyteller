"""Integration test: OpenRouter API round-trip."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def _api_key() -> str | None:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    return os.getenv("OPENROUTER_API_KEY")


@pytest.mark.skipif(not _api_key(), reason="OPENROUTER_API_KEY not set")
def test_openrouter_text_generation() -> None:
    """Single short call to OpenRouter; verifies key, network, and response shape."""
    from storyteller.llm import generate

    messages = [
        {"role": "user", "content": "Reply with exactly: ok"},
    ]
    result = generate(messages, model="google/gemma-3-27b-it:free", temperature=0.0)

    assert isinstance(result, str), "Response must be a string"
    assert len(result) > 0, "Response must not be empty"


@pytest.mark.skipif(not _api_key(), reason="OPENROUTER_API_KEY not set")
def test_openrouter_uses_default_model() -> None:
    """Calling generate() without model uses config default_model."""
    from storyteller.config import get_config
    from storyteller.llm import generate

    cfg = get_config()
    assert cfg.default_model, "default_model must be set in config.yaml"

    result = generate([{"role": "user", "content": "Say: hello"}], temperature=0.0)
    assert isinstance(result, str) and len(result) > 0


def test_config_no_ollama_fields() -> None:
    """Config must not expose old ollama/backend fields."""
    from storyteller.config import Config
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(Config)}
    assert "default_backend" not in field_names
    assert "default_model_ollama" not in field_names
    assert "default_model_openrouter" not in field_names
    assert "default_model" in field_names


def test_llm_module_no_ollama() -> None:
    """llm module must not expose backend parameter or ollama function."""
    import inspect
    from storyteller import llm

    sig = inspect.signature(llm.generate)
    assert "backend" not in sig.parameters, "generate() must not have 'backend' param"
    assert not hasattr(llm, "_ollama"), "llm module must not have _ollama"
