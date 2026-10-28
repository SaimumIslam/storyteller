"""Prompt templates for FB-style storytelling posts, per output language."""
from __future__ import annotations

import yaml

from .config import get_config
from .retrieve import RetrievedChunk
from .style import Style

# Prompt scaffolding per output language. Keys must match config.SUPPORTED_LANGUAGES.
TEXT: dict[str, dict[str, str]] = {
    "bn": {
        "default_role": "ইতিহাসবিদ এবং বাংলা গল্পকার",
        "system": "তুমি একজন {role}।\n\nকঠোর নিয়মাবলী:\n{rules}\n",
        "page": ", পৃষ্ঠা {page}",
        "source_tag": "[উৎস {i}: {title}{page}]",
        "no_sources": "(কোনো প্রাসঙ্গিক উৎস পাওয়া যায়নি)",
        "style_header": "\n--- লেখার স্টাইল ---",
        "emotion": "আবেগ / সুর: {v}",
        "tone": "টোন: {v}",
        "length": "দৈর্ঘ্য: প্রায় {target_words} শব্দ (সর্বনিম্ন {min_words}, সর্বোচ্চ {max_words}), আনুমানিক {paragraphs} অনুচ্ছেদ।",
        "instructions": "\nবিশেষ নির্দেশনা:",
        "examples_header": "\n--- উদাহরণ পোস্ট (এই স্টাইলে লিখতে হবে, তবে নকল করবে না) ---",
        "example_tag": "\n[উদাহরণ {i}]\n{ex}",
        "examples_footer": "\n--- উদাহরণ শেষ ---",
        "user": (
            "বিষয়: {topic}\n\nউৎস:\n{sources}\n\n"
            "উপরের উৎস থেকে একটি ফেসবুক পোস্ট লেখো। নিয়মাবলী ও লেখার স্টাইল মেনে চলবে।\n"
            "যদি উৎসে যথেষ্ট তথ্য না থাকে, তবে শুধু বলো \"প্রদত্ত উৎসে এই বিষয়ে যথেষ্ট তথ্য নেই।\" — গল্প বানাবে না।\n"
        ),
        "references": "তথ্যসূত্র:",
        "not_found": "প্রদত্ত উৎসে এই বিষয়ে কোনো তথ্য পাওয়া যায়নি। অনুগ্রহ করে প্রথমে বইগুলো `{books_dir}` ফোল্ডারে রাখুন এবং `ingest` চালান।",
    },
    "en": {
        "default_role": "historian and storyteller",
        "system": "You are a {role}.\n\nStrict rules:\n{rules}\n",
        "page": ", page {page}",
        "source_tag": "[Source {i}: {title}{page}]",
        "no_sources": "(no relevant sources found)",
        "style_header": "\n--- Writing style ---",
        "emotion": "Emotion / mood: {v}",
        "tone": "Tone: {v}",
        "length": "Length: about {target_words} words (min {min_words}, max {max_words}), roughly {paragraphs} paragraphs.",
        "instructions": "\nSpecific instructions:",
        "examples_header": "\n--- Example posts (match this style, do not copy them) ---",
        "example_tag": "\n[Example {i}]\n{ex}",
        "examples_footer": "\n--- End of examples ---",
        "user": (
            "Topic: {topic}\n\nSources:\n{sources}\n\n"
            "Write a Facebook post in English from the sources above. Follow the rules and the writing style.\n"
            "If the sources don't contain enough information, reply only with "
            "\"The provided sources don't contain enough information on this topic.\" Do not invent a story.\n"
        ),
        "references": "References:",
        "not_found": "No information on this topic was found in the sources. Put your books in `{books_dir}` and run `ingest` first.",
    },
}


def _load_system_prompt(language: str) -> str:
    cfg = get_config()
    t = TEXT[language]
    with open(cfg.rules_for(language), "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    role = data.get("role", t["default_role"])
    rules: list[str] = data.get("rules", [])

    numbered = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, start=1))
    return t["system"].format(role=role, rules=numbered)


def _page(language: str, page: int | None) -> str:
    return TEXT[language]["page"].format(page=page) if page else ""


def _format_sources(chunks: list[RetrievedChunk], language: str) -> str:
    parts: list[str] = []
    for i, c in enumerate(chunks, start=1):
        tag = TEXT[language]["source_tag"].format(i=i, title=c.book_title, page=_page(language, c.page))
        parts.append(f"{tag}\n{c.text}")
    return "\n\n---\n\n".join(parts)


def _style_block(style: Style, language: str) -> str:
    t = TEXT[language]
    lines: list[str] = [t["style_header"]]
    if style.emotion:
        lines.append(t["emotion"].format(v=style.emotion))
    if style.tone:
        lines.append(t["tone"].format(v=style.tone))
    lines.append(t["length"].format(**style.length_spec()))
    if style.instructions:
        lines.append(t["instructions"])
        lines.append(style.instructions)
    return "\n".join(lines)


def _examples_block(style: Style, language: str, max_examples: int = 2) -> str:
    if not style.examples:
        return ""
    t = TEXT[language]
    parts = [t["examples_header"]]
    for i, ex in enumerate(style.examples[:max_examples], start=1):
        parts.append(t["example_tag"].format(i=i, ex=ex))
    parts.append(t["examples_footer"])
    return "\n".join(parts)


def build_messages(
    topic: str,
    chunks: list[RetrievedChunk],
    style: Style | None = None,
    language: str | None = None,
) -> list[dict[str, str]]:
    language = get_config().lang(language)
    sources = _format_sources(chunks, language) if chunks else TEXT[language]["no_sources"]

    system = _load_system_prompt(language)
    if style:
        system += _style_block(style, language)
        system += _examples_block(style, language)

    user = TEXT[language]["user"].format(topic=topic, sources=sources)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def deterministic_references(chunks: list[RetrievedChunk], language: str | None = None) -> str:
    """Build a citation list from chunk metadata, deduplicated by (book, page)."""
    language = get_config().lang(language)
    seen: set[tuple[str, int | None]] = set()
    lines: list[str] = []
    for c in chunks:
        key = (c.book_title, c.page)
        if key in seen:
            continue
        seen.add(key)
        method = " (OCR)" if c.extraction_method == "ocr" else ""
        lines.append(f"- {c.book_title}{_page(language, c.page)}{method}")
    if not lines:
        return ""
    return TEXT[language]["references"] + "\n" + "\n".join(lines)
