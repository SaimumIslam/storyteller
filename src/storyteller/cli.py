"""CLI entry: ingest / ask / search / books."""
from __future__ import annotations

import shutil

import typer

from .config import DEFAULTS_DIR, get_config, home_dir
from .generate import generate_post
from .ingest import ingest_all, list_books
from .retrieve import retrieve
from .style import LENGTH_PRESETS, list_styles, load_style

app = typer.Typer(help="Bangla / English FB Post Generator — RAG-based, any topic", no_args_is_help=True)


@app.command()
def init() -> None:
    """Create the storyteller home (books/, config, rules, styles) for editing."""
    home = home_dir()
    (home / "books").mkdir(parents=True, exist_ok=True)
    for name in ("config.yaml", "rules.yaml", "rules-en.yaml", "rules-islamic.yaml", ".env.example"):
        src, dst = DEFAULTS_DIR / name, home / name
        if src.is_file() and not dst.exists():
            shutil.copy2(src, dst)
            typer.echo(f"created {dst}")
    styles_dst = home / "styles"
    if not styles_dst.exists():
        shutil.copytree(DEFAULTS_DIR / "styles", styles_dst)
        typer.echo(f"created {styles_dst}/")
    typer.echo(f"\nHome: {home}")
    typer.echo(f"Drop .pdf/.txt books into {home / 'books'} then run: storyteller ingest")


@app.command()
def info() -> None:
    """Show where books, index, and output live."""
    cfg = get_config()
    typer.echo(f"home:      {cfg.home}")
    typer.echo(f"books:     {cfg.books_dir}")
    typer.echo(f"index:     {cfg.chroma_path}")
    typer.echo(f"posts:     {cfg.output_dir}")
    typer.echo(f"copy:      {cfg.copy_dir}")
    typer.echo(f"language:  {cfg.language}")
    typer.echo(f"rules:     {cfg.rules_file}")
    typer.echo(f"model:     {cfg.default_model}")
    typer.echo(f"api key:   {'set' if cfg.openrouter_api_key else 'not set (only needed for `ask`)'}")


@app.command()
def ingest() -> None:
    """Ingest all new .pdf/.txt files in the books folder."""
    ingest_all()


@app.command()
def ask(
    topic: str = typer.Option(..., "--topic", "-t", help="Topic in Bangla or English"),
    model: str = typer.Option(None, "--model", "-m", help="OpenRouter model name"),
    k: int = typer.Option(None, "--k", help="Number of chunks to retrieve"),
    style: str = typer.Option(None, "--style", "-s", help="Style name (file in styles/)"),
    length: str = typer.Option(None, "--length", "-l", help="short | medium | long"),
    image: bool = typer.Option(False, "--image", help="Generate an image for the post"),
    lang: str = typer.Option(None, "--lang", help="Output language: bn | en (default: config.yaml `language`)"),
) -> None:
    """Generate a Bangla FB post on a topic."""
    if length and length not in LENGTH_PRESETS:
        typer.echo(f"Invalid --length. Choose one of: {', '.join(LENGTH_PRESETS)}", err=True)
        raise typer.Exit(code=2)
    body, md_path, txt_path, img_path = generate_post(
        topic=topic, model=model, k=k, style_name=style, length=length,
        with_image=True if image else False, language=lang,
    )
    typer.echo(body)
    typer.echo(f"\n---")
    typer.echo(f"archive (.md): {md_path}")
    typer.echo(f"copy   (.txt): {txt_path}   ← paste this to Facebook")
    if img_path is not None:
        typer.echo(f"image  (.png): {img_path}   ← upload with the post")


@app.command()
def mcp() -> None:
    """Run the MCP server (stdio) for AI clients."""
    from .mcp_server import main

    main()


@app.command()
def styles(
    lang: str = typer.Option(None, "--lang", help="bn | en (default: config.yaml `language`)"),
) -> None:
    """List available styles."""
    lang = get_config().lang(lang)
    names = list_styles(lang)
    if not names:
        typer.echo(f"No styles found. Drop .md files into styles/{lang}/.")
        return
    typer.echo(f"Available styles for {lang} ({len(names)}):")
    for n in names:
        try:
            s = load_style(n, lang)
            typer.echo(f"  - {n}  (emotion={s.emotion or '-'}, length={s.length}, examples={len(s.examples)})")
        except Exception as e:
            typer.echo(f"  - {n}  [error: {e}]")


@app.command()
def search(
    topic: str = typer.Option(..., "--topic", "-t", help="Topic to search"),
    k: int = typer.Option(5, "--k", help="Top-k chunks"),
) -> None:
    """Debug: show top-k retrieved chunks for a topic."""
    chunks = retrieve(topic, k=k)
    if not chunks:
        typer.echo("No chunks found. Have you run `ingest`?")
        raise typer.Exit(code=1)
    for i, c in enumerate(chunks, start=1):
        page = f" p.{c.page}" if c.page else ""
        typer.echo(f"\n[{i}] {c.book_title}{page} (score={c.score:.3f}, method={c.extraction_method})")
        typer.echo(c.text[:400] + ("..." if len(c.text) > 400 else ""))


@app.command()
def books() -> None:
    """List ingested books."""
    titles = list(list_books())
    if not titles:
        typer.echo(f"No books ingested yet. Drop files in {get_config().books_dir} and run `ingest`.")
        return
    cfg = get_config()
    typer.echo(f"Ingested books ({len(titles)}):")
    for t in titles:
        typer.echo(f"  - {t}")
    typer.echo(f"\nState file: {cfg.state_file}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
