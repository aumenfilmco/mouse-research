# Phase 2: Single-URL Archive Pipeline - Research

**Researched:** 2026-04-01
**Domain:** Playwright fetching, text extraction (newspaper4k/trafilatura), OpenCV preprocessing, GLM-OCR via Ollama, Obsidian note writing (python-frontmatter)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Article image extraction:** Download full page JPG from Newspapers.com via Playwright (fetching the page image URL, not the Print/Download UI). Store both the full-page image and the cropped article image.
- **Crop before OCR:** Crop to article area before OCR. Resize article crop to 500px max dimension before GLM-OCR.
- **OCR strategy:** GLM-OCR primary (500px max, Ollama HTTP API). Tesseract fallback when Ollama unavailable. OCR queue: save image path to `~/.mouse-research/ocr-queue.jsonl` when neither engine available; archive without OCR text.
- **OpenCV preprocessing:** grayscale → CLAHE contrast → denoise → deskew before OCR.
- **Text source priority:** Newspapers.com → OCR is primary (`## Article Text`). Modern web articles → newspaper4k/trafilatura is primary. When both available → store web extract in `## Web Extract`.
- **Trigger OCR when:** source is Newspapers.com (always), or text extraction returns < 50 chars.
- **Obsidian frontmatter:** `person` as list (`person: ["Dave McCollum"]`). Wikilinks in note body (not frontmatter). Screenshot embedded below title (`![[screenshot.png]]`). Empty `## Notes` section at bottom. Fields: person (list), source (string), date, url, tags (list), captured (date), extraction (method).
- **Duplicate detection:** Match on URL (normalized — strip query params except Newspapers.com image ID). Existing folder with matching URL in metadata.json → print warning and skip.
- **Error handling:** `--file` mode: log failed URL to failures.jsonl, print warning, continue. No extractable text: archive with screenshot + metadata, mark as "no text extracted". Rate limiting: 5-second delay between fetches in `--file` mode.

### Claude's Discretion

- Exact article crop detection logic (how to identify article boundaries on the full page)
- HTML parsing details for extracting Newspapers.com page image URLs
- Slug generation algorithm details
- Internal module structure (single module vs. separate fetcher/extractor/exporter modules)

### Deferred Ideas (OUT OF SCOPE)

- People notes and Source notes auto-linking (Phase 4: Research Graph)
- Master article index generation (Phase 4)
- Batch search and interactive review (Phase 3: Bulk Search)
- Retry failures command (Phase 3)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ARCH-01 | `archive <url>` fetches via headless Playwright with saved cookies, captures article-focused screenshot (2x scale) and raw HTML — for Newspapers.com, extracts clipped article image (not full page) | Playwright `page.screenshot(full_page=True, scale="css")` + `device_scale_factor=2`; cookies via `storage_state`; Newspapers.com image URL extraction via network interception |
| ARCH-02 | Text extraction via newspaper4k (title, author, date, body) with Trafilatura fallback when extraction returns < 50 chars | `article.html = html; article.download_state = ArticleDownloadState.SUCCESS; article.parse()` for newspaper4k; `trafilatura.bare_extraction()` returns Document object |
| ARCH-03 | GLM-OCR via Ollama processes the target article image (not full page) with `[illegible]` markers, Markdown-formatted output | `ollama.generate(model="glm-ocr", prompt=..., images=[b64_bytes])`; response in `.response` field; 500px max dimension enforced |
| ARCH-04 | Tesseract fallback when Ollama/GLM-OCR unavailable; images queued to `~/.mouse-research/ocr-queue.jsonl` if neither available | `pytesseract.image_to_string(img, config="--psm 1")` for full-page; JSONL append pattern for queue |
| ARCH-05 | OCR preprocessing (deskew, CLAHE contrast) for degraded 1970s-80s scans before GLM-OCR | Verified pipeline: `cvtColor → createCLAHE → fastNlMeansDenoising → minAreaRect deskew → Pillow resize` |
| ARCH-06 | Auto-detect newspaper source from URL domain | Domain-to-name mapping dict; Newspapers.com → parse publication name from page HTML JSON blob |
| ARCH-07 | Auto-detect article date from metadata, URL patterns, or OCR output | newspaper4k `article.publish_date`; trafilatura `document.date`; URL date patterns; regex fallback on OCR text |
| ARCH-08 | Generate article folder with slug `YYYY-MM-DD_source-slug_title-slug` containing screenshot, page_image, article.md, ocr_raw.md, metadata.json, source.html | `slugify` pattern; `pathlib.Path.mkdir(parents=True, exist_ok=True)` |
| ARCH-09 | Article note as Obsidian-formatted Markdown with YAML frontmatter (person, source, date, url, tags), wikilinks, embedded screenshot | `frontmatter.Post(body, **metadata)` + `frontmatter.dumps(post)` — verified produces correct YAML |
| ARCH-10 | `mouse-research ocr <image-path>` OCRs local image with `--person`, `--date`, `--source` flags, exports to vault | Reuses OCR + Obsidian export pipeline; skips Playwright fetch step |
| ARCH-11 | `mouse-research archive --file urls.txt` archives multiple URLs sequentially | Typer `--file` option; sequential loop with 5s `time.sleep()` between fetches; failures.jsonl logging |
</phase_requirements>

