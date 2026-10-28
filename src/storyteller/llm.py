"""LLM backend: OpenRouter (via openai SDK)."""
from __future__ import annotations

from .config import get_config

Message = dict[str, str]  # {"role": "system"|"user"|"assistant", "content": "..."}


def generate(messages: list[Message], model: str | None = None, temperature: float | None = None) -> str:
    from openai import OpenAI

    cfg = get_config()
    if not cfg.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set. Add it to .env")

    temp = cfg.temperature if temperature is None else temperature
    _model = model or cfg.default_model

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=cfg.openrouter_api_key,
    )
    res = client.chat.completions.create(
        model=_model,
        messages=messages,
        temperature=temp,
    )
    return (res.choices[0].message.content or "").strip()
