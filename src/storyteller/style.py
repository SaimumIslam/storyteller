"""Style loader: parse styles/<language>/*.md (YAML front matter + body)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import get_config

LENGTH_PRESETS: dict[str, dict[str, int]] = {
    "short":  {"target_words": 180, "min_words": 120, "max_words": 250, "paragraphs": 2},
    "medium": {"target_words": 400, "min_words": 300, "max_words": 550, "paragraphs": 4},
    "long":   {"target_words": 750, "min_words": 600, "max_words": 950, "paragraphs": 6},
}


@dataclass
class Style:
    name: str
    emotion: str = ""
    tone: str = ""
    length: str = "medium"
    target_words: int | None = None
    extra: dict = field(default_factory=dict)
    instructions: str = ""
    examples: list[str] = field(default_factory=list)

    def length_spec(self) -> dict[str, int]:
        preset = LENGTH_PRESETS.get(self.length, LENGTH_PRESETS["medium"]).copy()
        if self.target_words:
            preset["target_words"] = self.target_words
        return preset


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_EXAMPLE_SPLIT_RE = re.compile(r"^##\s+.*$", re.MULTILINE)


def _split_body(body: str) -> tuple[str, list[str]]:
    """Split body into (instructions, examples).
    `# Style Instructions` or text before first `# Example` -> instructions.
    Each `## Example N` block -> one example.
    """
    parts = re.split(r"^#\s+Example[s]?\b.*$", body, maxsplit=1, flags=re.MULTILINE | re.IGNORECASE)
    instructions = parts[0].strip()
    instructions = re.sub(r"^#\s+Style Instructions\s*\n?", "", instructions, flags=re.IGNORECASE).strip()

    examples: list[str] = []
    if len(parts) > 1:
        ex_section = parts[1]
        blocks = _EXAMPLE_SPLIT_RE.split(ex_section)
        for b in blocks:
            b = b.strip()
            if b and len(b) > 30:
                examples.append(b)
    return instructions, examples


def _style_path(name: str, language: str) -> Path | None:
    for d in get_config().styles_dirs(language):
        p = d / f"{name}.md"
        if p.is_file():
            return p
    return None


def load_style(name: str, language: str | None = None) -> Style:
    language = get_config().lang(language)
    path = _style_path(name, language)
    if path is None:
        raise FileNotFoundError(f"Style not found for language {language!r}: {name}. Available: {list_styles(language)}")
    raw = path.read_text(encoding="utf-8")

    fm: dict = {}
    body = raw
    m = _FRONTMATTER_RE.match(raw)
    if m:
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        body = m.group(2)

    instructions, examples = _split_body(body)

    length = str(fm.get("length", "medium")).lower()
    if length not in LENGTH_PRESETS:
        length = "medium"

    return Style(
        name=fm.get("name", name),
        emotion=str(fm.get("emotion", "")),
        tone=str(fm.get("tone", "")),
        length=length,
        target_words=int(fm["target_words"]) if fm.get("target_words") else None,
        extra={k: v for k, v in fm.items() if k not in {"name", "emotion", "tone", "length", "target_words"}},
        instructions=instructions,
        examples=examples,
    )


def list_styles(language: str | None = None) -> list[str]:
    cfg = get_config()
    names: set[str] = set()
    for d in cfg.styles_dirs(cfg.lang(language)):
        if d.is_dir():
            names.update(p.stem for p in d.glob("*.md"))
    return sorted(names)


def default_style(length: str | None = None) -> Style:
    return Style(
        name="default",
        length=(length or "medium"),
    )
