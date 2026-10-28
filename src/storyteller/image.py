"""Image generation via OpenAI images API (DALL-E 3 / DALL-E 2)."""
from __future__ import annotations

import base64
import os
from pathlib import Path

import yaml

from .config import get_config
from .llm import generate as llm_generate


def _image_rules() -> dict:
    cfg = get_config()
    with open(cfg.rules_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("image", {})


def _openai_client():
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Add it to .env")
    return OpenAI(api_key=api_key)


def build_image_prompt(topic: str, post_body: str, model: str | None = None) -> str:
    """Use the text LLM to distill an English visual scene from the post."""
    rules = _image_rules()
    system = rules.get(
        "prompt_system",
        "You write short English image-generation prompts. "
        "NO people, NO faces, NO figures. ONE line, max 30 words, comma-separated. No quotes, no preamble.",
    )
    style_suffix = rules.get("style_suffix", "cinematic lighting, high detail, 4k")

    user = f"Topic: {topic}\n\nPost excerpt:\n{post_body[:600]}\n\nVisual prompt:"
    out = llm_generate(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=model,
        temperature=0.4,
    )
    line = out.strip().splitlines()[0] if out.strip() else topic
    return f"{line}, {style_suffix}"


def generate_image(prompt: str, out_path: Path) -> Path:
    cfg = get_config()
    rules = _image_rules()
    client = _openai_client()

    negative_prompt = rules.get(
        "negative_prompt",
        "people, face, figure, cartoon, text, watermark, low quality, blurry",
    )
    full_prompt = f"{prompt}\n\nAvoid: {negative_prompt}"

    response = client.images.generate(
        model=cfg.image.model_id,
        prompt=full_prompt,
        size=cfg.image.size,
        quality=cfg.image.quality,
        n=1,
        response_format="b64_json",
    )

    img_data = base64.b64decode(response.data[0].b64_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(img_data)
    return out_path
