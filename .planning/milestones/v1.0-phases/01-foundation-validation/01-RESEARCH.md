# Phase 1: Foundation + Validation - Research

**Researched:** 2026-04-01
**Domain:** Python CLI packaging, Playwright auth, Node.js subprocess integration, GLM-OCR via Ollama, pydantic-settings YAML config
**Confidence:** HIGH (stack verified; LOW only for newspapers-com-scraper live behavior and GLM-OCR accuracy on 1970s newsprint)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at Claude's discretion — pure infrastructure phase. Key constraints from PRD:
- CLI framework: Typer + Rich (from research STACK.md)
- Config location: `~/.mouse-research/config.yaml`
- Cookie storage: `~/.mouse-research/cookies/<domain>.json` via Playwright `storage_state()`
- Logging: `~/.mouse-research/logs/YYYY-MM-DD.log` with INFO/DEBUG levels
- Failure log: `~/.mouse-research/logs/failures.jsonl`
- Node.js scraper: installed as local dep in `~/.mouse-research/node_modules/`
- OCR: GLM-OCR via Ollama at `http://localhost:11434`

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and PRD specifications to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SETUP-01 | `mouse-research install` handles Node.js newspapers-com-scraper dependency installation in `~/.mouse-research/` | npm install pattern, package.json in ~/.mouse-research/, scraper-wrapper.js approach documented below |
| SETUP-02 | `pip install mouse-research` or `pip install -e .` installs the tool with all Python dependencies | pyproject.toml entry point pattern, src layout, dependency list verified |
| FOUND-01 | `mouse-research doctor` validates all external dependencies and reports status | Rich Table output pattern, dependency probe commands documented below |
| FOUND-02 | YAML config file at `~/.mouse-research/config.yaml` controls vault paths, OCR settings, browser settings, rate limits, and source domain mapping | pydantic-settings YamlConfigSettingsSource pattern verified from official docs |
| FOUND-03 | Structured logging to `~/.mouse-research/logs/YYYY-MM-DD.log` with INFO/DEBUG levels and `--verbose` flag | Python logging + Rich handler pattern documented below |
| FOUND-04 | Failed URLs logged to `~/.mouse-research/logs/failures.jsonl` for retry | jsonlines append pattern, no extra library needed |
| FOUND-05 | `mouse-research login <domain>` opens visible browser for manual login and saves cookies | Playwright non-headless launch + storage_state() save pattern verified from official docs |
| FOUND-06 | Saved cookies auto-loaded for all Playwright sessions with pre-flight auth check detecting expired sessions | storage_state load pattern + auth preflight check strategy documented below |
</phase_requirements>

---

## Summary

Phase 1 is a greenfield Python CLI project that must accomplish three distinct goals: (1) establish the installable project scaffold with pyproject.toml, Typer entry points, and all Python deps; (2) build the config/cookie/logging foundation that every subsequent phase depends on; and (3) empirically validate the two highest-risk unknowns before any downstream phase is built around them.

The stack is fully determined by prior research in STACK.md and is locked into CLAUDE.md. Python 3.14.3 is installed on the machine (newer than the stated 3.11+ minimum — all required packages support 3.11+ and will work on 3.14). Google Chrome and Obsidian are confirmed present. Node.js 24.14.1 is installed (exceeds 18+ requirement). Ollama, Tesseract, and Playwright browsers are NOT yet installed — these must be installed as part of Phase 1's `mouse-research install` / `doctor` workflow.

The two validation bets are genuinely unknown: `newspapers-com-scraper` v1.1.0 uses Puppeteer + stealth plugin (not a simple HTTP scraper), published a year ago with no updates since, and its live behavior against the current Newspapers.com API is unverified. GLM-OCR accuracy on actual 1970s Pennsylvania microfilm scans is unverified — the OmniDocBench score does not cover degraded historical newsprint. Both must be tested with real data before Phase 2 depends on either.

