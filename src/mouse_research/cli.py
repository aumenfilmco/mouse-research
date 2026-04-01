"""Typer CLI entry point for mouse-research."""
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


if __name__ == "__main__":
    app()
