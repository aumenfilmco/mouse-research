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


def _display_results(results: list, excluded_count: int) -> None:
    """Display search results in a Rich Table."""
    from rich.table import Table

    table = Table(title=f"Search Results ({len(results)} found)")
    table.add_column("#", style="bold", width=4)
    table.add_column("Newspaper", min_width=20)
    table.add_column("Date", width=12)
    table.add_column("Location", min_width=15)
    table.add_column("URL", overflow="fold", max_width=40)
    table.add_column("Matches", width=8, justify="right")

    for r in results:
        # Extract URL snippet after /image/ if present, else truncate to 40 chars
        url = r.url
        if "/image/" in url:
            snippet = "..." + url[url.index("/image/"):]
            if len(snippet) > 40:
                snippet = snippet[:37] + "..."
        else:
            snippet = url[:40] + "..." if len(url) > 40 else url

        table.add_row(
            str(r.number),
            r.title,
            r.date,
            r.location,
            snippet,
            str(r.keyword_matches),
        )

    console.print(table)
    if excluded_count > 0:
        console.print(f"[dim]{excluded_count} result(s) excluded (already in vault)[/dim]")


def _batch_archive_with_progress(
    urls_and_titles: list[tuple[str, str]],
    config,
    persons: list,
    tags: list,
) -> None:
    """Archive a list of (url, title) pairs with a Rich Progress bar and rate limiting."""
    import time
    from mouse_research.archiver import archive_url
    from rich.progress import Progress, SpinnerColumn, BarColumn, TaskProgressColumn, TextColumn

    archived = 0
    failed = 0

    try:
        with Progress(
            SpinnerColumn(),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[dim]{task.description}"),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task("Archiving", total=len(urls_and_titles))
            for i, (url, title) in enumerate(urls_and_titles):
                if i > 0:
                    time.sleep(config.rate_limit_seconds)
                desc = title[:50] + "..." if len(title) > 50 else title
                progress.update(task, description=desc)
                result = archive_url(url, config, person=persons, tags=tags)
                if result.error:
                    failed += 1
                else:
                    archived += 1
                progress.advance(task)
    except KeyboardInterrupt:
        remaining = len(urls_and_titles) - archived - failed
        console.print(f"\n[yellow]Interrupted.[/yellow] Partial results:")
        console.print(f"  Archived: {archived}  Failed: {failed}  Remaining: {remaining}")
        raise typer.Exit(code=130)

    console.print(f"[bold]Done:[/bold] {archived} archived, {failed} failed")
    if failed > 0:
        console.print("[yellow]Failed URLs logged to:[/yellow] ~/.mouse-research/logs/failures.jsonl")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search term (e.g. 'Dave McCollum wrestling')"),
    years: Optional[str] = typer.Option(None, "--years", help="Year or range: 1982 or 1975-1985"),
    location: Optional[str] = typer.Option(None, "--location", help="State name or region code (e.g. 'Pennsylvania' or 'us-pa')"),
    auto_archive: bool = typer.Option(False, "--auto-archive", help="Archive all results without interactive review"),
    person: Optional[list[str]] = typer.Option(None, "--person", "-p", help="Person name(s) to associate"),
    tag: Optional[list[str]] = typer.Option(None, "--tag", "-t", help="Tag(s) to apply"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    """Search Newspapers.com and archive selected results.

    Examples:
        mouse-research search 'Dave McCollum'
        mouse-research search 'McCollum' --years 1975-1985 --location Pennsylvania
        mouse-research search 'McCollum' --auto-archive --person 'Dave McCollum'
    """
    from mouse_research.config import get_config
    from mouse_research.logger import setup_logging
    from mouse_research.searcher import search_and_filter, parse_selection, ScraperError

    setup_logging(verbose=verbose)
    config = get_config()
    persons = list(person) if person else []
    tags = list(tag) if tag else ["newspaper", "archive"]

    try:
        results, excluded_count = search_and_filter(query, years, location, config)
    except ScraperError as e:
        console.print(f"[red]Search failed:[/red] {e}")
        raise typer.Exit(code=1)

    if not results:
        console.print(f"[yellow]No results found for '{query}'.[/yellow]")
        console.print("[dim]Try broadening your search — remove --years or --location filters.[/dim]")
        return

    _display_results(results, excluded_count)

    if auto_archive:
        urls_and_titles = [(r.url, r.title) for r in results]
        _batch_archive_with_progress(urls_and_titles, config, persons, tags)
    else:
        from rich.prompt import Prompt
        selection_str = Prompt.ask("Enter selection (e.g. 1,3,5-12,all)")
        try:
            indices = parse_selection(selection_str, len(results))
        except ValueError as e:
            console.print(f"[red]Invalid selection:[/red] {e}")
            raise typer.Exit(code=1)
        selected = [(results[i].url, results[i].title) for i in indices]
        console.print(f"Archiving [bold]{len(selected)}[/bold] articles...")
        _batch_archive_with_progress(selected, config, persons, tags)


@app.command(name="retry-failures")
def retry_failures(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    """Reprocess failed URLs from failures.jsonl."""
    import json
    import time
    from mouse_research.config import get_config
    from mouse_research.logger import setup_logging, FAILURE_LOG
    from mouse_research.archiver import archive_url
    from rich.progress import Progress, SpinnerColumn, BarColumn, TaskProgressColumn, TextColumn

    setup_logging(verbose=verbose)
    config = get_config()

    if not FAILURE_LOG.exists():
        console.print("[yellow]No failures log found.[/yellow]")
        return

    records = []
    seen: set[str] = set()
    for line in FAILURE_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        url = record.get("url", "")
        if url and url not in seen:
            seen.add(url)
            records.append(record)

    if not records:
        console.print("[green]No failures to retry.[/green]")
        return

    console.print(f"Retrying [bold]{len(records)}[/bold] failed URL(s)...")

    still_failed: list[dict] = []
    archived = 0

    with Progress(
        SpinnerColumn(),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[dim]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Retrying", total=len(records))
        for i, record in enumerate(records):
            if i > 0:
                time.sleep(config.rate_limit_seconds)
            desc = record.get("reason", "")[:50]
            progress.update(task, description=desc)
            result = archive_url(record["url"], config)
            if result.skipped:
                archived += 1
            elif result.error or not result.success:
                still_failed.append(record)
            else:
                archived += 1
            progress.advance(task)

    FAILURE_LOG.write_text(
        "\n".join(json.dumps(r) for r in still_failed) + ("\n" if still_failed else ""),
        encoding="utf-8",
    )

    console.print(f"[bold]Done:[/bold] {archived} resolved, {len(still_failed)} still failed")


if __name__ == "__main__":
    app()
