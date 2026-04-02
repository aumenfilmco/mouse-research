"""Typer CLI entry point for mouse-research."""
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, help="MOUSE newspaper research pipeline")
console = Console()


@app.command()
def install():
    """Install Node.js dependencies (newspapers-com-scraper)."""
    from mouse_research.installer import install_node_deps
    success = install_node_deps(console)
    if not success:
        raise typer.Exit(code=1)


@app.command()
def doctor():
    """Validate all external dependencies and report status."""
    from mouse_research.doctor import run_doctor
    all_pass = run_doctor()
    if not all_pass:
        raise typer.Exit(code=1)


@app.command()
def login(domain: str = typer.Argument(..., help="Domain to authenticate (e.g. newspapers.com)")):
    """Open browser for manual login and save cookies."""
    from mouse_research.cookies import interactive_login
    success = interactive_login(domain, console)
    if not success:
        raise typer.Exit(code=1)


@app.command()
def archive(
    url: str = typer.Argument(None, help="URL of article to archive"),
    file: Optional[Path] = typer.Option(None, "--file", "-f",
        help="File containing URLs to archive (one per line)"),
    person: Optional[list[str]] = typer.Option(None, "--person", "-p",
        help="Person name(s) to associate (repeatable: --person 'Dave McCollum' --person 'John Smith')"),
    tag: Optional[list[str]] = typer.Option(None, "--tag", "-t",
        help="Tag(s) to apply (repeatable)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    """Archive a newspaper article URL into the Obsidian vault.

    Single URL:   mouse-research archive https://www.newspapers.com/image/12345678/
    From file:    mouse-research archive --file urls.txt
    With person:  mouse-research archive <url> --person "Dave McCollum"
    """
    from mouse_research.config import get_config
    from mouse_research.logger import setup_logging

    setup_logging(verbose=verbose)
    config = get_config()
    tags = list(tag) if tag else ["newspaper", "archive"]
    persons = list(person) if person else []

    if file is not None:
        # --file mode: batch archiving with 5-second rate limiting (ARCH-11)
        _archive_file(file, config, persons, tags)
    elif url is not None:
        # Single URL mode
        _archive_single(url, config, persons, tags)
    else:
        console.print("[red]Error:[/red] Provide a URL or --file path.")
        raise typer.Exit(code=1)


def _archive_single(url: str, config, persons: list, tags: list) -> None:
    """Archive one URL and print result."""
    from mouse_research.archiver import archive_url

    with console.status(f"Archiving [bold]{url}[/bold]..."):
        result = archive_url(url, config, person=persons, tags=tags)

    if result.skipped:
        console.print(f"[yellow]Skipped:[/yellow] {result.skip_reason}")
        console.print(f"URL already in vault: {url}")
    elif result.error:
        console.print(f"[red]Failed:[/red] {result.error}")
        raise typer.Exit(code=1)
    else:
        console.print(f"[green]Archived:[/green] {result.slug}")
        console.print(f"Folder: {result.folder}")
        if result.ocr_queued:
            console.print("[yellow]Note:[/yellow] OCR queued — run when Ollama is available")


def _archive_file(file_path: Path, config, persons: list, tags: list) -> None:
    """Archive multiple URLs from a file with 5-second rate limiting.

    Rate limiting: 5 seconds between fetches (config.rate_limit_seconds).
    Failures: logged to failures.jsonl, printed as warnings, batch continues.
    """
    import time
    from mouse_research.archiver import archive_url

    if not file_path.exists():
        console.print(f"[red]Error:[/red] File not found: {file_path}")
        raise typer.Exit(code=1)

    urls = [
        line.strip() for line in file_path.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not urls:
        console.print("[yellow]No URLs found in file.[/yellow]")
        return

    console.print(f"Archiving [bold]{len(urls)}[/bold] URLs from {file_path.name}")
    archived = skipped = failed = 0

    for i, url in enumerate(urls):
        if i > 0:
            # Rate limiting: 5-second delay between fetches
            delay = config.rate_limit_seconds
            console.print(f"[dim]Waiting {delay:.0f}s before next fetch...[/dim]")
            time.sleep(delay)

        console.print(f"\n[{i+1}/{len(urls)}] {url}")
        result = archive_url(url, config, person=persons, tags=tags)

        if result.skipped:
            console.print(f"  [yellow]Skipped:[/yellow] {result.skip_reason}")
            skipped += 1
        elif result.error:
            console.print(f"  [red]Failed:[/red] {result.error}")
            failed += 1
            # Continue with next URL — failure already logged to failures.jsonl by archiver
        else:
            console.print(f"  [green]OK:[/green] {result.slug}")
            if result.ocr_queued:
                console.print("  [yellow]OCR queued[/yellow]")
            archived += 1

    console.print(f"\n[bold]Done:[/bold] {archived} archived, {skipped} skipped, {failed} failed")
    if failed > 0:
        console.print(f"[yellow]Failed URLs logged to:[/yellow] ~/.mouse-research/logs/failures.jsonl")


@app.command()
def ocr(
    image_path: Path = typer.Argument(..., help="Path to image file to OCR"),
    person: Optional[list[str]] = typer.Option(None, "--person", "-p",
        help="Person name(s) to associate"),
    source: Optional[str] = typer.Option(None, "--source", "-s",
        help="Publication name (e.g. 'Gettysburg Times')"),
    article_date: Optional[str] = typer.Option(None, "--date", "-d",
        help="Article date (YYYY-MM-DD)"),
    tag: Optional[list[str]] = typer.Option(None, "--tag", "-t",
        help="Tag(s) to apply"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    """OCR a local newspaper scan and export to the Obsidian vault.

    Example: mouse-research ocr scan.jpg --person "Dave McCollum" --date 1986-03-15 --source "Gettysburg Times"
    """
    import shutil
    from datetime import date as date_cls

    from mouse_research.config import get_config
    from mouse_research.logger import setup_logging
    from mouse_research.ocr import ocr_image
    from mouse_research.obsidian import make_slug, create_article_folder, write_article_note, write_metadata_json
    from mouse_research.types import ArticleRecord, ArticleData, OcrResult

    setup_logging(verbose=verbose)
    config = get_config()

    if not image_path.exists():
        console.print(f"[red]Error:[/red] File not found: {image_path}")
        raise typer.Exit(code=1)

    persons = list(person) if person else []
    tags = list(tag) if tag else ["newspaper", "scan", "archive"]
    source_name = source or "Unknown Source"

    # Parse date
    pub_date = None
    if article_date:
        try:
            pub_date = date_cls.fromisoformat(article_date)
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid date format '{article_date}' — use YYYY-MM-DD")
            raise typer.Exit(code=1)

    with console.status(f"Running OCR on [bold]{image_path.name}[/bold]..."):
        ocr_result = ocr_image(image_path, config, url=str(image_path))

    if ocr_result.queued:
        console.print("[yellow]OCR queued:[/yellow] Neither Ollama nor Tesseract available.")
        console.print(f"Image queued at: ~/.mouse-research/ocr-queue.jsonl")

    # Extract title from first OCR line (or use filename)
    title = image_path.stem.replace("_", " ").replace("-", " ")
    if ocr_result.text:
        first_line = ocr_result.text.strip().splitlines()[0].lstrip("#").strip()
        if first_line and len(first_line) < 120:
            title = first_line

    article_data = ArticleData(
        title=title,
        publish_date=pub_date,
        extraction_method="none",
    )

    slug = make_slug(pub_date, source_name, title)
    today = date_cls.today()
    folder = create_article_folder(config.vault.path, slug)

    # Copy original image to vault folder
    dest_image = folder / image_path.name
    shutil.copy2(str(image_path), str(dest_image))

    # Save raw OCR text
    if ocr_result.text:
        (folder / "ocr_raw.md").write_text(ocr_result.text, encoding="utf-8")

    record = ArticleRecord(
        slug=slug,
        url=str(image_path.resolve()),
        source_name=source_name,
        article_data=article_data,
        ocr_result=ocr_result,
        screenshot_path=dest_image,  # Use copied image as the "screenshot"
        page_image_path=None,
        article_image_path=None,
        person=persons,
        tags=tags,
        captured=today,
    )

    write_article_note(folder, record)
    write_metadata_json(folder, record)

    console.print(f"[green]OCR complete:[/green] {slug}")
    console.print(f"Folder: {folder}")
    console.print(f"Engine: {ocr_result.engine}")


if __name__ == "__main__":
    app()
