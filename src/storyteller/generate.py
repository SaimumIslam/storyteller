"""RAG orchestration: retrieve -> prompt -> LLM -> write FB post."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .config import get_config
from .llm import generate as llm_generate
from .prompts import TEXT, build_messages, deterministic_references
from .retrieve import retrieve
from .style import Style, default_style, load_style


def _slug(text: str, maxlen: int = 40) -> str:
    s = re.sub(r"\s+", "-", text.strip())
    s = re.sub(r"[^\wঀ-৿-]", "", s, flags=re.UNICODE)
    return s[:maxlen] or "post"


def _append_references(body: str, ref_block: str, language: str) -> str:
    if not ref_block:
        return body
    if TEXT[language]["references"].rstrip(":") in body:
        return body
    return body.rstrip() + "\n\n" + ref_block


def _strip_markdown(text: str) -> str:
    """Strip common markdown artifacts so the .txt copy pastes cleanly to FB."""
    out = text
    out = re.sub(r"^#{1,6}\s+", "", out, flags=re.MULTILINE)
    out = re.sub(r"\*\*(.+?)\*\*", r"\1", out)
    out = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", out)
    out = re.sub(r"__(.+?)__", r"\1", out)
    out = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"\1", out)
    out = re.sub(r"`([^`]+)`", r"\1", out)
    out = re.sub(r"^\s*[-*+]\s+", "• ", out, flags=re.MULTILINE)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def generate_post(
    topic: str,
    model: str | None = None,
    k: int | None = None,
    style_name: str | None = None,
    length: str | None = None,
    with_image: bool | None = None,
    language: str | None = None,
) -> tuple[str, Path, Path, Path | None]:
    cfg = get_config()
    model = model or cfg.default_model
    language = cfg.lang(language)

    if style_name:
        style: Style = load_style(style_name, language)
        if length:
            style.length = length
    else:
        style = default_style(length=length)

    chunks = retrieve(topic, k=k)
    if not chunks:
        body = TEXT[language]["not_found"].format(books_dir=cfg.books_dir)
        md_path, txt_path = _write_output(topic, body, cfg, model)
        return body, md_path, txt_path, None

    messages = build_messages(topic, chunks, style=style, language=language)
    raw = llm_generate(messages, model=model, temperature=cfg.temperature)

    refs = deterministic_references(chunks, language)
    final = _append_references(raw, refs, language)

    md_path, txt_path = _write_output(topic, final, cfg, model)

    img_path: Path | None = None
    do_image = cfg.image.enabled if with_image is None else with_image
    if do_image:
        img_path = _generate_image_for_post(topic, final, cfg, model, md_path.stem)

    return final, md_path, txt_path, img_path


def _generate_image_for_post(topic: str, body: str, cfg, model: str, stem: str) -> Path | None:
    try:
        from .image import build_image_prompt, generate_image

        prompt_model = cfg.image.prompt_model or model
        prompt = build_image_prompt(topic, body, model=prompt_model)
        out_path = cfg.image.output_dir / f"{stem}.png"
        return generate_image(prompt, out_path)
    except Exception as e:
        import sys
        print(f"[image] skipped: {e}", file=sys.stderr)
        return None


def _write_output(topic: str, body: str, cfg, model: str) -> tuple[Path, Path]:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    cfg.copy_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _slug(topic)

    md_path = cfg.output_dir / f"{ts}_{slug}.md"
    md_header = (
        f"<!-- topic: {topic} | model: {model} | generated: {ts} -->\n\n"
    )
    md_path.write_text(md_header + body, encoding="utf-8")

    txt_path = cfg.copy_dir / f"{ts}_{slug}.txt"
    clean = _strip_markdown(body)
    txt_path.write_text(clean + "\n", encoding="utf-8")

    return md_path, txt_path
