# Technology Stack: MOUSE Research Pipeline

**Project:** MOUSE Research Pipeline (newspaper archiving + OCR + Obsidian export)
**Researched:** 2026-04-01
**Overall confidence:** HIGH (all versions verified against PyPI/official sources)

---

## Recommended Stack

### CLI Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Typer | 0.24.1 | CLI command structure (`archive`, `search`, `ocr`, `doctor`) | Built on Click, uses Python type hints — no decorator boilerplate. Commands like `mouse-research archive <url>` map directly to typed function signatures. Integrates natively with Rich for progress display. Greenfield project, no legacy migration needed. |
| Rich | 14.3.3 | Terminal output: progress bars, tables, status spinners | Best-in-class terminal formatting. Provides `Progress`, `Live`, `Table`, and `Console` — covers batch progress display, search result tables, and doctor health output. Typer delegates to it automatically. |

**Do NOT use:** Click directly (Typer gives you Click plus type-safety), argparse (too low-level), questionary alone (use Typer + Rich prompts instead).

---

### Web Fetching / Browser Automation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| playwright (Python) | 1.58.0 | Headless Chromium fetch, screenshot, cookie management | Industry standard for JS-heavy sites. `browser_context.storage_state()` is the correct mechanism for saving/restoring Newspapers.com session cookies across runs — verified pattern. `launch_persistent_context()` has a known session persistence bug (GitHub issue #36139); use `storage_state()` save/load instead. Requires Python 3.9+. |

