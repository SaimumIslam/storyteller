---
name: storyteller
description: Write Bangla or English Facebook-style posts grounded in the user's own book library, with citations. Use when the user asks for a post, story, or article on a historical or religious topic from their books, wants to add books to the library, or asks what the library covers.
---

# Storyteller

The `storyteller` MCP server searches the user's ingested books (Bangla or English PDFs and text files) and returns passages with book titles and page numbers. Posts must be built only from those passages.

## Writing a post

1. Call `library_info` to see the ingested books and available styles. If no books are ingested, tell the user where the books folder is and offer to run ingestion.
2. Call `prepare_post` with the topic and, if the user gave them, `style` and `length` (`short`, `medium`, `long`). Set `language` to `en` when the user wants English (or writes the request in English and doesn't ask for Bangla), `bn` for Bangla; omit it to use the library default. Books in either language work for either output language. It returns a writing brief: rules, style guidance, example posts, source passages and a reference block.
3. Write the post yourself in the brief's language, following the brief:
   - Use only facts present in the sources. Don't add anything from your own knowledge, even if you are confident it's true.
   - If the sources don't cover the topic, say so instead of writing a post.
   - Don't copy the example posts; match their voice.
   - End with the exact reference block from the brief.
   - Plain text, no markdown headings. The post goes straight onto Facebook.
4. Call `save_post` with the topic, the post body and your model name. Show the user the post and the path of the `.txt` copy.

Use `generate_post` only when the user explicitly asks for a specific OpenRouter model. It needs `OPENROUTER_API_KEY`.

## Adding books

- Books go in the books folder shown by `library_info` (by default `~/.storyteller/books`).
- `ingest_books` processes new files. The first run downloads a ~2 GB embedding model, and scanned PDFs are OCR'd page by page, which can take a long time. If you have a shell, prefer running `uvx --from git+https://github.com/SaimumIslam/storyteller storyteller ingest` (or `storyteller ingest` if installed) so the progress is visible and nothing times out.
- English-only books need `language`/`lang_filter.scripts` set for English in the home `config.yaml`, otherwise ingestion drops their text (see the README's Languages section).
- OCR for scanned PDFs needs Tesseract with the Bangla pack and Poppler installed on the system (`brew install tesseract tesseract-lang poppler` on macOS, `apt install tesseract-ocr tesseract-ocr-ben poppler-utils` on Debian/Ubuntu).

## Exploring

`search_sources` returns raw passages for a topic. Use it to answer questions about what the books say, or to check coverage before writing.
