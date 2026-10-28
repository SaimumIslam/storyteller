"""Bangla text normalization + language detection."""
from __future__ import annotations

import re
import unicodedata

ZWJ = "‍"
ZWNJ = "‌"
BOM = "﻿"

BANGLA_RANGE = (0x0980, 0x09FF)
ARABIC_RANGES = [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)]
LATIN_RANGE = (0x0041, 0x007A)


def _in_range(cp: int, lo: int, hi: int) -> bool:
    return lo <= cp <= hi


def _is_arabic(cp: int) -> bool:
    return any(_in_range(cp, lo, hi) for lo, hi in ARABIC_RANGES)


_QUOTE_MAP = {
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "«": '"', "»": '"',
    "–": "-", "—": "-",
    "…": "...",
}


def _replace_quotes(s: str) -> str:
    for k, v in _QUOTE_MAP.items():
        s = s.replace(k, v)
    return s


def normalize_bangla(text: str) -> str:
    """NFC + Bangla-specific cleanup. Idempotent."""
    if not text:
        return ""
    t = text.replace(BOM, "")
    t = unicodedata.normalize("NFC", t)
    t = _replace_quotes(t)
    t = re.sub(f"[{ZWJ}{ZWNJ}]{{2,}}", ZWJ, t)
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"।{2,}", "।", t)
    t = re.sub(r"[ \t]+([।,.;:!?])", r"\1", t)
    return t.strip()


def char_ratios(text: str) -> dict[str, float]:
    """Return Unicode-block ratios over alphabetic chars only."""
    if not text:
        return {"bn": 0.0, "ar": 0.0, "en": 0.0, "other": 0.0}
    bn = ar = en = other = 0
    for ch in text:
        cp = ord(ch)
        if not ch.isalpha():
            continue
        if _in_range(cp, *BANGLA_RANGE):
            bn += 1
        elif _is_arabic(cp):
            ar += 1
        elif _in_range(cp, *LATIN_RANGE) or _in_range(cp, 0x0061, 0x007A):
            en += 1
        else:
            other += 1
    total = bn + ar + en + other
    if total == 0:
        return {"bn": 0.0, "ar": 0.0, "en": 0.0, "other": 0.0}
    return {
        "bn": bn / total,
        "ar": ar / total,
        "en": en / total,
        "other": other / total,
    }


def dominant_lang(text: str) -> str:
    r = char_ratios(text)
    if r["bn"] == r["ar"] == r["en"] == r["other"] == 0.0:
        return "unknown"
    return max(r, key=r.get)


# ---------- boilerplate page heuristics ----------

_PAGENUM_LINE = re.compile(r"^\s*[^\d\n]{0,80}[\.\s]{2,}\s*[\d০-৯]+\s*$")
_BANGLA_DIGITS = re.compile(r"[০-৯]")
_LATIN_DIGITS = re.compile(r"\d")

# Bangla + English front-matter section headings.
# Match as whole-line / heading style (short, near top of page).
FRONT_MATTER_PATTERNS = [
    r"ভূমিকা",
    r"মুখবন্ধ",
    r"প্রস্তাবনা",
    r"প্রাক[ -]?কথন",
    r"প্রকাশকের\s*কথা",
    r"প্রকাশকীয়",
    r"লেখকের\s*কথা",
    r"অনুবাদকের\s*কথা",
    r"সম্পাদকীয়",
    r"সম্পাদকের\s*কথা",
    r"উৎসর্গ",
    r"কৃতজ্ঞতা",
    r"ধন্যবাদ\s*স্বীকার",
    r"সূচিপত্র",
    r"বিষয়সূচি",
    r"নিবেদন",
    r"আরজ",
    # English / transliterations sometimes found in Bangla books
    r"\bpreface\b",
    r"\bforeword\b",
    r"\bintroduction\b",
    r"\bpublisher'?s?\s+note\b",
    r"\bauthor'?s?\s+note\b",
    r"\btranslator'?s?\s+note\b",
    r"\bdedication\b",
    r"\backnowledge?ments?\b",
    r"\btable\s+of\s+contents\b",
    r"\bcontents\b",
]

BACK_MATTER_PATTERNS = [
    r"পরিশিষ্ট",
    r"গ্রন্থপঞ্জি",
    r"গ্রন্থ\s*সূত্র",
    r"তথ্যসূত্র",
    r"রেফারেন্স",
    r"শব্দকোষ",
    r"পরিভাষা",
    r"নির্ঘণ্ট",
    r"সূচক",
    r"টীকা",
    r"ফুটনোট",
    r"\bappendix\b",
    r"\bbibliography\b",
    r"\bglossary\b",
    r"\bindex\b",
    r"\bnotes\b",
    r"\breferences\b",
]

_FRONT_RE = re.compile("|".join(FRONT_MATTER_PATTERNS), re.IGNORECASE | re.UNICODE)
_BACK_RE = re.compile("|".join(BACK_MATTER_PATTERNS), re.IGNORECASE | re.UNICODE)


def _top_lines(text: str, n: int = 5) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[:n])


def _heading_match(pattern: re.Pattern, text: str) -> str | None:
    """Match only if keyword dominates a short line near the top (i.e. behaves like a heading)."""
    top = _top_lines(text, 5)
    for ln in top.splitlines():
        ln_stripped = ln.strip()
        if not ln_stripped:
            continue
        m = pattern.search(ln_stripped)
        if not m:
            continue
        kw_len = len(m.group(0))
        line_len = len(ln_stripped)
        if line_len <= 20:
            return m.group(0)
        if kw_len / line_len >= 0.50:
            return m.group(0)
    return None


def looks_like_front_matter(text: str) -> str | None:
    return _heading_match(_FRONT_RE, text)


def looks_like_back_matter(text: str) -> str | None:
    return _heading_match(_BACK_RE, text)


def looks_like_cover_page(text: str) -> bool:
    """Heuristic: very few lines, very few words. Title/author only."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) > 8:
        return False
    total_alpha = sum(1 for ch in text if ch.isalpha())
    return total_alpha < 60


def looks_like_index_page(text: str) -> bool:
    """Heuristic: page is TOC/index if many lines end with a page number with dot-leaders."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 5:
        return False
    hits = sum(1 for ln in lines if _PAGENUM_LINE.match(ln))
    return hits / len(lines) >= 0.4


def is_low_content(text: str, min_chars: int = 80) -> bool:
    return len(text.strip()) < min_chars