---

## Summary

Phase 2 implements the core `mouse-research archive <url>` pipeline. The five-step flow (Fetch → Extract → OCR → Metadata → Export) is well-defined by the PRD and CONTEXT.md decisions. The primary technical challenge is the Newspapers.com-specific path: extracting the full newspaper page JPG from the viewer page, cropping to the specific article area, and feeding that crop into GLM-OCR at ≤500px. For modern web articles the path is simpler: newspaper4k/trafilatura extract text directly from the page HTML.

All core library APIs have been verified against the live `.venv` installation. One missing dependency was found: `lxml-html-clean` is not installed but is required by both newspaper4k and trafilatura — this must be added to `pyproject.toml` as an explicit dependency and installed in Wave 0. Everything else (Playwright 1.58.0, OpenCV 4.13.0, Pillow 12.2.0, pytesseract + Tesseract 5.5.2, ollama SDK 0.6.1, python-frontmatter 1.1.0) is installed and functional.

The Newspapers.com image URL discovery approach relies on Playwright network interception: when the viewer page loads, it fetches a full-resolution newspaper page image from `img.newspapers.com`. By listening to `page.on("response")` for responses matching `img.newspapers.com`, the pipeline can capture the direct JPG URL and download it via `httpx`. The page HTML also contains a JSON blob with OCR text, publication name, date, and page number — parseable via `json.loads()` on the embedded `<script>` tags. Article crop boundaries are left to Claude's discretion (per CONTEXT.md) — the recommended approach is a semi-automatic bounding box: use Playwright's `page.evaluate()` to extract highlighted article region coordinates from the DOM, or fall back to a center-weighted crop that covers 70% of the page height.

**Primary recommendation:** Build six modules — `fetcher.py`, `extractor.py`, `ocr.py`, `preprocessor.py`, `obsidian.py`, `archiver.py` — with typed dataclasses flowing between them. Add `archive` and `ocr` commands to `cli.py`.

---

## Standard Stack

### Core (all verified installed in .venv)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| playwright (Python) | 1.58.0 | Authenticated page fetch, screenshot, network interception | Already used in Phase 1; `channel="chrome"` required on macOS |
| newspaper4k | 0.9.5 | Primary HTML text extraction | Handles article title, authors, publish_date, body in one call |
| trafilatura | 2.0.0 | Fallback text extraction | Returns `Document` object with `.title`, `.text`, `.date`, `.author` |
| lxml-html-clean | 0.4.4 | Required by newspaper4k + trafilatura | Separated from lxml in Python 3.14+ ecosystem; MUST be added to pyproject.toml |
| opencv-python | 4.13.0.92 | Image preprocessing pipeline | Verified: grayscale, CLAHE, denoise, deskew all working |
| Pillow | 12.2.0 | Image loading, resize, base64 conversion | Required for 500px resize before GLM-OCR |
| ollama | 0.6.1 | GLM-OCR via Ollama HTTP API | `ollama.generate(model="glm-ocr", images=[...])` — response in `.response` |
| pytesseract | 0.3.13 | Tesseract fallback OCR | Verified: Tesseract 5.5.2 installed, `get_tesseract_version()` works |
| python-frontmatter | 1.1.0 | Obsidian note YAML frontmatter writing | `frontmatter.Post(body, **meta)` + `frontmatter.dumps()` — verified output |
| httpx | 0.27.0+ | Direct image download from img.newspapers.com | Sync HTTP; already in pyproject.toml |

### Missing Dependency (Wave 0 install required)

```bash
# Add to pyproject.toml dependencies and install:
.venv/bin/pip install lxml-html-clean
```

Both newspaper4k and trafilatura fail to import without it:
- newspaper4k raises: `ModuleNotFoundError: No module named 'lxml_html_clean'`
- trafilatura raises: `ImportError: lxml.html.clean module is now a separate project lxml_html_clean`

**Add to pyproject.toml:**
```toml
"lxml-html-clean>=0.4.4",
```

---

## Architecture Patterns

### Recommended Module Structure