**Primary recommendation:** Build SETUP-02 first (pyproject.toml scaffold + pip install -e .), then FOUND-01/02/03/04 foundation modules, then FOUND-05/06 cookie management, and finally the two validation tasks (scraper smoke test, GLM-OCR CER test on real 1970s scans) — in that order.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | 0.24.1 | CLI entry point and command dispatch | Verified PyPI Feb 2026; type-hint-driven Click wrapper, no boilerplate |
| rich | 14.3.3 | Terminal output: tables, progress, spinners | Verified PyPI Feb 2026; Typer integrates natively |
| pydantic-settings | 2.13.1 | YAML config loading with type validation | Verified PyPI Feb 2026; `YamlConfigSettingsSource` handles `~/.mouse-research/config.yaml` |
| playwright (Python) | 1.58.0 | Headless Chromium, screenshots, cookie management | Verified PyPI Jan 2026; `storage_state()` is canonical auth pattern |
| ollama (Python SDK) | 0.6.1 | Interface to local Ollama server for GLM-OCR | Verified PyPI Nov 2025; official client |
| pytesseract | 0.3.13 | Fallback OCR when Ollama unavailable | Verified PyPI Aug 2024 |
| Pillow | 12.2.0 | Image loading for OCR, format conversion | Verified PyPI Apr 2026 |
| httpx | 0.28.1 | Sync HTTP for health checks, non-JS fetches | MEDIUM — version from WebSearch, use `>=0.27.0` pin |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| opencv-python | 4.13.0.92 | Image preprocessing before OCR | Phase 2+ — not needed for Phase 1 validation, but declare in deps |
| newspaper4k | 0.9.5 | Article text extraction | Phase 2 — declare in deps now |
| trafilatura | 2.0.0 | Fallback text extraction | Phase 2 — declare in deps now |
| python-frontmatter | 1.1.0 | Obsidian YAML frontmatter read/write | Phase 4 — declare in deps now |

### Node.js Dependencies (installed in `~/.mouse-research/`)

| Package | Version | Purpose |
|---------|---------|---------|
| newspapers-com-scraper | 1.1.0 (pin this) | Newspapers.com keyword search via Puppeteer |
| puppeteer-extra | 3.3.6 | Puppeteer with plugin support (transitive dep) |
| puppeteer-extra-plugin-stealth | 2.11.2 | Anti-bot detection evasion (transitive dep) |

**CRITICAL:** Pin `newspapers-com-scraper` to `1.1.0` in the `~/.mouse-research/package.json`. Do NOT use `latest` — the package was last published a year ago and uses an undocumented internal API that could break silently on update.

**Installation:**
```bash
# System dependencies (Homebrew)
brew install ollama tesseract tesseract-lang

# Playwright browser (bundled Chromium — version-matched to Python package)
pip3 install playwright && playwright install chromium

# Python project (editable install during dev)
pip3 install -e .

# Node.js scraper (installed by mouse-research install command)
mkdir -p ~/.mouse-research
cd ~/.mouse-research && npm install newspapers-com-scraper@1.1.0
```

**Version verification (confirmed 2026-04-01):**
- Node.js 24.14.1 — installed, exceeds 18+ requirement
- Python 3.14.3 — installed, exceeds 3.11+ requirement
- Google Chrome — `/Applications/Google Chrome.app` confirmed present
- Obsidian — `/Applications/Obsidian.app` confirmed present
- Ollama — NOT installed (must install via Homebrew in Phase 1)
- Tesseract — NOT installed (must install via Homebrew in Phase 1)
- Playwright browsers — NOT installed (must run `playwright install chromium`)

---

## Architecture Patterns

### Recommended Project Structure

```
pyproject.toml
src/
  mouse_research/
    __init__.py
    cli.py           # Typer app, all @app.command() decorators — thin dispatch only
    config.py        # AppConfig(BaseSettings) with YamlConfigSettingsSource
    logger.py        # setup_logging(), get_logger() — Rich handler + file handler
    doctor.py        # check_all_dependencies() → DoctorResult dataclass
    cookie_store.py  # save_cookies(), load_cookies(), check_auth() 
    installer.py     # install_node_deps() — runs npm install in ~/.mouse-research/
tests/
  test_config.py
  test_cookie_store.py
  test_doctor.py
  fixtures/
    sample_1970s_scan.jpg     # Real Gettysburg Times / York Daily Record scan for OCR test
```