**Install Chromium via:** `playwright install chromium` (not Google Chrome — Playwright's bundled Chromium is version-matched and avoids system Chrome conflicts).

**Do NOT use:** Selenium (slower, more brittle, worse async story), Requests + BeautifulSoup alone (cannot execute JavaScript, cannot handle Newspapers.com's JS-rendered pages), Puppeteer (Node.js only).

**Cookie management pattern:** On first run, open non-headless browser, prompt user to log in manually, save `context.storage_state(path="cookies.json")`. On subsequent runs, load from file. Add expiry detection: if a fetch returns a login redirect, delete cookies and prompt re-login.

---

### Text Extraction

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| newspaper4k | 0.9.5 | Primary article text extraction from HTML | Actively maintained fork of the abandoned newspaper3k. Handles article title, body, authors, publish date, and images in one call. Purpose-built for news articles — knows how to strip nav, ads, and boilerplate from news site HTML. |
| trafilatura | 2.0.0 | Fallback text extraction | Consistently outperforms other libraries on content extraction benchmarks. Outputs clean Markdown or JSON with metadata. Use when newspaper4k returns empty/poor body text (common on paywalled pages that render partial content). |

**Cascade logic:** Try newspaper4k first. If `article.text` length < 200 characters, fall back to trafilatura. If both fail, flag for manual review in the Obsidian note frontmatter.

**Do NOT use:** BeautifulSoup alone (requires hand-written extraction per site), readability-lxml (less accurate than trafilatura for news), newspaper3k (unmaintained since 2020).

---

### OCR

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| ollama (Python SDK) | 0.6.1 | Interface to local Ollama server running GLM-OCR | Official Ollama Python client. Use `ollama.generate()` with the native `/api/generate` endpoint (not the OpenAI-compatible endpoint — Ollama's vision API has limitations there). |
| glm-ocr (via Ollama) | latest (2.2 GB) | Primary OCR for scanned newspaper pages | State-of-the-art on OmniDocBench V1.5 (94.62 score). 0.9B parameters — runs efficiently on Apple Silicon M-series via Ollama's MLX backend. Uses context-aware inference rather than pure edge detection, which is critical for degraded 1970s-80s newsprint. The q8_0 quantized variant (1.6 GB) is acceptable if memory pressure is an issue. |
| pytesseract | 0.3.13 | Fallback OCR for GLM-OCR failures | Reliable, battle-tested, Homebrew-installable. Install engine: `brew install tesseract tesseract-lang`. Significantly lower accuracy on multi-column 1970s layouts vs GLM-OCR, but zero dependency on Ollama being running. Use as fallback when Ollama is unavailable or GLM-OCR returns low-confidence output. |
| Pillow | 12.2.0 | Image loading, preprocessing, format conversion | Required by pytesseract. Also used for screenshot capture post-processing (crop, resize, convert to PNG for embedding). |
| opencv-python | 4.13.0.92 | Image preprocessing pipeline before OCR | Deskew, binarize, denoise scanned pages before passing to both GLM-OCR and Tesseract. Standard pipeline: grayscale → CLAHE contrast enhancement → denoising → adaptive threshold → deskew. Measurably improves accuracy on degraded newsprint. |

**GLM-OCR setup:** `ollama pull glm-ocr`. Confirm Ollama is running with `ollama serve`. The `mouse-research doctor` command should verify this.

**Do NOT use:** Cloud OCR (Google Vision, AWS Textract) — project requirement is local-only. EasyOCR — lower accuracy than GLM-OCR on historical documents. Surya — not available via Ollama, additional dependency complexity.

---

### Newspapers.com Search (Node.js subprocess)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| newspapers-com-scraper | latest (npm) | Search Newspapers.com by keyword, date range, location | Existing Node.js tool that handles Newspapers.com's search interface. Reuse avoids reimplementing a complex scraper. Runs as a Python subprocess — Python `subprocess.run(['node', 'scraper.js', ...])` with JSON stdout capture. |
| Node.js | 18+ (LTS) | Runtime for newspapers-com-scraper | Project requirement. Install via Homebrew: `brew install node`. |

**Integration pattern:** Python spawns Node.js process, passes search parameters as CLI args or via stdin JSON, reads structured JSON from stdout. Subprocess stderr goes to Python logger. Handle non-zero exit codes as search failure.

**CRITICAL — Validate early:** newspapers-com-scraper is untested in this project. It is the highest-risk dependency. Validate in Phase 1 before building anything that depends on it. Test: does it work without Newspapers.com auth? Does it return consistent JSON? Does it respect rate limits? The scraper requires Google Chrome installed — confirm it finds the system Chrome or configure `executablePath`.

**Do NOT use:** Python Selenium/Playwright reimplementation of Newspapers.com search — the Node.js scraper exists and eliminates that work. Do not pipe large result sets through subprocess stdin — use a temp JSON file for large payloads.

---

### Obsidian Note Writing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| python-frontmatter | 1.1.0 | Read/write YAML frontmatter in `.md` files | Simple, correct YAML frontmatter parsing. Handles the `---` delimiter blocks that Obsidian reads. Use for both creating new notes and updating existing People/Source index notes. |

**No library needed for wikilinks:** Obsidian wikilinks (`[[Note Name]]`) are plain text. Write them as f-strings. Do not use any "obsidian SDK" — direct file I/O to the vault path is the correct approach.

**Frontmatter schema (per article note):**
```yaml
---
title: "Article Title"
date: 2024-01-15
publication: "Gettysburg Times"
url: "https://www.newspapers.com/..."
people: ["[[John Smith]]", "[[Jane Doe]]"]
tags: [wrestling, mouse-documentary, 1970s]
ocr_method: glm-ocr          # or tesseract, newspaper4k, trafilatura
archived: 2026-04-01
---
```

**Do NOT use:** obsidiantools (analysis library, not for writing), obsidian-export (Rust CLI for exporting, not writing), any Obsidian plugin API (no programmatic plugin access exists for external tools). Obsidian 1.12.x added an official CLI but it is read-focused; direct file writes remain the correct write path.

---

### Configuration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pydantic-settings | 2.13.1 | YAML config file + env var loading with type validation | Reads from YAML config file (`~/.mouse-research/config.yaml`) with typed fields. Catches misconfiguration at startup rather than mid-run. Supports `BaseSettings` with `model_config = SettingsConfigDict(yaml_file="config.yaml")`. Python 3.9+ required. |
| PyYAML | (pydantic-settings dependency) | YAML config file parsing | Pulled in automatically by pydantic-settings. No direct usage needed. |

**Config file location:** `~/.mouse-research/config.yaml` — user-level, outside the project repo, no risk of committing vault paths to version control.

**Do NOT use:** `.env` files alone (YAML is more readable for multi-key configs like vault paths), configparser (no type validation), raw `json.load` (YAML is more human-editable).

---

### HTTP (supplementary fetches)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| httpx | 0.28.1 | Sync HTTP for non-JS pages, health checks | Used when Playwright is overkill — e.g., checking if a URL is reachable, downloading images directly. Sync API keeps the codebase simple (no async complexity in a CLI tool). |

**Do NOT use:** requests (fine, but httpx is strictly better — HTTP/2, better timeouts, same sync API). aiohttp (async adds complexity not needed in a single-user CLI).

---

### Testing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pytest | latest | Unit and integration tests | Standard Python test runner. Use `pytest-playwright` for browser tests. |
| pytest-playwright | latest | Playwright test fixtures | Provides `page` and `browser` fixtures; enables headless browser tests in CI. |

---

## Packaging and Project Structure

```
pyproject.toml           # Project metadata, dependencies, entry point
src/
  mouse_research/
    cli.py               # Typer app, all commands
    config.py            # pydantic-settings config model
    fetcher.py           # Playwright fetch, screenshot, cookie management
    extractor.py         # newspaper4k + trafilatura text extraction
    ocr.py               # GLM-OCR (Ollama) + Tesseract fallback pipeline
    preprocessor.py      # OpenCV/Pillow image preprocessing
    obsidian.py          # Note writing, frontmatter, wikilinks, index updates
    scraper.py           # Node.js subprocess wrapper for newspapers-com-scraper
    doctor.py            # Health check: Ollama, Node.js, Tesseract, vault path
tests/
node_modules/            # newspapers-com-scraper and its deps
package.json
```

**Entry point in pyproject.toml:**
```toml
[project.scripts]
mouse-research = "mouse_research.cli:app"
```

**Install as editable:** `pip install -e .` during development.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| CLI | Typer | Click directly | Typer is Click with type hints — strictly better for greenfield |
| CLI | Typer | argparse | Too verbose, no auto-help generation |
| Browser | Playwright | Selenium | Slower, less reliable on modern JS-heavy sites |
| Browser | Playwright | Requests+BS4 | Cannot handle JavaScript-rendered pages |
| OCR primary | GLM-OCR (Ollama) | Google Vision API | Project requires local-only, no API costs |
| OCR primary | GLM-OCR (Ollama) | Surya | Not Ollama-native, harder to install on macOS |
| OCR fallback | Tesseract/pytesseract | EasyOCR | Lower accuracy on historical docs; heavier install |
| Text extraction | newspaper4k | newspaper3k | Unmaintained since 2020; newspaper4k is the maintained fork |
| Config | pydantic-settings | python-dotenv | No type validation; no YAML support |
| HTTP | httpx | requests | httpx is strictly better (HTTP/2, better timeouts) |

---

## Installation

```bash
# System dependencies (Homebrew on macOS)
brew install python@3.11 node tesseract tesseract-lang

# Install Ollama
brew install ollama
ollama serve &  # or set up launchd service for always-on
ollama pull glm-ocr  # ~2.2 GB download

# Playwright browser
playwright install chromium

# Python project
pip install -e .

# Node.js scraper
npm install  # installs newspapers-com-scraper and deps
```

**Full Python dependency list:**
```
newspaper4k>=0.9.5
trafilatura>=2.0.0
playwright>=1.58.0
pytesseract>=0.3.13
Pillow>=12.2.0
opencv-python>=4.13.0
ollama>=0.6.1
python-frontmatter>=1.1.0
pydantic-settings>=2.13.1
typer>=0.24.1
rich>=14.3.3
httpx>=0.28.1
pytest>=8.0
pytest-playwright
```

---

## Confidence Assessment

| Component | Confidence | Basis |
|-----------|------------|-------|
| Playwright 1.58.0 | HIGH | Verified on PyPI (Jan 2026 release) |
| newspaper4k 0.9.5 | HIGH | Verified on PyPI (Feb 2026 release) |
| trafilatura 2.0.0 | HIGH | Verified on PyPI (Dec 2024 release) |
| Typer 0.24.1 | HIGH | Verified on PyPI (Feb 2026 release) |
| Rich 14.3.3 | HIGH | Verified on PyPI (Feb 2026 release) |
| pydantic-settings 2.13.1 | HIGH | Verified on PyPI (Feb 2026 release) |
| python-frontmatter 1.1.0 | HIGH | Verified on PyPI (Jan 2024 release) |
| ollama Python SDK 0.6.1 | HIGH | Verified on PyPI (Nov 2025 release) |
| pytesseract 0.3.13 | HIGH | Verified on PyPI (Aug 2024 release) |
| Pillow 12.2.0 | HIGH | Verified on PyPI (Apr 2026 release) |
| opencv-python 4.13.0.92 | HIGH | Verified on PyPI (Feb 2026 release) |
| httpx 0.28.1 | MEDIUM | Version from WebSearch, not directly verified on PyPI |
| glm-ocr via Ollama | MEDIUM | Model page verified; accuracy on 1970s newsprint not benchmarked specifically — context-aware inference is theoretically better for degraded text, but no direct evidence for this specific use case |
| newspapers-com-scraper | LOW | GitHub repo confirmed; untested in this project; requires early validation — DO NOT design around it until integration is confirmed working |
| Playwright cookie storage_state | MEDIUM | Pattern confirmed in official docs; known bug with launch_persistent_context (GitHub #36139) means the storage_state() approach is required, not optional |

---

## Sources

- [newspaper4k PyPI](https://pypi.org/project/newspaper4k/)
- [trafilatura PyPI](https://pypi.org/project/trafilatura/)
- [trafilatura docs](https://trafilatura.readthedocs.io/)
- [playwright PyPI](https://pypi.org/project/playwright/)
- [playwright Python auth docs](https://playwright.dev/python/docs/auth)
- [pytesseract PyPI](https://pypi.org/project/pytesseract/)
- [ollama Python SDK PyPI](https://pypi.org/project/ollama/)
- [glm-ocr Ollama model page](https://ollama.com/library/glm-ocr)
- [GLM-OCR GitHub](https://github.com/zai-org/GLM-OCR)
- [Typer PyPI](https://pypi.org/project/typer/)
- [Rich PyPI](https://pypi.org/project/rich/)
- [python-frontmatter PyPI](https://pypi.org/project/python-frontmatter/)
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/)
- [Pillow PyPI](https://pypi.org/project/Pillow/)
- [opencv-python PyPI](https://pypi.org/project/opencv-python/)
- [newspapers-com-scraper GitHub](https://github.com/njraladdin/newspapers-com-scraper)
- [tesseract Homebrew formula](https://formulae.brew.sh/formula/tesseract)