```
src/mouse_research/
├── cli.py           # Add: archive(), ocr() Typer commands
├── archiver.py      # Orchestrates the 5-step pipeline for single URL
├── fetcher.py       # Playwright fetch, screenshot, image URL extraction
├── extractor.py     # newspaper4k + trafilatura text extraction
├── preprocessor.py  # OpenCV pipeline: grayscale → CLAHE → denoise → deskew → resize
├── ocr.py           # GLM-OCR (Ollama) + Tesseract fallback + queue
├── obsidian.py      # Note writing, frontmatter, folder creation
├── config.py        # (existing) AppConfig
├── cookies.py       # (existing) Cookie management
├── logger.py        # (existing) Logging
└── installer.py     # (existing) MOUSE_DIR constant
```

### Pattern 1: Typed Dataclasses Between Pipeline Stages

Pass typed dataclasses between pipeline stages — no shared mutable globals.

```python
# Source: ARCHITECTURE.md + verified against project conventions
from dataclasses import dataclass, field
from pathlib import Path
from datetime import date
from typing import Optional

@dataclass
class FetchResult:
    url: str
    html: str
    screenshot_path: Path
    page_image_path: Optional[Path]   # Newspapers.com full-page JPG (if extracted)
    article_image_path: Optional[Path] # Cropped + resized article image
    is_newspapers_com: bool

@dataclass
class ArticleData:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    publish_date: Optional[date] = None
    text: str = ""
    extraction_method: str = "none"   # newspaper4k | trafilatura | none

@dataclass
class OcrResult:
    text: str = ""
    engine: str = "none"              # glm-ocr | tesseract | queued | none
    queued: bool = False

@dataclass
class ArticleRecord:
    slug: str
    url: str
    source_name: str
    article_data: ArticleData
    ocr_result: OcrResult
    screenshot_path: Path
    page_image_path: Optional[Path]
    article_image_path: Optional[Path]
    person: list[str]
    tags: list[str]
    captured: date
```

### Pattern 2: newspaper4k with Pre-Fetched HTML (verified)

newspaper4k's `parse()` uses `self.html` directly. Inject pre-fetched Playwright HTML:

```python
# Source: verified via .venv inspection
from newspaper import Article
from newspaper.article import ArticleDownloadState

def extract_with_newspaper4k(url: str, html: str) -> ArticleData:
    article = Article(url)
    article.html = html
    article.download_state = ArticleDownloadState.SUCCESS
    article.parse()
    return ArticleData(
        title=article.title or "",
        authors=article.authors or [],
        publish_date=article.publish_date,
        text=article.text or "",
        extraction_method="newspaper4k",
    )
```

Key note: `article.title` uses the `<title>` tag if no better title found. For Newspapers.com viewer pages, this returns the newspaper name, not the article headline — use OCR text as the title source instead.

### Pattern 3: trafilatura bare_extraction with Pre-Fetched HTML (verified)

`bare_extraction()` returns a `Document` object (not a dict):

```python
# Source: verified via .venv inspection
import trafilatura

def extract_with_trafilatura(html: str) -> ArticleData:
    doc = trafilatura.bare_extraction(
        html,
        include_comments=False,
        include_tables=False,
        with_metadata=True,
    )
    if doc is None:
        return ArticleData()
    return ArticleData(
        title=doc.title or "",
        authors=[doc.author] if doc.author else [],
        publish_date=_parse_date(doc.date),
        text=doc.text or "",
        extraction_method="trafilatura",
    )
```

### Pattern 4: Playwright Fetch with Network Interception for Newspapers.com

The Newspapers.com viewer loads a full-resolution newspaper page JPG from `img.newspapers.com`. Intercept with `page.on("response")` to capture the URL, then download via httpx.

```python
# Source: Playwright network docs (HIGH confidence) + Wikipedia talk page research
from playwright.sync_api import sync_playwright, Response
import httpx

def fetch_newspapers_com(url: str, storage_state: str) -> FetchResult:
    page_image_url = None

    def capture_image_response(response: Response):
        nonlocal page_image_url
        if "img.newspapers.com" in response.url and response.status == 200:
            content_type = response.headers.get("content-type", "")
            if "image" in content_type:
                page_image_url = response.url

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(
            storage_state=storage_state,
            device_scale_factor=2,
        )
        page = context.new_page()
        page.on("response", capture_image_response)
        page.goto(url, wait_until="networkidle", timeout=30000)

        html = page.content()
        screenshot_bytes = page.screenshot(full_page=True)
        # ... save screenshot, download page_image_url via httpx
        browser.close()
```

**IMPORTANT:** `channel="chrome"` is required on macOS (Phase 1 finding). Playwright Chromium headless fails with ValidationError 54.

**Fallback if network interception misses the image:** The page HTML contains embedded JSON with publication metadata. Search for `window.__PRELOADED_STATE__` or `<script type="application/json">` tags. The image ID is in the URL itself (`/image/46677507`) and the full JPG can be constructed as:
`https://img.newspapers.com/img/img?id={image_id}&width=2000` (MEDIUM confidence — from Wikipedia talk page research; exact parameter names need live verification).

### Pattern 5: OpenCV Preprocessing Pipeline (verified)

