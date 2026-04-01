"""Typer CLI entry point for mouse-research."""
import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, help="MOUSE newspaper research pipeline")
console = Console()


@app.command()
def install():
    """Install Node.js dependencies (newspapers-com-scraper)."""
    console.print("[yellow]install command not yet implemented — run after plan 01-03[/yellow]")


@app.command()
def doctor():
    """Validate all external dependencies and report status."""
    console.print("[yellow]doctor command not yet implemented — run after plan 01-04[/yellow]")


@app.command()
def login(domain: str = typer.Argument(..., help="Domain to authenticate (e.g. newspapers.com)")):
    """Open browser for manual login and save cookies."""
    console.print(f"[yellow]login command not yet implemented — run after plan 01-05[/yellow]")


if __name__ == "__main__":
    app()