### Pattern 1: pyproject.toml with Typer Entry Point

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mouse-research"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.24.1",
    "rich>=14.3.3",
    "pydantic-settings>=2.13.1",
    "playwright>=1.58.0",
    "ollama>=0.6.1",
    "pytesseract>=0.3.13",
    "Pillow>=12.2.0",
    "httpx>=0.27.0",
    "opencv-python>=4.13.0",
    "newspaper4k>=0.9.5",
    "trafilatura>=2.0.0",
    "python-frontmatter>=1.1.0",
]

[project.scripts]
mouse-research = "mouse_research.cli:app"
```

### Pattern 2: Typer Multi-Command App

```python
# src/mouse_research/cli.py
import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, help="MOUSE newspaper research pipeline")
console = Console()

@app.command()
def install():
    """Install Node.js dependencies (newspapers-com-scraper)."""
    from mouse_research.installer import install_node_deps
    install_node_deps()

@app.command()
def doctor():
    """Validate all external dependencies."""
    from mouse_research.doctor import check_all_dependencies
    check_all_dependencies()

@app.command()
def login(domain: str = typer.Argument(..., help="Domain to authenticate (e.g. newspapers.com)")):
    """Open browser for manual login and save cookies."""
    from mouse_research.cookie_store import interactive_login
    interactive_login(domain)

if __name__ == "__main__":
    app()
```

### Pattern 3: pydantic-settings YAML Config

```python
# src/mouse_research/config.py
from pathlib import Path
from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

CONFIG_PATH = Path.home() / ".mouse-research" / "config.yaml"

class VaultSettings(BaseModel):
    path: str = str(Path.home() / "Documents" / "Obsidian Vault" /
                    "01-Aumen-Film-Co" / "Projects" / "MOUSE" / "Research")

class OcrSettings(BaseModel):
    primary_engine: str = "glm-ocr"
    ollama_url: str = "http://localhost:11434"
    fallback_engine: str = "tesseract"

class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(yaml_file=str(CONFIG_PATH))

    vault: VaultSettings = VaultSettings()
    ocr: OcrSettings = OcrSettings()
    rate_limit_seconds: float = 5.0
    log_level: str = "INFO"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (YamlConfigSettingsSource(settings_cls), env_settings, init_settings)

def get_config() -> AppConfig:
    """Load config, creating defaults if file doesn't exist."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        _write_default_config()
    return AppConfig()
```

### Pattern 4: Playwright Cookie Save/Load

```python
# src/mouse_research/cookie_store.py
from pathlib import Path
from playwright.sync_api import sync_playwright

COOKIE_DIR = Path.home() / ".mouse-research" / "cookies"

def interactive_login(domain: str) -> None:
    """Open visible browser, wait for login, save storage_state."""
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    cookie_path = COOKIE_DIR / f"{domain}.json"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"https://www.{domain}")
        # Block until user signals completion
        input(f"Log in to {domain} in the browser, then press ENTER here...")
        context.storage_state(path=str(cookie_path))
        browser.close()
    print(f"Cookies saved to {cookie_path}")

def load_cookies_into_context(domain: str, context) -> bool:
    """Load saved storage_state into an existing browser context.
    Returns False if cookie file doesn't exist."""
    cookie_path = COOKIE_DIR / f"{domain}.json"
    if not cookie_path.exists():
        return False
    # storage_state must be passed at new_context() creation, not post-hoc.
    # This function is a reference — callers must pass storage_state at context creation:
    # context = browser.new_context(storage_state=str(cookie_path))
    return True

def preflight_auth_check(domain: str) -> bool:
    """Verify saved cookies still work. Returns True if authenticated."""
    cookie_path = COOKIE_DIR / f"{domain}.json"
    if not cookie_path.exists():
        return False
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(cookie_path))
        page = context.new_page()
        # Fetch a known authenticated URL and check for login indicators
        page.goto(f"https://www.{domain}", wait_until="domcontentloaded", timeout=15000)
        page_text = page.inner_text("body")
        browser.close()
    # If "Sign in" or "Subscribe" is prominent, session is expired
    expired_signals = ["sign in", "log in", "subscribe", "create account"]
    return not any(s in page_text.lower() for s in expired_signals)
```

**CRITICAL NOTE:** `storage_state` must be passed at `browser.new_context(storage_state=...)` creation time — it cannot be injected into an already-created context. The `launch_persistent_context()` API has a known session persistence bug (GitHub issue #36139) and must NOT be used.

### Pattern 5: Ollama GLM-OCR Image Call

```python
# Images must be base64-encoded strings — not file paths
import base64
import ollama