```python
# Source: verified via .venv execution
import cv2
import numpy as np
from PIL import Image
import io, base64

def preprocess_for_ocr(image_path: Path, max_dim: int = 500) -> bytes:
    """Full preprocessing pipeline. Returns base64-encoded PNG bytes for Ollama."""
    img = cv2.imread(str(image_path))

    # 1. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. CLAHE contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 3. Denoise
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10,
                                         templateWindowSize=7,
                                         searchWindowSize=21)

    # 4. Deskew using minAreaRect
    coords = np.column_stack(np.where(denoised > 0))
    if len(coords) > 10:
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        (h, w) = denoised.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        denoised = cv2.warpAffine(denoised, M, (w, h),
                                   flags=cv2.INTER_CUBIC,
                                   borderMode=cv2.BORDER_REPLICATE)

    # 5. Resize to max_dim (500px for GLM-OCR)
    pil_img = Image.fromarray(denoised)
    w, h = pil_img.size
    scale = max_dim / max(w, h)
    if scale < 1.0:
        pil_img = pil_img.resize(
            (int(w * scale), int(h * scale)),
            Image.Resampling.LANCZOS,
        )

    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()
```

### Pattern 6: GLM-OCR via Ollama (verified API)

```python
# Source: verified via .venv inspection — ollama.GenerateResponse.model_fields
import ollama

OCR_PROMPT = (
    "Extract all text from this newspaper article image. "
    "Preserve headlines, subheadlines, bylines, and body text. "
    "Output as clean Markdown. "
    "If text is illegible, mark it as [illegible]. "
    "Do not guess or fabricate text that cannot be read."
)

def ocr_with_glm(image_bytes: bytes, ollama_url: str = "http://localhost:11434") -> str:
    client = ollama.Client(host=ollama_url)
    response = client.generate(
        model="glm-ocr",
        prompt=OCR_PROMPT,
        images=[image_bytes],   # bytes accepted directly (no manual base64)
    )
    return response.response   # GenerateResponse.response field (verified)
```

**Key fields of `ollama.GenerateResponse`:** `model`, `response` (the text output), `done`, `done_reason`, `total_duration`, `eval_count`. The text output is in `.response`.

### Pattern 7: python-frontmatter Note Writing (verified)

```python
# Source: verified via .venv execution — exact output format confirmed
import frontmatter
from pathlib import Path
from datetime import date

def write_article_note(folder: Path, record: ArticleRecord) -> Path:
    # Determine primary text
    if record.ocr_result.text:
        primary_text = record.ocr_result.text
        section = "## Article Text"
    else:
        primary_text = record.article_data.text
        section = "## Article Text"

    body_parts = [
        f"# {record.article_data.title or 'Untitled'}",
        "",
        "![[screenshot.png]]",
        "",
        section,
        "",
        primary_text or "_No text extracted._",
    ]

    # Web extract secondary section (if both OCR and web extraction succeeded)
    if record.ocr_result.text and record.article_data.text:
        body_parts += ["", "## Web Extract", "", record.article_data.text]

    body_parts += ["", "## Notes", ""]
    body = "\n".join(body_parts)

    post = frontmatter.Post(
        body,
        person=record.person,                          # list format
        source=record.source_name,
        date=record.article_data.publish_date,
        url=record.url,
        tags=record.tags,
        captured=record.captured,
        extraction=record.ocr_result.engine or record.article_data.extraction_method,
    )

    note_path = folder / "article.md"
    note_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return note_path
```

**Confirmed frontmatter output format:**
```yaml
---
captured: 2026-04-01
date: 1986-03-15
extraction: glm-ocr
person:
- Dave McCollum
source: Gettysburg Times
tags:
- wrestling
- state-championship
url: https://www.newspapers.com/image/12345678/
---
```
Keys are sorted alphabetically by python-frontmatter's YAML dumper. Obsidian reads this correctly.

### Pattern 8: Slug Generation

```python
import re
from datetime import date

def make_slug(pub_date: date | None, source_name: str, title: str) -> str:
    date_str = pub_date.strftime("%Y-%m-%d") if pub_date else "undated"
    source_slug = re.sub(r"[^a-z0-9]+", "-", source_name.lower()).strip("-")[:30]
    title_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    return f"{date_str}_{source_slug}_{title_slug}"
```

### Pattern 9: Duplicate Detection

```python
import json

def is_duplicate(vault_articles_dir: Path, url: str) -> bool:
    """Check if URL (normalized) already exists in any article folder."""
    normalized = _normalize_url(url)
    for meta_file in vault_articles_dir.glob("*/metadata.json"):
        try:
            meta = json.loads(meta_file.read_text())
            if _normalize_url(meta.get("url", "")) == normalized:
                return True
        except (json.JSONDecodeError, OSError):
            continue
    return False

def _normalize_url(url: str) -> str:
    """Strip query params except Newspapers.com image ID (the path itself)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    # For newspapers.com/image/12345678 — the ID is in the path, not query params
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
```

