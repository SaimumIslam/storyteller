# Storyteller — Bangla & English FB Post Generator

RAG-based CLI and MCP server. Drop any PDFs/text files into `books/`, ingest them, then generate Bangla or English Facebook-style posts on any topic — with proper citations, language filtering, boilerplate removal, and customizable writing style.

Works for any domain: Islamic history, war & battles, science, biography, politics, literature — whatever books you put in.

---

## Features

- **RAG** — retrieves from your own books, never fabricates.
- **Bangla and English** — write posts in either language, from books in either language (one `language` setting, or `--lang` per run). See [Languages](#languages).
- **Bangla-aware text cleanup** — Unicode-normalized, ZWJ/quote cleanup, danda standardization.
- **OCR fallback** — Tesseract (Bangla, English, or both) auto-triggers on image-based PDF pages.
- **Smart filtering** — auto-skips cover page, preface, publisher's note, dedication, TOC, bibliography, glossary, index. Drops chunks in scripts you don't want (e.g. Arabic quotes inside Bangla books).
- **Style system** — pick tone (emotional / dramatic / reflective) and length (short / medium / long) via `styles/<language>/*.md` files with few-shot examples.
- **Any domain** — works with any books: history, war, science, biography, literature, etc.
- **OpenRouter** — any model on OpenRouter (Gemma, DeepSeek, Llama, Claude, GPT, etc.) via one API key.
- **FB-pasteable output** — clean `.txt` copy stripped of markdown, alongside archival `.md`.
- **Optional image** — OpenAI image generation (DALL-E 3), off by default; enable per-run with `--image`.
- **MCP server + Claude Code plugin** — use it from Claude Code, Claude Desktop, Cursor or any MCP client; your assistant writes the post, no extra API key.

---

## Use it from your AI assistant (MCP)

Storyteller ships an [MCP](https://modelcontextprotocol.io) server, so Claude Code, Claude Desktop, Cursor, VS Code and other MCP clients can search your books and write posts directly. When your assistant writes the post itself (`prepare_post` → `save_post`), **no OpenRouter key is needed**.

Prerequisites: [uv](https://docs.astral.sh/uv/getting-started/installation/), plus Tesseract and Poppler if you have scanned PDFs (see [System dependencies](#1-system-dependencies)).

### Claude Code (plugin, recommended)

```
/plugin marketplace add SaimumIslam/storyteller
/plugin install storyteller@storyteller
```

This installs the MCP server and a `storyteller` skill that teaches Claude the workflow. Then ask: *"বদরের যুদ্ধ নিয়ে একটি আবেগময় ছোট পোস্ট লেখো"*.

Or add only the MCP server:

```bash
claude mcp add storyteller -- uvx --python 3.12 --from git+https://github.com/SaimumIslam/storyteller storyteller-mcp
```

### Claude Desktop, Cursor, VS Code and other clients

Add this to the client's MCP config (`claude_desktop_config.json`, `.cursor/mcp.json`, and so on):

```json
{
  "mcpServers": {
    "storyteller": {
      "command": "uvx",
      "args": ["--python", "3.12", "--from", "git+https://github.com/SaimumIslam/storyteller", "storyteller-mcp"],
      "env": { "STORYTELLER_HOME": "/absolute/path/to/your/library" }
    }
  }
}
```

`env` is optional. Without it, your library lives in `~/.storyteller`.

### MCP tools

| Tool | What it does |
|---|---|
| `library_info` | Books folder location, ingested books, styles |
| `ingest_books` | Index new files in the books folder |
| `search_sources` | Top-k passages for a topic, with book and page |
| `prepare_post` | Writing brief: rules, style, examples, sources, reference list. The assistant writes the post |
| `save_post` | Save a finished post as `.md` + Facebook-ready `.txt` |
| `generate_post` | Server-side generation via OpenRouter (needs `OPENROUTER_API_KEY`) |

### Adding books

```bash
uvx --python 3.12 --from git+https://github.com/SaimumIslam/storyteller storyteller init    # creates ~/.storyteller
cp ~/my-books/*.pdf ~/.storyteller/books/
uvx --python 3.12 --from git+https://github.com/SaimumIslam/storyteller storyteller ingest
```

Ingest in a terminal for big libraries: the first run downloads the `bge-m3` embedding model (~2 GB), and OCR of scanned PDFs is slow. Asking your assistant to call `ingest_books` works too.

---

## Where your data lives

Storyteller picks a **home** folder in this order:

1. `$STORYTELLER_HOME`
2. the current directory, if it contains `config.yaml` (for example a cloned repo)
3. `~/.storyteller`

Home holds `books/`, the index (`data/`), `output/`, `.env`, and optional overrides of `config.yaml`, `rules*.yaml` and `styles/<language>/`. Anything missing falls back to the bundled defaults. `storyteller init` copies the defaults into home so you can edit them, and `storyteller info` prints every path.

---

## Setup (CLI / development)

### 1. System dependencies

```bash
brew install tesseract tesseract-lang poppler                          # macOS
sudo apt install tesseract-ocr tesseract-ocr-ben poppler-utils          # Debian / Ubuntu
```

`tesseract-lang` brings the Bangla pack (`ben`). `poppler` lets `pdf2image` rasterize PDF pages for OCR. Verify with `tesseract --list-langs | grep ben`. English (`eng`) ships with Tesseract. Only needed for scanned (image-based) PDFs.

### 2. Install

Without cloning:

```bash
uv tool install --python 3.12 git+https://github.com/SaimumIslam/storyteller
storyteller init
```

From a clone:

```bash
git clone https://github.com/SaimumIslam/storyteller && cd storyteller
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

Either way you get two commands: `storyteller` (CLI) and `storyteller-mcp` (MCP server). Inside a clone, the repo itself is the home, and the included `.mcp.json` registers the server for Claude Code.

### 3. API key (only for `storyteller ask` / `generate_post`)

```bash
cp .env.example .env      # in your home folder
```

```
OPENROUTER_API_KEY=sk-or-v1-...
```

Get a free key at [openrouter.ai](https://openrouter.ai).

### 4. Config

Defaults live in `config.yaml`. The default model is `deepseek/deepseek-v4-flash:free`. Change it to any OpenRouter model:

```yaml
default_model: deepseek/deepseek-v4-flash:free
```

### Docker

The image bundles Tesseract (Bangla + English) and Poppler:

```bash
docker build -t storyteller .
docker run --rm -v ~/.storyteller:/library storyteller ingest
docker run --rm -v ~/.storyteller:/library storyteller ask -t "বদরের যুদ্ধ"
```

---

## Quick start

```bash
# 1. Drop any PDFs / .txt files into the books folder (see `storyteller info`)
cp ~/war-of-1971.pdf books/

# 2. Ingest (re-run anytime; only new files get processed)
storyteller ingest

# 3. Generate a post on any topic
storyteller ask --topic "বদরের যুদ্ধ"
storyteller ask --topic "মুক্তিযুদ্ধের শুরু"
```

Output:
- `output/posts/*.md`: archive with metadata header
- `output/copy/*.txt`: clean text, **paste this to Facebook**

---

## Languages

Posts can be written in **Bangla (`bn`)** or **English (`en`)**. The books can be in either language too: the `bge-m3` embedding model is multilingual, so an English topic finds Bangla passages and vice versa, and the model translates faithfully from the sources.

### Switch the default to English

In `config.yaml` (in your home folder; run `storyteller init` first if you installed the package):

```yaml
language: en
```

That one setting changes:

| What | `bn` | `en` |
|---|---|---|
| Prompt template and citation format | Bangla (`তথ্যসূত্র:` / `পৃষ্ঠা`) | English (`References:` / `page`) |
| Rules file | `rules.yaml` | `rules-en.yaml` |
| Styles folder | `styles/bn/` | `styles/en/` |
| OCR pack (if `ocr.lang` is not set) | `ben` | `eng` |
| Ingest language filter (if `lang_filter.scripts` is not set) | keep Bangla chunks | keep English chunks |

The shipped `config.yaml` sets `ocr.lang: ben` and `lang_filter.scripts: [bn]` explicitly. If your books are English, change those lines too (or delete them so they follow `language`):

```yaml
ocr:
  lang: eng
lang_filter:
  scripts: [en]
```

### Mixed library or per-post language

Keep `language: bn` as the default and pick English per post:

```bash
storyteller ask --topic "Battle of Badr" --lang en --style reflective
storyteller styles --lang en
```

In MCP clients, `prepare_post` and `generate_post` take a `language` argument, so you can just ask your assistant for "an English post about ...".

For a library with both Bangla and English books, keep both scripts when ingesting and OCR with both packs:

```yaml
ocr:
  lang: ben+eng
lang_filter:
  scripts: [bn, en]
```

Language filter settings apply at ingest time. After changing them, re-ingest (delete `data/` in your home folder, then run `storyteller ingest`).

### Other languages

Only `bn` and `en` have built-in prompt templates. To add another one, add an entry to `TEXT` in `src/storyteller/prompts.py` and to `SUPPORTED_LANGUAGES` in `src/storyteller/config.py`, then create `rules-<code>.yaml` and `styles/<code>/`. PRs welcome.

---

## CLI commands

| Command | Purpose |
|---|---|
| `init` | Create the home folder with editable config, rules and styles |
| `info` | Show home, books, index and output paths |
| `ingest` | Process new books in the books folder |
| `ask --topic "..."` | Generate a FB post |
| `search --topic "..." --k 5` | Debug: show top-k retrieved chunks |
| `books` | List ingested books |
| `styles` | List available styles |
| `mcp` | Run the MCP server on stdio |

### `ask` flags

```bash
storyteller ask \
  --topic "হিজরত" \          # required
  --model deepseek/deepseek-v4-flash:free \  # override OpenRouter model
  --style emotional \        # styles/<language>/emotional.md
  --lang en \                # bn | en (default: config.yaml `language`)
  --length short \           # short | medium | long
  --k 6 \                    # retrieval count
  --image                    # generate image (off by default)
```

All flags except `--topic` are optional; defaults come from `config.yaml`.

---

## Image generation (optional)

Image generation uses the OpenAI Images API (`dall-e-3` by default). It is **off by default** and needs `OPENAI_API_KEY` in `.env`. The OpenRouter model first writes an English scene prompt from the post, then the image model renders it.

```bash
storyteller ask --topic "বদর যুদ্ধ" --image
```

Image output: `output/images/*.png`. To enable by default, set `image.enabled: true` in `config.yaml`. Image prompt rules (`prompt_system`, `style_suffix`, `negative_prompt`) can go under `image:` in your rules file.

---

## Ingestion pipeline

Each PDF/TXT goes through:

1. **SHA256 dedupe** — skip if already ingested.
2. **Text extraction** — `pdfplumber` first; auto-fallback to **Tesseract Bangla OCR** for image-based pages (preprocess: grayscale → autocontrast → threshold → median filter).
3. **Bangla normalization** — Unicode NFC, strip BOM, collapse ZWJ/ZWNJ, normalize quotes and danda `।`, whitespace cleanup.
4. **Boilerplate filter** (positional, configurable):
   - Cover page (first 1–3 pages, sparse text)
   - Front matter: ভূমিকা / মুখবন্ধ / প্রস্তাবনা / প্রকাশকের কথা / লেখকের কথা / উৎসর্গ / সূচিপত্র + English equivalents
   - Back matter: গ্রন্থপঞ্জি / তথ্যসূত্র / শব্দকোষ / পরিভাষা / নির্ঘণ্ট / পরিশিষ্ট + English equivalents
   - TOC pages (dot-leader heuristic)
   - Pages below `min_page_chars` (blank / page-number only)
5. **Chunk** — `RecursiveCharacterTextSplitter` (Bangla-aware separators including `।`).
6. **Language filter** — Unicode-block ratio per chunk. Drop chunks where the scripts in `lang_filter.scripts` make up less than `min_ratio` (default 0.30).
7. **Embed** — `BAAI/bge-m3` (multilingual, 1024-dim, normalized).
8. **Store** — ChromaDB persistent collection with metadata `{book_title, source_file, page, chunk_idx, extraction_method, lang, bn_ratio, file_hash}`.

---

## Per-book overrides

For known weird layouts, override in `config.yaml`:

```yaml
book_overrides:
  seerah-ibn-kathir.pdf:
    front_skip_pages: 12         # hard-skip first N pages
    back_skip_pages: 20          # hard-skip last N pages
    skip_pages: [145, 146, 250]  # drop specific page numbers
```

To re-ingest after changing overrides: delete the file's hash from `data/ingest_state.json` in your home folder, then re-run `ingest`.

To force OCR on a known image-only PDF:

```yaml
ocr:
  force_ocr_files:
    - scanned-book.pdf
```

---

## Rules system (`rules.yaml`, `rules-en.yaml`)

Prompt rules live in YAML files, one per language: `rules.yaml` (Bangla) and `rules-en.yaml` (English). Plain YAML, no Python required.

```yaml
role: "ইতিহাসবিদ এবং বাংলা গল্পকার"

rules:
  - "শুধুমাত্র উৎসের তথ্য ব্যবহার করবে। উৎসে নেই এমন কিছু বানাবে না।"
  - "উৎসে তথ্য না থাকলে স্পষ্টভাবে বলবে — অনুমান করে গল্প বানাবে না।"
  - "ফেসবুক পোস্ট আকারে লিখবে: হুক → গল্প → শিক্ষা → তথ্যসূত্র।"
  - "মানবিক, সাবলীল বাংলায় লিখবে।"
  # add or remove rules freely
```

English rules look the same:

```yaml
role: "historian and storyteller who writes for Facebook"

rules:
  - "Use only facts from the \"Sources\" section below. Never invent names, dates, numbers, quotes, or events."
  - "If the sources are in another language, translate faithfully. Don't embellish while translating."
```

To use a different rule file for a language (e.g. for a different domain), update `rules_files` in `config.yaml`:

```yaml
rules_files:
  bn: ./rules-islamic.yaml
  en: ./rules-en.yaml
```

Each domain can have its own rules file — swap without touching code.

---

## Style system

Each style is a markdown file in `styles/<language>/` (`styles/bn/`, `styles/en/`). The same style name can exist in both languages, and `--style emotional` picks the one matching the post language. YAML front matter sets emotion / tone / length. Body has writing instructions + 1–2 full example FB posts. The generator injects them as few-shot examples.

**Built-in styles** (available in both `bn` and `en`):
| Style | Emotion (bn) | Emotion (en) | Length |
|---|---|---|---|
| `emotional` | হৃদয়স্পর্শী, আবেগপূর্ণ | moving, heartfelt | medium (~450 w) |
| `dramatic` | রোমাঞ্চকর, টানটান (cinematic) | gripping, tense | long (~800 w) |
| `reflective` | চিন্তাশীল, প্রশ্নবোধক | thoughtful, questioning | short (~200 w) |

**Length presets:**
| Length | Target | Range | Paragraphs |
|---|---|---|---|
| short | 180 w | 120–250 | 2 |
| medium | 400 w | 300–550 | 4 |
| long | 750 w | 600–950 | 6 |

`--length` overrides the style's default.

**Create your own style:**

```markdown
---
name: my-style
emotion: শান্ত ও দার্শনিক
tone: প্রজ্ঞাময় বৃদ্ধের কণ্ঠস্বরের মতো
length: medium
target_words: 350
---

# Style Instructions

- ছোট ছোট বাক্য।
- উপমা ব্যবহার করো।
- শেষে একটি প্রশ্ন রেখে যাও।

# Examples

## উদাহরণ ১
<paste a full FB post here>
```

Save as `styles/bn/my-style.md`. Use with `--style my-style`.

An English style uses the same format, saved in `styles/en/`:

```markdown
---
name: my-style
emotion: calm, philosophical
tone: like a wise elder speaking slowly
length: medium
target_words: 350
---

# Style Instructions

- Short sentences.
- Use one vivid comparison.
- End with a question.

# Examples

## Example 1
<paste a full FB post here>
```

---

## Post structure

Every generated post follows:

1. **Hook** — short attention-grabbing opener
2. **Story** — chronological narration strictly from retrieved sources
3. **Reflection** — moral / takeaway
4. **References** — deterministic list built from chunk metadata (book + page)

If chunks came from OCR, references get an `(OCR)` tag.

---

## Output files

| Path | Format | Use |
|---|---|---|
| `output/posts/YYYYMMDD-HHMMSS_<slug>.md` | Markdown with metadata header | Archive |
| `output/copy/YYYYMMDD-HHMMSS_<slug>.txt` | Plain UTF-8, markdown stripped | **Paste to Facebook** |
| `output/images/YYYYMMDD-HHMMSS_<slug>.png` | PNG | Upload with post (if `--image`) |

---

## Config reference (`config.yaml`)

```yaml
default_model: deepseek/deepseek-v4-flash:free   # any OpenRouter model ID
retrieval_k: 6                    # chunks pulled per query
temperature: 0.7                  # raise for more variation

image:
  enabled: false                  # true = generate image by default
  model_id: dall-e-3

ocr:
  enabled: true
  lang: ben                       # ben | eng | ben+eng
  min_chars_per_page: 50

lang_filter:
  enabled: true
  scripts: [bn]                   # bn | en | ar; [bn, en] for a mixed library
  min_ratio: 0.30                 # drop chunk if those scripts make up less than this

boilerplate:
  drop_cover_page: true
  drop_front_matter: true
  drop_back_matter: true
  drop_index_pages: true
  front_zone_ratio: 0.20
  back_zone_ratio: 0.15
  min_page_chars: 80
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `OPENROUTER_API_KEY not set` | Add key to `.env` |
| `No endpoints found for <model>` | Model ID wrong or unavailable — check [openrouter.ai/models](https://openrouter.ai/models) |
| Rate limited (429) | Free model quota hit — wait or switch to another free model with `--model` |
| Empty output / "তথ্য নেই" | Run `search --topic "..."` to verify retrieval. Topic may not be in books. |
| Bangla glyphs show as boxes | Editor font issue — switch to SolaimanLipi, Kalpurush, or Noto Bangla |
| OCR garbled | Low scan quality or wrong language — raise `ocr.dpi` to 400; verify `ben` pack installed |
| Real content dropped as front matter | Set `drop_front_matter: false` or shrink `front_zone_ratio` to `0.10` |
| Real content dropped by lang filter | Lower `lang_filter.min_ratio` to `0.15`, or add the book's script to `lang_filter.scripts` |
| English books produce no chunks | Set `lang_filter.scripts: [en]` (or `[bn, en]`) and `ocr.lang: eng`, then re-ingest |
| Re-ingest after settings change | Delete file's hash from `data/ingest_state.json`, run `ingest` again |

---

## Architecture

```
books/*.pdf,*.txt
       │
       ▼
  ingest.py
   ├─ pdfplumber + OCR fallback
   ├─ normalize_bangla()
   ├─ skip cover / front / back / index
   ├─ chunk (RecursiveCharacterTextSplitter)
   ├─ lang filter (kept scripts ≥ 0.30)
   └─ embed (bge-m3) → ChromaDB

ask --topic
       │
       ▼
  retrieve.py  (top-k chunks)
       │
       ▼
  prompts.py (bn | en) + style (+ examples)
       │
       ▼
  llm.py → OpenRouter API
       │
       ▼
  generate.py  → append deterministic refs
       │
       ├─→ output/posts/*.md
       ├─→ output/copy/*.txt    ← paste to Facebook
       └─→ output/images/*.png  ← only with --image
```

---

## Domain notes

The system is domain-agnostic — the LLM reads only what you retrieve from your books, so output quality depends entirely on your book collection. Tips:

- **Islamic history** — drop Seerah, Hadith compilations, Islamic history books in Bangla/English
- **War history** — drop battle accounts, military history, liberation war books
- **Biography** — drop biographies; works best when the person has dedicated chapters
- **Mixed library** — all books coexist in one ChromaDB collection; retrieval is semantic, so only relevant chunks are pulled regardless of domain

If the retrieved chunks are thin on a topic, use `search --topic "..."` to debug what's being retrieved.

---

## Out of scope (for now)

- Multi-post series / continuity memory across posts
- Web UI
- Fine-tuning
- Built-in prompt templates for languages other than Bangla and English

---

## Contributing

Issues and PRs welcome. See [AGENTS.md](AGENTS.md) for layout and dev commands; run `pytest` before sending a PR. Please don't commit books or anything under `data/` or `output/`.

## License

[MIT](LICENSE). The license covers the code only. You are responsible for having the rights to the books you ingest.
