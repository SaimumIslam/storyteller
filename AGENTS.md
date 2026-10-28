# Agent guide

Storyteller is a Python RAG tool: it ingests Bangla and English books (PDF/TXT, with Tesseract OCR fallback) into ChromaDB using `BAAI/bge-m3` embeddings, then writes cited Facebook-style posts in Bangla (`bn`) or English (`en`). It ships a CLI (`storyteller`) and an MCP server (`storyteller-mcp`).

## Setup

```bash
# system deps for OCR (macOS; Linux: apt install tesseract-ocr tesseract-ocr-ben poppler-utils)
brew install tesseract tesseract-lang poppler

uv venv && uv pip install -e ".[dev]"      # or: python -m venv venv && pip install -e ".[dev]"
cp .env.example .env                       # OPENROUTER_API_KEY only needed for `storyteller ask`
```

## Commands

```bash
storyteller info                 # where books / index / output live
storyteller ingest               # index new files in books/
storyteller search -t "বদরের যুদ্ধ" --k 5
storyteller ask -t "বদরের যুদ্ধ" --style emotional --length short
storyteller ask -t "Battle of Badr" --lang en --style reflective
storyteller mcp                  # MCP server on stdio (same as storyteller-mcp)
pytest                           # tests; OpenRouter tests skip without a key
```

## Layout

- `src/storyteller/` is the package. `config.py` resolves paths, `ingest.py` extracts, filters, chunks and embeds, `retrieve.py` queries, `prompts.py` builds the prompt, `generate.py` orchestrates and writes output, `mcp_server.py` exposes MCP tools.
- Language: `config.yaml` `language` (bn | en) picks the prompt template (`TEXT` in `prompts.py`), rules file (`rules_files`), and `styles/<language>/`. Functions take an optional `language` override validated by `Config.lang()`.
- `config.yaml`, `rules*.yaml` and `styles/<language>/*.md` at the repo root are the defaults. They are bundled into the wheel as `storyteller/defaults/`.
- Runtime home: `$STORYTELLER_HOME`, else the current directory if it has `config.yaml`, else `~/.storyteller`. Books, index (`data/`) and `output/` live under home. Running from the repo root uses the repo as home.

## Rules

- Never commit `books/`, `data/`, `output/` or `.env`. Books are usually copyrighted and the index is derived from them.
- The MCP server talks over stdout. Anything that prints during a tool call must go through `_quiet()` in `mcp_server.py`.
- Generated posts must only use retrieved source text; keep that constraint in `rules*.yaml` and in prompts.