### Pattern 10: OCR Queue

```python
import json
from datetime import datetime

MOUSE_DIR = Path.home() / ".mouse-research"
OCR_QUEUE_PATH = MOUSE_DIR / "ocr-queue.jsonl"

def enqueue_for_ocr(image_path: Path, url: str, article_dir: Path) -> None:
    """Add image to OCR queue when neither Ollama nor Tesseract is available."""
    MOUSE_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "image_path": str(image_path),
        "url": url,
        "article_dir": str(article_dir),
        "queued_at": datetime.now().isoformat(),
    }
    with OCR_QUEUE_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")
```

### Pattern 11: Article Crop Strategy (Claude's Discretion)

Per CONTEXT.md, the exact crop logic is at Claude's discretion. Two approaches are available:

**Option A — DOM coordinate extraction (recommended):** Newspapers.com's viewer highlights the article region with a bounding box in the DOM. Use `page.evaluate()` after page load to extract the highlighted element's bounding rect, map to the full-page image coordinates, and crop with Pillow.

```python
# Extract article bounding box from viewer DOM
bbox = page.evaluate("""() => {
    const el = document.querySelector('.clip-region') 
             || document.querySelector('[class*="article"]')
             || document.querySelector('[class*="clip"]');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: r.x, y: r.y, width: r.width, height: r.height};
}""")
```

The exact CSS selector for the Newspapers.com article highlight region is **unknown** (MEDIUM confidence) — requires live testing against the actual viewer DOM. Plan should include a task that inspects the live viewer DOM before implementing crop logic.

**Option B — Center-crop fallback:** If DOM extraction fails, crop center 80% width × 60% height of the full page image. Less precise but always produces a cropped image smaller than full-page, which avoids GLM-OCR GGML crashes.

```python
from PIL import Image

def center_crop(img: Image.Image, width_pct=0.8, height_pct=0.6) -> Image.Image:
    w, h = img.size
    left = int(w * (1 - width_pct) / 2)
    top = int(h * (1 - height_pct) / 2)
    right = w - left
    bottom = top + int(h * height_pct)
    return img.crop((left, top, right, bottom))
```

**Recommendation:** Implement Option A with Option B as fallback. Add a `--crop-box "x,y,w,h"` CLI override flag for manual crop specification on problematic pages.

### Anti-Patterns to Avoid

- **Fat CLI commands:** `archive()` in cli.py must delegate to `archiver.archive_url(url, config)`. No business logic in CLI functions.
- **OCR on modern HTML articles:** Only OCR when source is Newspapers.com or text extraction returns < 50 chars. GLM-OCR takes ~1.5s/image — wasted on digital text.
- **Passing full-page images to GLM-OCR:** Phase 1 validated this causes GGML assertion crashes AND hallucinations. Always crop and resize to ≤500px first.
- **Using `article.set_html()`:** Does not exist in newspaper4k. Use `article.html = html; article.download_state = ArticleDownloadState.SUCCESS`.
- **Using `trafilatura.bare_extraction()` result as dict:** Returns `Document` object. Access via attributes (`.title`, `.text`, `.date`, `.author`), not `result["title"]`.
- **Using `frontmatter.dump(post, file_handle)`:** Requires binary file handle — error-prone. Use `frontmatter.dumps(post)` (returns string) then `path.write_text(result)`.
- **Overwriting existing article folders:** Duplicate check must run before any file I/O.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML frontmatter for Obsidian | Custom string templating | python-frontmatter | Handles delimiter escaping, YAML type serialization (dates, lists) correctly |
| HTML article extraction | Custom BeautifulSoup scraper | newspaper4k + trafilatura | Both handle nav/ad stripping, byline detection, date extraction from dozens of site patterns |
| Image deskew | Custom rotation detection | OpenCV `minAreaRect` | Correct Hough-based approach; hand-rolled angle detection is unreliable |
| Network request monitoring | Polling page source | Playwright `page.on("response")` | Event-driven, zero polling overhead, captures exact URLs |
| Slug sanitization | Custom regex | `re.sub(r"[^a-z0-9]+", "-", s.lower())` | Simple and sufficient; no third-party needed |

---

## Common Pitfalls

### Pitfall 1: lxml-html-clean Not Installed
**What goes wrong:** `from newspaper import Article` and `import trafilatura` both raise ImportError at module load time. Neither library works.
**Why it happens:** `lxml_html_clean` was separated from lxml in 2023; it is not a transitive dependency of newspaper4k or trafilatura on PyPI — must be declared explicitly.
**How to avoid:** Add `lxml-html-clean>=0.4.4` to `pyproject.toml` dependencies. Install in Wave 0.
**Warning signs:** `ModuleNotFoundError: No module named 'lxml_html_clean'` on any import of newspaper4k or trafilatura.

