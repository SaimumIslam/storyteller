"""Config loader. YAML defaults + .env secrets.

Paths resolve against a "home" directory holding the user's books, index and
output. Home is picked in this order:
  1. $STORYTELLER_HOME
  2. the current directory, if it has a config.yaml (e.g. a cloned repo)
  3. ~/.storyteller

Any of config.yaml / rules*.yaml / styles/*.md missing from home falls back to
the bundled defaults shipped with the package.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

SUPPORTED_LANGUAGES = ("bn", "en")
# Tesseract language packs per output language
_OCR_LANGS = {"bn": "ben", "en": "eng"}
_DEFAULT_RULES = {"bn": "./rules.yaml", "en": "./rules-en.yaml"}

_PKG_DIR = Path(__file__).resolve().parent
# Wheel installs ship defaults inside the package; a source checkout keeps them at repo root.
DEFAULTS_DIR = _PKG_DIR / "defaults" if (_PKG_DIR / "defaults").is_dir() else _PKG_DIR.parent.parent


def home_dir() -> Path:
    env = os.getenv("STORYTELLER_HOME")
    if env:
        return Path(env).expanduser().resolve()
    cwd = Path.cwd()
    if (cwd / "config.yaml").is_file():
        return cwd.resolve()
    return (Path.home() / ".storyteller").resolve()


def resolve_resource(rel: str | Path, home: Path | None = None) -> Path:
    """Return home/rel if it exists, else the bundled default."""
    home = home or home_dir()
    p = (home / rel).resolve()
    if p.exists():
        return p
    return (DEFAULTS_DIR / rel).resolve()


@dataclass
class OCRConfig:
    enabled: bool = True
    lang: str = "ben"                # tesseract pack(s), e.g. ben | eng | ben+eng
    dpi: int = 300
    min_chars_per_page: int = 50
    force_ocr_files: list[str] = field(default_factory=list)


@dataclass
class LangFilterConfig:
    enabled: bool = True
    scripts: list[str] = field(default_factory=lambda: ["bn"])  # keys of textnorm.char_ratios: bn | en | ar
    min_ratio: float = 0.30          # keep chunk if combined ratio of `scripts` >= this


@dataclass
class BoilerplateConfig:
    drop_index_pages: bool = True
    drop_cover_page: bool = True
    drop_front_matter: bool = True
    drop_back_matter: bool = True
    front_zone_ratio: float = 0.20    # only scan first 20% of book for front-matter headings
    back_zone_ratio: float = 0.15     # only scan last 15% of book for back-matter headings
    min_page_chars: int = 80


@dataclass
class BookOverride:
    front_skip_pages: int = 0
    back_skip_pages: int = 0
    skip_pages: list[int] = field(default_factory=list)


@dataclass
class ImageConfig:
    enabled: bool = False
    model_id: str = "dall-e-3"
    prompt_model: str | None = None  # OpenRouter model for writing the image prompt; None = use default_model
    size: str = "1024x1024"
    quality: str = "standard"        # standard | hd (dall-e-3 only)
    output_dir: Path = field(default_factory=lambda: Path("./output/images"))


@dataclass
class Config:
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    retrieval_k: int
    default_model: str
    temperature: float
    language: str
    rules_files: dict[str, Path]
    chroma_path: Path
    collection: str
    books_dir: Path
    output_dir: Path
    copy_dir: Path
    state_file: Path
    ocr: OCRConfig
    lang_filter: LangFilterConfig
    boilerplate: BoilerplateConfig
    book_overrides: dict[str, BookOverride]
    image: ImageConfig
    openrouter_api_key: str | None
    home: Path
    styles_root: list[Path]

    @property
    def rules_file(self) -> Path:
        return self.rules_for(self.language)

    def lang(self, language: str | None) -> str:
        """Validate a per-call language override, falling back to the configured one."""
        language = (language or self.language).lower()
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}. Choose one of: {', '.join(SUPPORTED_LANGUAGES)}")
        return language

    def rules_for(self, language: str) -> Path:
        return self.rules_files.get(language) or resolve_resource(_DEFAULT_RULES[language], self.home)

    def styles_dirs(self, language: str) -> list[Path]:
        return [d / language for d in self.styles_root]

    @classmethod
    def load(cls) -> "Config":
        root = home_dir()
        load_dotenv(root / ".env")
        with open(resolve_resource("config.yaml", root), "r", encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f)

        language = str(raw.get("language", "bn")).lower()
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"config.yaml: language must be one of {SUPPORTED_LANGUAGES}, got {language!r}")

        rules_raw = raw.get("rules_files") or {}
        if raw.get("rules_file"):  # legacy single-file setting applies to the configured language
            rules_raw = {**rules_raw, language: raw["rules_file"]}
        rules_files = {lang: resolve_resource(path, root) for lang, path in rules_raw.items()}

        ocr_raw = raw.get("ocr", {}) or {}
        ocr = OCRConfig(
            enabled=bool(ocr_raw.get("enabled", True)),
            lang=str(ocr_raw.get("lang") or _OCR_LANGS[language]),
            dpi=int(ocr_raw.get("dpi", 300)),
            min_chars_per_page=int(ocr_raw.get("min_chars_per_page", 50)),
            force_ocr_files=list(ocr_raw.get("force_ocr_files", []) or []),
        )

        lf_raw = raw.get("lang_filter", {}) or {}
        lang_filter = LangFilterConfig(
            enabled=bool(lf_raw.get("enabled", True)),
            scripts=list(lf_raw.get("scripts") or [language]),
            min_ratio=float(lf_raw.get("min_ratio", lf_raw.get("min_bn_ratio", 0.30))),
        )

        bp_raw = raw.get("boilerplate", {}) or {}
        boilerplate = BoilerplateConfig(
            drop_index_pages=bool(bp_raw.get("drop_index_pages", True)),
            drop_cover_page=bool(bp_raw.get("drop_cover_page", True)),
            drop_front_matter=bool(bp_raw.get("drop_front_matter", True)),
            drop_back_matter=bool(bp_raw.get("drop_back_matter", True)),
            front_zone_ratio=float(bp_raw.get("front_zone_ratio", 0.20)),
            back_zone_ratio=float(bp_raw.get("back_zone_ratio", 0.15)),
            min_page_chars=int(bp_raw.get("min_page_chars", 80)),
        )

        img_raw = raw.get("image", {}) or {}
        image = ImageConfig(
            enabled=bool(img_raw.get("enabled", False)),
            model_id=str(img_raw.get("model_id", "dall-e-3")),
            prompt_model=img_raw.get("prompt_model") or None,
            size=str(img_raw.get("size", "1024x1024")),
            quality=str(img_raw.get("quality", "standard")),
            output_dir=(root / img_raw.get("output_dir", "./output/images")).resolve(),
        )

        overrides_raw = raw.get("book_overrides", {}) or {}
        book_overrides: dict[str, BookOverride] = {}
        for fname, ov in overrides_raw.items():
            ov = ov or {}
            book_overrides[fname] = BookOverride(
                front_skip_pages=int(ov.get("front_skip_pages", 0)),
                back_skip_pages=int(ov.get("back_skip_pages", 0)),
                skip_pages=list(ov.get("skip_pages", []) or []),
            )

        return cls(
            embedding_model=raw["embedding_model"],
            chunk_size=int(raw["chunk_size"]),
            chunk_overlap=int(raw["chunk_overlap"]),
            retrieval_k=int(raw["retrieval_k"]),
            default_model=raw["default_model"],
            temperature=float(raw["temperature"]),
            language=language,
            rules_files=rules_files,
            chroma_path=(root / raw["chroma_path"]).resolve(),
            collection=raw["collection"],
            books_dir=(root / raw["books_dir"]).resolve(),
            output_dir=(root / raw["output_dir"]).resolve(),
            copy_dir=(root / raw.get("copy_dir", "./output/copy")).resolve(),
            state_file=(root / raw["state_file"]).resolve(),
            ocr=ocr,
            lang_filter=lang_filter,
            boilerplate=boilerplate,
            book_overrides=book_overrides,
            image=image,
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
            home=root,
            styles_root=[root / "styles", DEFAULTS_DIR / "styles"],
        )


_cached: Config | None = None


def get_config() -> Config:
    global _cached
    if _cached is None:
        _cached = Config.load()
    return _cached
