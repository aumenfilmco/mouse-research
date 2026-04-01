"""Node.js dependency installer for newspapers-com-scraper."""
import json
import subprocess
import shutil
from pathlib import Path

from rich.console import Console

MOUSE_DIR = Path.home() / ".mouse-research"
NODE_DIR = MOUSE_DIR
PACKAGE_JSON = NODE_DIR / "package.json"


def install_node_deps(console: Console | None = None) -> bool:
    """Install newspapers-com-scraper via npm in ~/.mouse-research/.

    Creates package.json if missing, runs npm install.
    Returns True on success, False on failure.
    """
    if console is None:
        console = Console()

    # Check Node.js is available
    node_path = shutil.which("node")
    if not node_path:
        console.print("[red]Error:[/red] Node.js not found. Install with: brew install node")
        return False

    npm_path = shutil.which("npm")
    if not npm_path:
        console.print("[red]Error:[/red] npm not found. Install with: brew install node")
        return False

    # Create directory
    NODE_DIR.mkdir(parents=True, exist_ok=True)

    # Create package.json if missing
    if not PACKAGE_JSON.exists():
        pkg = {
            "name": "mouse-research-node-deps",
            "version": "1.0.0",
            "private": True,
            "description": "Node.js dependencies for mouse-research CLI",
            "dependencies": {
                "newspapers-com-scraper": "1.1.0"
            }
        }
        PACKAGE_JSON.write_text(json.dumps(pkg, indent=2) + "\n")
        console.print(f"Created {PACKAGE_JSON}")

    # Run npm install
    console.print("Installing Node.js dependencies...")
    result = subprocess.run(
        [npm_path, "install"],
        cwd=str(NODE_DIR),
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        console.print(f"[red]npm install failed:[/red]\n{result.stderr}")
        return False

    console.print("[green]Node.js dependencies installed successfully.[/green]")
    return True