### Pitfall 2: GLM-OCR GGML Crash on Large Images
**What goes wrong:** Ollama 0.19.0 (installed) crashes with `GGML_ASSERT([rsets->data count] == 0) failed` for images above ~500px max dimension. The crash is also state-corrupting — subsequent calls to GLM-OCR fail even with smaller images until Ollama is restarted.
**Why it happens:** Known llama.cpp bug (tracked at github.com/ggml-org/llama.cpp/pull/17869). Not fixed in Ollama 0.19.0.
**How to avoid:** Always resize to ≤500px max dimension before calling GLM-OCR. In `preprocessor.py`, enforce this as a hard limit.
**Warning signs:** `GGML_ASSERT` in Ollama server logs; subsequent OCR calls return empty responses.

### Pitfall 3: Playwright `channel="chrome"` Required on macOS
**What goes wrong:** `p.chromium.launch(headless=True)` fails on macOS with ValidationError 54.
**Why it happens:** Playwright's bundled Chromium has macOS launch issues (Phase 1 validated). System Chrome works correctly.
**How to avoid:** Always use `p.chromium.launch(headless=True, channel="chrome")` in all Playwright code. This is already in `cookies.py` for `interactive_login()` but must also be in `fetcher.py`.
**Warning signs:** `playwright._impl._errors.Error: Browser closed unexpectedly` or ValidationError 54.

### Pitfall 4: Newspapers.com Image URL Not Captured by Network Interception
**What goes wrong:** The `page.on("response")` handler misses the image load because the image was loaded from browser cache (second visit to same page) or the request completed before the handler was registered.
**Why it happens:** `page.on("response")` only captures new requests, not cached responses.
**How to avoid:** Register the handler before `page.goto()`. Disable browser cache via `browser.new_context(... no-cache headers)` or `page.route("**/*", lambda r: r.continue_())`. As fallback, parse the image ID from the URL path (`/image/46677507`) and construct the download URL directly.
**Warning signs:** `page_image_url` is still `None` after `page.goto()` completes.

### Pitfall 5: newspaper4k Title from `<title>` Tag on Newspapers.com
**What goes wrong:** For Newspapers.com viewer pages, `article.title` returns the newspaper name (e.g., "The Gettysburg Times") rather than the article headline, because the page title tag contains the publication name.
**Why it happens:** newspaper4k falls back to the HTML `<title>` tag when no article headline is found in the content body. Newspapers.com viewer pages are image-based, not text-based.
**How to avoid:** For Newspapers.com sources, use the OCR output's first non-empty line as the title. Use `article.title` only as a last resort for non-Newspapers.com sources.

### Pitfall 6: article.publish_date Returns None for Most Sources
**What goes wrong:** `article.publish_date` is `None` for most articles, including Newspapers.com pages.
**Why it happens:** Date is embedded in the page as structured data only on modern CMS-based sites. Older and scanned-paper sites don't have `<meta>` date tags.
**How to avoid:** Implement a date resolution cascade: (1) newspaper4k `publish_date`, (2) trafilatura `doc.date`, (3) URL date pattern regex (`/(\d{4})/(\d{2})/(\d{2})/`), (4) Newspapers.com JSON blob in page source, (5) user-provided `--date` flag, (6) `None` with frontmatter `date: null`.

### Pitfall 7: Vault Path Contains Spaces
**What goes wrong:** `/Users/aumen-server/Documents/Obsidian Vault/...` contains a space. Shell operations on this path fail if not quoted; Python `Path` operations work correctly but subprocess calls need `str(path)` quoting.
**Why it happens:** Default vault path has a space in "Obsidian Vault".
**How to avoid:** Use `pathlib.Path` for all file operations (handles spaces transparently). Never construct vault paths via string concatenation.

---

## Code Examples

### Full Archive Pipeline Orchestration

```python
# archiver.py — thin orchestrator, delegates to modules
from pathlib import Path
from datetime import date
import time

from mouse_research.config import AppConfig
from mouse_research.fetcher import fetch_page, is_newspapers_com
from mouse_research.extractor import extract_text
from mouse_research.preprocessor import preprocess_for_ocr
from mouse_research.ocr import run_ocr
from mouse_research.obsidian import write_article_folder
from mouse_research.logger import log_failure, get_logger

def archive_url(
    url: str,
    config: AppConfig,
    person: list[str],
    tags: list[str],
) -> Path | None:
    logger = get_logger(__name__)

    # Duplicate check
    vault_articles = Path(config.vault.path) / "Articles"
    if is_duplicate(vault_articles, url):
        logger.warning(f"Duplicate URL skipped: {url}")
        return None

    try:
        fetch_result = fetch_page(url, config)
        article_data = extract_text(fetch_result.html, url)

        # OCR decision
        should_ocr = fetch_result.is_newspapers_com or len(article_data.text) < 50
        ocr_result = run_ocr(fetch_result.article_image_path, config) if should_ocr else OcrResult()

        record = build_article_record(url, fetch_result, article_data, ocr_result, person, tags)
        return write_article_folder(vault_articles, record)

    except Exception as e:
        log_failure(url, str(e), phase="archive")
        return None
```

