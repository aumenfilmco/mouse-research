"""Health check for mouse-research external dependencies."""
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from mouse_research.config import get_config
from mouse_research.installer import MOUSE_DIR


def _check_command(cmd: str, version_flag: str = "--version") -> tuple[bool, str]:
    """Check if a command exists and get its version."""
    path = shutil.which(cmd)
    if not path:
        return False, "not found"
    try:
        result = subprocess.run(
            [path, version_flag],
            capture_output=True, text=True, timeout=10,
        )
        version = result.stdout.strip() or result.stderr.strip()
        # Take first line only
        version = version.split("\n")[0][:60]
        return True, version
    except (subprocess.TimeoutExpired, OSError):
        return True, "found (version unknown)"


def _check_ollama_running(ollama_url: str) -> tuple[bool, str]:
    """Check if Ollama server is running."""
    try:
        import httpx
        resp = httpx.get(f"{ollama_url}/api/tags", timeout=5.0)
        if resp.status_code == 200:
            return True, "running"
        return False, f"HTTP {resp.status_code}"
    except Exception:
        return False, "not running — start with: ollama serve"


def _check_glm_ocr(ollama_url: str) -> tuple[bool, str]:
    """Check if GLM-OCR model is pulled in Ollama."""
    try:
        import httpx
        resp = httpx.get(f"{ollama_url}/api/tags", timeout=5.0)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            for m in models:
                if "glm-ocr" in m.get("name", ""):
                    size_gb = m.get("size", 0) / (1024**3)
                    return True, f"pulled ({size_gb:.1f} GB)"
            return False, "not pulled — run: ollama pull glm-ocr"
        return False, "cannot check (Ollama not running)"
    except Exception:
        return False, "cannot check (Ollama not running)"


def _check_playwright_browsers() -> tuple[bool, str]:
    """Check if Playwright Chromium is installed."""
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium; p.stop(); print('OK')"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return True, "chromium installed"
        return False, "not installed — run: playwright install chromium"
    except Exception:
        return False, "check failed"


def _check_vault_path(vault_path: str) -> tuple[bool, str]:
    """Check if the Obsidian vault path exists and is writable."""
    p = Path(vault_path)
    if not p.exists():
        return False, f"not found: {vault_path}"
    if not p.is_dir():
        return False, f"not a directory: {vault_path}"
    # Check writable
    try:
        test_file = p / ".mouse-research-write-test"
        test_file.touch()
        test_file.unlink()
        return True, str(vault_path)
    except OSError:
        return False, f"not writable: {vault_path}"


def _check_disk_space() -> tuple[bool, str]:
    """Check available disk space (need at least 5 GB)."""
    import os
    stat = os.statvfs(str(Path.home()))
    free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
    if free_gb >= 5.0:
        return True, f"{free_gb:.1f} GB free"
    return False, f"{free_gb:.1f} GB free (need 5 GB)"


def _check_node_scraper() -> tuple[bool, str]:
    """Check if newspapers-com-scraper is installed in ~/.mouse-research/."""
    scraper_dir = MOUSE_DIR / "node_modules" / "newspapers-com-scraper"
    if scraper_dir.exists():
        pkg_json = scraper_dir / "package.json"
        if pkg_json.exists():
            import json
            pkg = json.loads(pkg_json.read_text())
            version = pkg.get("version", "unknown")
            return True, f"v{version}"
        return True, "installed"
    return False, "not installed — run: mouse-research install"


def run_doctor() -> bool:
    """Run all health checks and display results. Returns True if all pass."""
    config = get_config()
    console = Console()
    table = Table(title="mouse-research doctor", show_header=True)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    checks = [
        ("Python", *_check_command("python3")),
        ("Node.js", *_check_command("node")),
        ("npm", *_check_command("npm")),
        ("Ollama", *_check_ollama_running(config.ocr.ollama_url)),
        ("GLM-OCR model", *_check_glm_ocr(config.ocr.ollama_url)),
        ("Tesseract", *_check_command("tesseract")),
        ("Playwright", *_check_playwright_browsers()),
        ("Scraper (npm)", *_check_node_scraper()),
        ("Vault path", *_check_vault_path(config.vault.path)),
        ("Disk space", *_check_disk_space()),
    ]

    all_pass = True
    for name, ok, details in checks:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        if not ok:
            all_pass = False
            details = f"[red]{details}[/red]"
        table.add_row(name, status, details)

    console.print(table)

    if all_pass:
        console.print("\n[green bold]All checks passed.[/green bold]")
    else:
        console.print("\n[yellow]Some checks failed. Fix the issues above and re-run: mouse-research doctor[/yellow]")

    return all_pass