def ocr_image(image_path: str, prompt: str = None) -> str:
    """Run GLM-OCR on an image via Ollama. Returns extracted text."""
    if prompt is None:
        prompt = (
            "Extract all text from this newspaper image. "
            "Preserve reading order. Use [illegible] for unreadable text. "
            "Output as plain text with paragraph breaks."
        )
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    response = ollama.generate(
        model="glm-ocr",
        prompt=prompt,
        images=[image_b64],   # list of base64 strings
        stream=False,
    )
    return response["response"]
```

**Note:** Use `ollama.generate()` with the native endpoint, not the OpenAI-compatible chat endpoint — Ollama's vision API has limitations at the OpenAI compatibility layer.

### Pattern 6: Structured Logging

```python
# src/mouse_research/logger.py
import logging
import sys
from datetime import date
from pathlib import Path
from rich.logging import RichHandler

LOG_DIR = Path.home() / ".mouse-research" / "logs"
FAILURE_LOG = LOG_DIR / "failures.jsonl"

def setup_logging(verbose: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{date.today().isoformat()}.log"
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            RichHandler(rich_tracebacks=True, show_path=False),
            logging.FileHandler(log_file),
        ],
    )

def log_failure(url: str, reason: str, phase: str) -> None:
    """Append a failed URL to failures.jsonl for later retry."""
    import json
    from datetime import datetime
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {"url": url, "reason": reason, "phase": phase,
              "timestamp": datetime.utcnow().isoformat()}
    with open(FAILURE_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")
```

### Pattern 7: Doctor Health Check

```python
# src/mouse_research/doctor.py
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from rich.console import Console
from rich.table import Table

@dataclass
class Check:
    name: str
    status: bool
    detail: str

def check_all_dependencies() -> list[Check]:
    checks = []
    console = Console()

    # Node.js
    node = shutil.which("node")
    checks.append(Check("Node.js", node is not None,
                         subprocess.run(["node", "--version"], capture_output=True,
                                        text=True).stdout.strip() if node else "not found"))

    # Ollama
    checks.append(Check("Ollama", _ping_ollama(), "http://localhost:11434"))

    # GLM-OCR model loaded in Ollama
    checks.append(Check("glm-ocr model", _check_ollama_model("glm-ocr"), "ollama list"))

    # Tesseract
    tess = shutil.which("tesseract")
    checks.append(Check("Tesseract", tess is not None,
                         subprocess.run(["tesseract", "--version"], capture_output=True,
                                        text=True).stdout.split("\n")[0] if tess else "not found"))

    # Playwright/Chromium
    checks.append(Check("Playwright Chromium", _check_playwright(), "playwright install chromium"))

    # newspapers-com-scraper node_modules
    scraper_dir = Path.home() / ".mouse-research" / "node_modules" / "newspapers-com-scraper"
    checks.append(Check("newspapers-com-scraper", scraper_dir.exists(),
                         str(scraper_dir) if scraper_dir.exists() else "run: mouse-research install"))

    # Obsidian vault path
    vault = Path("/Users/aumen-server/Documents/Obsidian Vault/01-Aumen-Film-Co/Projects/MOUSE/Research")
    checks.append(Check("Vault path", vault.exists(), str(vault)))

    # Disk space (warn if < 6 GB free)
    import shutil as sh
    free_gb = sh.disk_usage(Path.home()).free / 1e9
    checks.append(Check("Disk space", free_gb > 6, f"{free_gb:.1f} GB free"))

    _render_table(checks, console)
    return checks
```

### Pattern 8: newspapers-com-scraper Subprocess Wrapper

The scraper uses a **JavaScript API** (event emitter), not a CLI. The PRD specifies a thin `scraper-wrapper.js` that reads CLI args and writes JSON to stdout:

```javascript
// ~/.mouse-research/scraper-wrapper.js
const { NewspapersScraper } = require('newspapers-com-scraper');

const args = process.argv.slice(2);
const keyword = args[0];
const startYear = parseInt(args[1]) || 1970;
const endYear = parseInt(args[2]) || 2025;
const limit = parseInt(args[3]) || 100;

const scraper = new NewspapersScraper({
  keyword,
  dateRange: [startYear, endYear],
  limit,
  browser: {
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  },
});

const results = [];

scraper.on('article', (article) => {
  results.push(article);
});

scraper.on('complete', () => {
  process.stdout.write(JSON.stringify(results) + '\n');
  process.exit(0);
});

scraper.on('error', (err) => {
  process.stderr.write(JSON.stringify({ error: err.message }) + '\n');
  process.exit(1);
});

scraper.retrieve();
```

Python call pattern:
```python
import subprocess, json

result = subprocess.run(
    ["node", str(Path.home() / ".mouse-research/scraper-wrapper.js"),
     keyword, str(start_year), str(end_year), str(limit)],
    capture_output=True, text=True, timeout=120
)
if result.returncode != 0:
    raise RuntimeError(f"Scraper failed: {result.stderr}")
articles = json.loads(result.stdout)
```

**CRITICAL:** Always capture stderr separately and log before attempting JSON parse. Check exit code before parsing stdout. Use a timeout (120s minimum — Puppeteer startup + page load is slow).

### Anti-Patterns to Avoid

- **Calling `launch_persistent_context()`** — known session persistence bug (GitHub #36139). Always use `browser.new_context(storage_state=...)`.
- **Passing storage_state after context creation** — `storage_state` must be given at `new_context()` time; there is no method to inject it into an existing context.
- **Assuming `input()` works in Playwright headless loop** — The login command must use `headless=False` and block on `input()` in the main thread.
- **Parsing Node subprocess stdout without checking exit code first** — silent failures will appear as JSONDecodeError deep in Python code.
- **Using `ollama.chat()` for GLM-OCR** — use `ollama.generate()` with `images=` parameter; the OpenAI-compatible endpoint has vision limitations.
- **Hardcoding config paths** — always derive from `Path.home() / ".mouse-research/"` so the tool works for any user.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML config with type validation | Custom yaml.safe_load + dict parsing | pydantic-settings YamlConfigSettingsSource | Type errors caught at startup, not mid-run; nested models; env var override for free |
| Cookie serialization format | Custom JSON cookie dict | Playwright `context.storage_state()` | Captures cookies + localStorage + IndexedDB — modern auth flows need all three |
| Terminal health check table | Custom print formatting | Rich `Table` with green/red status | Aligned columns, color coding, zero effort |
| Base64 image encoding | Manual file read + encode | `base64.b64encode(f.read()).decode()` (stdlib) | No library needed — one line |
| Log file rotation | Custom date-based filename logic | Python `logging.FileHandler` with daily path | `date.today().isoformat()` in path; no rotation library needed at this scale |
| Failure log format | Custom CSV or plain text | jsonlines (one JSON object per line) | Machine-parseable for retry logic; stdlib `json` is sufficient — no jsonlines library needed |

**Key insight:** Every hand-rolled solution in this domain introduces an edge case at exactly the wrong moment (batch run at 2am). Use the standard mechanism.

---

## Runtime State Inventory

Step 2.5 SKIPPED — greenfield project, no existing runtime state. No databases, no existing services, no OS-registered tasks, no secrets, no build artifacts.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|---------|
| Python 3.11+ | All | ✓ | 3.14.3 | — |
| Node.js 18+ | SETUP-01, FOUND-01, scraper | ✓ | 24.14.1 | — |
| Google Chrome | newspapers-com-scraper (Puppeteer) | ✓ | Present at `/Applications/Google Chrome.app` | — |
| Obsidian | Vault write target | ✓ | Present | — |
| Ollama | FOUND-01 (doctor check), GLM-OCR validation | ✗ | Not installed | Install: `brew install ollama` |
| Tesseract | FOUND-01 (doctor check), OCR fallback | ✗ | Not installed | Install: `brew install tesseract tesseract-lang` |
| Playwright Chromium | FOUND-05, FOUND-06 | ✗ | Not installed | Install: `pip install playwright && playwright install chromium` |
| pip3 | SETUP-02 | ✓ | 26.0 | — |
| npm | SETUP-01 | ✓ | Bundled with Node 24 | — |
| Homebrew | System dep installs | ✓ | Present | — |

**Missing dependencies with no fallback:**
- Ollama — required for GLM-OCR validation (FOUND-01 success criterion 5); no alternative path
- Tesseract — required for FOUND-01 doctor check to report green
- Playwright Chromium — required for FOUND-05 login command and FOUND-06 auth check

**Missing dependencies with fallback:**
- None — all missing items have a clear install path via Homebrew or pip

---

## Common Pitfalls

### Pitfall 1: newspapers-com-scraper Uses Puppeteer, Not Plain HTTP

**What goes wrong:** The scraper is not a simple HTTP client — it uses `puppeteer-extra` with stealth plugin to drive a real Chrome browser. This means it requires Google Chrome to be locatable (it searches PATH and common locations). If `executablePath` is not explicitly set to `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, Puppeteer may use its own bundled Chromium which may conflict with or not satisfy the stealth requirements.

**Why it happens:** `puppeteer-extra-plugin-stealth` modifies browser fingerprints. The bundled Chromium may have different fingerprint characteristics than the stealth plugin expects.

**How to avoid:** Always pass `executablePath` explicitly in `scraper-wrapper.js` pointing to system Chrome. Confirm Chrome path during doctor check.

**Warning signs:** Puppeteer launch errors, "executable not found" errors, search returns 0 results immediately.

### Pitfall 2: Playwright storage_state Cannot Be Loaded Into Existing Context

**What goes wrong:** Developers assume `context.add_cookies()` or a similar post-creation method can restore full session state. They create the context, then try to inject cookies, missing localStorage and sessionStorage — Newspapers.com auth may depend on any of these.

**How to avoid:** Always pass `storage_state=str(cookie_path)` as a kwarg to `browser.new_context()`. If you need to check whether a cookie file exists before creating the context, do the file check first, then create the context conditionally.

**Warning signs:** Auth check passes but page content is still unauthenticated (localStorage/sessionStorage not restored).

### Pitfall 3: GLM-OCR Hallucination on 1970s Microfilm

**What goes wrong:** GLM-OCR is a generative 0.9B vision-language model. On degraded 1970s microfilm scans with ink bleed, torn margins, and multi-column layouts, it fills in plausible-sounding text using language priors when visual signal is weak. Names, dates, and statistics may be silently wrong.

**How to avoid:** The Phase 1 validation task must test with ACTUAL Gettysburg Times / York Daily Record scans from the 1970s — not clean modern documents. Measure Character Error Rate by manually transcribing a ground-truth section and comparing. If CER > 10%, document it clearly. Always embed the original scan in the Obsidian note alongside OCR output — human verification is the final arbiter.

**Warning signs:** OCR output is fluent and plausible but key nouns (names, scores, wrestling statistics) differ from what's visible in the image. Output is longer than the visible text area.

### Pitfall 4: Python 3.14 Compatibility Edge Cases

**What goes wrong:** The project specifies Python 3.11+ but the machine runs 3.14.3. Most packages are compatible, but pre-release Python versions (3.14 was released April 2026) may have C-extension packages that don't yet have compiled wheels for 3.14 — particularly `opencv-python` and potentially `pytesseract`.

**How to avoid:** Run `pip3 install -e .` early and check for wheel availability warnings. If `opencv-python` lacks a 3.14 wheel, use `opencv-python-headless` (smaller, often has faster wheel releases) or build from source. Log findings.

**Warning signs:** `pip install` proceeds with source builds (very slow), or `ModuleNotFoundError` on import despite successful install.

### Pitfall 5: Ollama Model Cold Start Timeout

**What goes wrong:** The first call to GLM-OCR via Ollama triggers a model load from disk (~2.2 GB). This takes 30–60 seconds on Apple Silicon. If the Phase 1 validation script uses a tight timeout (e.g., 30s default), the first OCR call appears to fail.

**How to avoid:** Use a 120-second timeout on the first `ollama.generate()` call. Add a model warmup step in `doctor` that makes a trivial OCR call to force model load. Detect "model loading" responses.

**Warning signs:** First OCR call times out or returns empty response; second call works fine.

### Pitfall 6: Newspapers.com Session Silently Fails Without Re-Login Prompt

**What goes wrong:** Playwright loads stale cookies with no error. Newspapers.com serves a degraded (unauthenticated) page rather than raising an HTTP error. The pipeline proceeds as if authenticated, storing empty or login-wall content.

**How to avoid:** Implement `preflight_auth_check()` (see Pattern 4 above). Call it before every Playwright session. If it returns False, halt with: `"Session expired. Run: mouse-research login newspapers.com"`. Never proceed silently.

**Warning signs:** Screenshots show login/subscribe pages. newspaper4k extracts zero text from pages that should have articles.

---

## Code Examples

### Minimal installable pyproject.toml

```toml
# Source: Python Packaging Authority (packaging.python.org)
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mouse-research"
version = "0.1.0"
requires-python = ">=3.11"
description = "Newspaper research pipeline for the MOUSE documentary"
dependencies = [
    "typer>=0.24.1",
    "rich>=14.3.3",
    "pydantic-settings>=2.13.1",
    "playwright>=1.58.0",
    "ollama>=0.6.1",
    "pytesseract>=0.3.13",
    "Pillow>=12.2.0",
    "httpx>=0.27.0",
    "opencv-python>=4.13.0",
    "newspaper4k>=0.9.5",
    "trafilatura>=2.0.0",
    "python-frontmatter>=1.1.0",
]

[project.scripts]
mouse-research = "mouse_research.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/mouse_research"]
```

### GLM-OCR Validation Test (Phase 1 success criterion 5)

```python
# Measure Character Error Rate on a real 1970s scan
# Run after ollama pull glm-ocr and ollama serve

import base64, ollama

def validate_glm_ocr(image_path: str, ground_truth: str) -> dict:
    """
    Returns: {'cer': float, 'ocr_text': str, 'engine': 'glm-ocr'}
    CER = edit_distance(ocr, truth) / len(truth)
    """
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    resp = ollama.generate(
        model="glm-ocr",
        prompt="Extract all text from this newspaper clipping. Preserve reading order. Mark illegible text as [illegible].",
        images=[img_b64],
        stream=False,
    )
    ocr_text = resp["response"]
    cer = _char_error_rate(ocr_text, ground_truth)
    return {"cer": cer, "ocr_text": ocr_text, "engine": "glm-ocr"}

def _char_error_rate(hypothesis: str, reference: str) -> float:
    """Levenshtein distance normalized by reference length."""
    import Levenshtein  # pip install python-Levenshtein
    return Levenshtein.distance(hypothesis, reference) / max(len(reference), 1)
```

### newspapers-com-scraper Smoke Test (Phase 1 success criterion 4)

```python
import subprocess, json
from pathlib import Path

def smoke_test_scraper(keyword: str = "wrestling Gettysburg 1978") -> dict:
    """
    Returns first result dict or raises on failure.
    Expected fields: title, date, location, url, keywordMatches
    """
    wrapper = Path.home() / ".mouse-research" / "scraper-wrapper.js"
    result = subprocess.run(
        ["node", str(wrapper), keyword, "1975", "1985", "5"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Scraper exited {result.returncode}. stderr: {result.stderr[:500]}"
        )
    if not result.stdout.strip():
        raise RuntimeError("Scraper returned empty stdout")
    articles = json.loads(result.stdout)
    assert len(articles) > 0, "Expected at least 1 result for known query"
    first = articles[0]
    for field in ("title", "date", "url"):
        assert field in first, f"Missing field '{field}' in scraper output"
    return first
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| newspaper3k (unmaintained) | newspaper4k 0.9.5 | 2022 (fork) | newspaper3k has known Python 3.11+ incompatibilities; newspaper4k is the maintained fork |
| Selenium for browser automation | Playwright with storage_state | ~2021 | Playwright is faster, more reliable, has native Python async support and built-in state management |
| Tesseract alone for OCR | GLM-OCR (generative) primary + Tesseract fallback | 2024–2025 | Generative models handle context-aware inference on degraded text; Tesseract remains valuable as a deterministic fallback |
| Click for Python CLIs | Typer 0.24.1 | ~2020 | Typer generates CLI from type annotations; no decorator argument lists to maintain |
| python-dotenv for config | pydantic-settings with YAML | ~2022 | Type validation at load time; YAML is more human-readable for nested config |

**Deprecated/outdated:**
- `newspaper3k`: unmaintained since 2020; use `newspaper4k` exclusively
- `launch_persistent_context()` in Playwright: has session persistence bug #36139; use `new_context(storage_state=...)` instead
- `ollama.chat()` for vision: OpenAI-compatible endpoint has limitations with images; use `ollama.generate()` with `images=` parameter

---

## Open Questions

1. **newspapers-com-scraper live behavior against current Newspapers.com API**
   - What we know: Package v1.1.0, published ~1 year ago, uses Puppeteer stealth, wraps undocumented internal API
   - What's unclear: Whether the internal API still returns the documented fields (`title`, `date`, `location`, `url`, `keywordMatches`); whether rate limiting or auth is required for search; whether Google Chrome path detection works without explicit `executablePath`
   - Recommendation: The Phase 1 smoke test (success criterion 4) is the only way to resolve this. Plan must execute this test against the live site before Phase 2 is built.

2. **GLM-OCR Character Error Rate on actual 1970s Pennsylvania microfilm**
   - What we know: OmniDocBench V1.5 score is 94.62 on the benchmark corpus; benchmark does not cover degraded microfilm
   - What's unclear: Whether CER on actual Gettysburg Times / York Daily Record 1970s scans is acceptable (< 10%) or requires Tesseract fallback or OpenCV preprocessing
   - Recommendation: Test with minimum 3 real scans, manually transcribe ground truth for one column of text each, compute CER. Document result. If CER > 15%, re-evaluate primary engine choice and escalate to user.

3. **Python 3.14 wheel availability for opencv-python**
   - What we know: opencv-python 4.13.0.92 was released Feb 2026; Python 3.14 was released Apr 2026
   - What's unclear: Whether opencv-python has compiled wheels for 3.14 yet (C extension — wheel lag is common)
   - Recommendation: Attempt `pip3 install opencv-python` early in Phase 1; if it fails or builds from source, use `opencv-python-headless` as alternative.

4. **Newspapers.com session duration**
   - What we know: Cookie storage via `storage_state()` is robust; exact Newspapers.com session duration is unknown
   - What's unclear: Whether sessions expire in 24 hours, 7 days, or 30 days; whether accessing pages extends the session
   - Recommendation: Document observed session duration during FOUND-05/06 testing. Store cookie file mtime and warn if older than 7 days.

---

## Sources

### Primary (HIGH confidence)
- Playwright Python auth docs (playwright.dev/python/docs/auth) — storage_state save/load pattern, `new_context(storage_state=)` API
- pydantic-settings docs (docs.pydantic.dev) — `YamlConfigSettingsSource`, `SettingsConfigDict(yaml_file=)` pattern
- Ollama REST API docs (github.com/ollama/ollama/blob/main/docs/api.md) — `images` field is base64 array in generate endpoint
- GLM-OCR Ollama library page (ollama.com/library/glm-ocr) — model name, size, quantization options
- newspapers-com-scraper npm registry (npmjs.com) — v1.1.0, MIT, 5 versions, deps: puppeteer-extra + stealth
- CLAUDE.md (this repo) — locked stack decisions, all versions verified against PyPI
- STACK.md (this repo) — full dependency list with PyPI version verification dates
- ARCHITECTURE.md (this repo) — component boundaries, data flow, build order
- PITFALLS.md (this repo) — critical pitfalls with root cause analysis

### Secondary (MEDIUM confidence)
- newspapers-com-scraper GitHub README (github.com/njraladdin/newspapers-com-scraper) — event API (article/progress/complete), config options, Chrome requirement confirmed
- Typer commands tutorial (typer.tiangolo.com/tutorial/commands/) — `@app.command()` pattern, `app()` vs `typer.run()` for multi-command CLIs

### Tertiary (LOW confidence)
- GLM-OCR accuracy on 1970s newsprint — no direct evidence found; inferred from OmniDocBench scores and general multimodal LLM hallucination research (arXiv 2501.11623). Empirical testing in Phase 1 is the only way to establish actual CER.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all Python package versions verified against PyPI in CLAUDE.md; Node/Python/Chrome/Obsidian environment verified live
- Architecture: HIGH — patterns drawn from official docs (Playwright, pydantic-settings, Ollama API); pyproject.toml pattern from Python Packaging Authority
- Pitfalls: HIGH for Playwright/config patterns (official docs); MEDIUM for scraper behavior (untested); MEDIUM for GLM-OCR accuracy on target corpus (no direct evidence)

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable ecosystem; newspapers-com-scraper live behavior should be re-validated if > 30 days since last confirmed working run)