### CLI Command Additions (cli.py)

```python
# Add to existing cli.py
from typing import Optional
import typer
from pathlib import Path

@app.command()
def archive(
    url: Optional[str] = typer.Argument(None, help="URL to archive"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="File of URLs (one per line)"),
    person: list[str] = typer.Option([], "--person", "-p", help="Person name(s)"),
    tags: list[str] = typer.Option([], "--tags", "-t", help="Tags"),
):
    """Archive a newspaper article to the Obsidian vault."""
    from mouse_research.archiver import archive_url
    from mouse_research.config import get_config
    import time

    cfg = get_config()

    if file:
        urls = [line.strip() for line in file.read_text().splitlines() if line.strip()]
        for i, u in enumerate(urls):
            if i > 0:
                time.sleep(cfg.rate_limit_seconds)
            archive_url(u, cfg, person, tags)
    elif url:
        archive_url(url, cfg, person, tags)
    else:
        console.print("[red]Provide a URL or --file[/red]")
        raise typer.Exit(1)


@app.command()
def ocr(
    image_path: Path = typer.Argument(..., help="Local image path to OCR"),
    person: list[str] = typer.Option([], "--person", "-p"),
    date_str: Optional[str] = typer.Option(None, "--date", "-d", help="YYYY-MM-DD"),
    source: Optional[str] = typer.Option(None, "--source", "-s"),
):
    """OCR a local newspaper scan and export to vault."""
    from mouse_research.archiver import archive_local_image
    from mouse_research.config import get_config
    cfg = get_config()
    archive_local_image(image_path, cfg, person=person, date_str=date_str, source=source)
```

---

## Newspapers.com Image URL Structure

**Confirmed from scraper source and Wikipedia talk page research (MEDIUM confidence — needs live verification):**

| Component | Value | Notes |
|-----------|-------|-------|
| Viewer URL | `https://www.newspapers.com/image/{pageId}` | pageId is a numeric integer |
| Image API | `https://img.newspapers.com/img/img?id={pageId}&width=2000` | Full-res download; exact params need live verification |
| Clipping API | `https://img.newspapers.com/img/img?clippingId={clippingId}` | For pre-clipped articles |
| Page HTML JSON | `window.__PRELOADED_STATE__` or `<script type="application/json">` | Contains title, date, page number, publication name |
| Embedded OCR text | JSON blob in page source: `"text":` key | Pre-extracted OCR text from Newspapers.com's own OCR |

**The image ID in the scraper output URL** (`https://www.newspapers.com/image/46677507?terms=...`) is the same `pageId` — it's in the URL path. Strip the query string to get the canonical URL.

**Critical unknown requiring live testing:** The exact URL format for downloading the full-resolution newspaper page JPG. The `img.newspapers.com` domain serves images but exact parameters (width, quality, format) need verification against a live authenticated session. **The plan must include a validation task for this before implementing the image download step.**

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python .venv | All modules | ✓ | 3.14.3 | — |
| playwright | ARCH-01 | ✓ | 1.58.0 | — |
| Google Chrome | Playwright `channel="chrome"` | ✓ | System install | — |
| newspaper4k | ARCH-02 | ✓ (needs lxml-html-clean) | 0.9.5 | trafilatura |
| trafilatura | ARCH-02 fallback | ✓ (needs lxml-html-clean) | 2.0.0 | — |
| lxml-html-clean | newspaper4k + trafilatura | ✗ NOT INSTALLED | — | Must install Wave 0 |
| opencv-python | ARCH-05 | ✓ | 4.13.0.92 | — |
| Pillow | ARCH-01, ARCH-05 | ✓ | 12.2.0 | — |
| ollama SDK | ARCH-03 | ✓ | 0.6.1 | — |
| Ollama service | ARCH-03 | ✓ | 0.19.0 | Tesseract fallback |
| glm-ocr model | ARCH-03 | ✓ | latest (2.2 GB) | — |
| pytesseract | ARCH-04 | ✓ | 0.3.13 | — |
| Tesseract engine | ARCH-04 | ✓ | 5.5.2 | OCR queue |
| python-frontmatter | ARCH-09 | ✓ | 1.1.0 | — |
| httpx | Image download | ✓ | 0.27.0+ | — |
| Obsidian vault | Output | ✓ | at configured path | — |

**Missing dependencies with no fallback:**
- `lxml-html-clean` — blocks newspaper4k and trafilatura imports entirely. **Must be installed in Wave 0 and added to pyproject.toml.**

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `newspaper3k` | `newspaper4k` | 2023 | newspaper3k unmaintained; use newspaper4k fork |
| `lxml.html.clean` (built-in) | `lxml-html-clean` (separate package) | 2023 | Must explicitly install; affects newspaper4k and trafilatura |
| `frontmatter.dump(post, fd)` requires binary fd | `frontmatter.dumps(post)` returns string | Stable | Use `dumps()` + `path.write_text()` |
| `trafilatura.extract()` returns string | `trafilatura.bare_extraction()` returns `Document` object | Stable | Access via `.title`, `.text`, `.date` attributes — not dict keys |
| `launch_persistent_context()` for cookies | `storage_state()` save/load | Phase 1 finding | Bug #36139 — persistent context doesn't persist session cookies |

---

## Open Questions

1. **Exact img.newspapers.com URL parameters for full-resolution JPG download**
   - What we know: Image ID is the numeric value in `/image/46677507`. Domain is `img.newspapers.com`. Page HTML contains publication metadata.
   - What's unclear: Exact URL format — `?id=` vs `?imageId=` vs path-based; whether auth cookies are required for image download; maximum width parameter value.
   - Recommendation: First task of Wave 1 should open a live Newspapers.com page with Playwright DevTools-equivalent network logging and capture the actual image request URL. Document the finding before implementing.

2. **Newspapers.com viewer DOM structure for article highlight/crop bounding box**
   - What we know: The viewer renders a highlighted region around the searched article. This region's coordinates could be used for automatic cropping.
   - What's unclear: CSS class names for the highlight element; whether the element exists in headless mode; whether coordinates map 1:1 to the full-page image coordinates.
   - Recommendation: Include a DOM inspection task in Wave 1. If the highlight element is not present in headless mode, fall back to the center-crop approach.

3. **Newspapers.com page HTML JSON blob structure**
   - What we know: The page source contains a JSON blob with publication metadata including title, date, location, page number.
   - What's unclear: The exact script tag or JS variable name (`window.__PRELOADED_STATE__` is a guess based on common SPA patterns).
   - Recommendation: Capture page source during the image URL discovery task and parse it to confirm structure.

---

## Project Constraints (from CLAUDE.md)

- **Language:** Python 3.11+ for all CLI and pipeline code. No new Node.js code (Node.js only for existing scraper subprocess in Phase 3).
- **OCR engines:** GLM-OCR via Ollama (primary), Tesseract (fallback) — local only, no cloud APIs.
- **Virtual environment:** `.venv/bin/python3` — macOS Python 3.14 is externally-managed (PEP 668). All installs via `.venv/bin/pip`.
- **Rate limiting:** 5-second delays between fetches in `--file` mode.
- **Dependencies:** All installable via Homebrew (system) or pip (Python). No exotic build requirements.
- **GSD workflow:** All changes must go through GSD execute-phase workflow.

---

## Sources

### Primary (HIGH confidence)
- `.venv` live inspection — all library APIs verified by execution (newspaper4k, trafilatura, cv2, Pillow, ollama, python-frontmatter, pytesseract)
- `~/.mouse-research/node_modules/newspapers-com-scraper/lib/NewspaperScraper.js` — scraper source, confirmed `article.page.viewerUrl` = `https://www.newspapers.com/image/{pageId}`
- `.planning/phases/01-foundation-validation/01-05-SUMMARY.md` — Phase 1 findings (GLM-OCR 500px limit, channel="chrome" requirement, CER <5% on crops)
- `validation/ocr-test.md` — GLM-OCR benchmark results
- Playwright Python network docs — `page.on("response")` interception pattern

### Secondary (MEDIUM confidence)
- Wikipedia talk:Newspapers.com — image URL format `https://img.newspapers.com/img/img?clippingId=...`, embedded OCR text in page source
- `.planning/phases/02-single-url-archive-pipeline/02-CONTEXT.md` — all locked decisions
- `mouse-research-pipeline-prd.md` — PRD Sections 4.2 (pipeline steps), data model

### Tertiary (LOW confidence — needs live verification)
- `https://img.newspapers.com/img/img?id={pageId}&width=2000` — inferred image URL format; exact parameters unverified
- Newspapers.com viewer DOM structure for article highlight bounding box — class names and coordinate mapping unverified

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified in .venv, all APIs tested via execution
- Architecture: HIGH — dataclass patterns, module boundaries, OCR routing all verified
- Newspapers.com image URL: MEDIUM — pageId structure confirmed; exact download URL parameters require live testing
- Article crop detection: LOW — DOM selector names are unknown; needs live viewer inspection
- Pitfalls: HIGH — all critical pitfalls either observed in Phase 1 or verified via code inspection

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable libraries; Newspapers.com frontend may change)
