# MOUSE Research Pipeline — Product Requirements Document

**Project:** MOUSE: 50 Years on the Mat  
**Author:** Chris Aumen / Aumen Film Co.  
**Version:** 1.0  
**Date:** April 1, 2026  
**Build Tool:** Claude Code  
**Runtime Environment:** Mac Mini (Apple Silicon), always-on, studio machine

---

## 1. Purpose

Build a CLI-driven newspaper research pipeline that runs on Chris's Mac Mini. The tool searches for articles about people and events related to the MOUSE documentary, downloads them as images, extracts text via OCR, and deposits organized research files directly into the project's Obsidian vault. One command, one language interface (Python), everything lands in the right folder.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        MOUSE RESEARCH CLI                       │
│                     `mouse-research <command>`                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: URL-In Pipeline            Phase 2: Bulk Discovery    │
│  ────────────────────────            ───────────────────────    │
│  User provides a URL →               Search query →             │
│  Playwright fetches page →            newspapers-com-scraper →   │
│  Screenshot + HTML saved →            JSON results →             │
│  newspaper4k extracts text →          Python orchestrator →      │
│  GLM-OCR on images/scans →           Feeds URLs into Phase 1    │
│  Trafilatura fallback →                                         │
│  Obsidian export →                                              │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                      OBSIDIAN VAULT                              │
│  /Users/aumen-server/Documents/Obsidian Vault/                  │
│    01-Aumen-Film-Co/Projects/MOUSE/Research/                    │
│      Articles/                                                  │
│      People/                                                    │
│      Sources/                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. System Requirements

### Hardware
- **Machine:** Mac Mini with Apple Silicon (M1/M2/M4)
- **RAM:** 8 GB minimum (16 GB recommended for GLM-OCR + Playwright concurrent use)
- **Disk:** ~5 GB for tooling (GLM-OCR model ~2 GB, Playwright browsers ~500 MB, Node.js deps ~200 MB, Python deps ~2 GB)

### Software Prerequisites
- **Python 3.11+** (via Homebrew or system)
- **Node.js 18+** (via Homebrew or nvm)
- **Ollama** (for GLM-OCR model serving)
- **Google Chrome** (for newspapers-com-scraper's Puppeteer dependency)
- **Obsidian** (already installed, vault at known path)

### Accounts Required
- **Newspapers.com** — Publisher Extra subscription (Chris has this)
- Optionally: LancasterOnline, York Daily Record digital subscriptions for current articles

---

## 4. Phase 1: URL-In Pipeline

### 4.1 Command Interface

```bash
# Archive a single article
mouse-research archive <url> --person "Dave McCollum" --tags "wrestling,state-championship"

# Archive multiple URLs from a file (one per line)
mouse-research archive --file urls.txt --person "Trevor Byers"

# Archive a local image (newspaper scan, photo of clipping)
mouse-research ocr <image-path> --person "Dave McCollum" --date "1986-03-15" --source "Gettysburg Times"

# Open the research index
mouse-research index
```

### 4.2 Pipeline Steps (per URL)

**Step 1 — Fetch & Screenshot (Playwright)**
- Launch headless Chromium with saved authentication cookies
- Navigate to URL, wait for full page load (network idle)
- Capture full-page screenshot as PNG (high-res, 2x device scale)
- Save raw HTML to disk
- If the URL is a Newspapers.com image viewer page: extract the newspaper page image directly (higher quality than screenshot)
- Timeout: 30 seconds per page, retry once on failure

**Step 2 — Text Extraction (newspaper4k + Trafilatura fallback)**
- Pass raw HTML to newspaper4k for structured extraction:
  - Article title
  - Author(s)
  - Publish date
  - Full article text
  - Top image URL
- If newspaper4k returns empty/partial text (< 50 characters), fall back to Trafilatura
- If both extractors fail (e.g., it's a scanned newspaper page, not a web article), skip to Step 3

**Step 3 — OCR (GLM-OCR via Ollama)**
- Triggered when:
  - Text extraction in Step 2 failed or returned < 50 chars
  - Source is Newspapers.com (always OCR the page image regardless of text extraction)
  - User explicitly invoked `mouse-research ocr` on a local image
- Send image to GLM-OCR running locally via Ollama
- Request Markdown-formatted output (preserves headlines, columns, reading order)
- Store both the raw OCR output and a cleaned version (strip OCR artifacts, normalize whitespace)
- Fallback: if Ollama/GLM-OCR is not running, queue the image for later OCR and log a warning

**Step 4 — Metadata Assembly**
- Generate a metadata JSON file:

```json
{
  "id": "2026-04-01-gettysburg-times-mccollum-state-finals",
  "person": "Dave McCollum",
  "source": "Gettysburg Times",
  "date": "1986-03-15",
  "date_captured": "2026-04-01T14:30:00",
  "url": "https://www.newspapers.com/image/12345678/",
  "title": "Bermudian Springs coach leads Eagles to state finals",
  "authors": [],
  "tags": ["wrestling", "state-championship", "1986-season"],
  "extraction_method": "glm-ocr",
  "text_length": 1247,
  "ocr_confidence": "high",
  "files": {
    "screenshot": "screenshot.png",
    "page_image": "page_image.jpg",
    "article_text": "article.md",
    "ocr_raw": "ocr_raw.md",
    "metadata": "metadata.json",
    "html": "source.html"
  }
}
```

- Auto-detect source from URL domain:
  - `newspapers.com` → parse newspaper name from page metadata
  - `lancasteronline.com` → "LancasterOnline"
  - `ydr.com` → "York Daily Record"
  - `eveningsun.com` → "The Evening Sun"
  - `gettysburgtimes.com` → "Gettysburg Times"
  - Other → prompt user or use domain name

- Auto-detect date from article metadata, URL patterns, or OCR output
- Generate a slug: `YYYY-MM-DD_source-slug_title-slug`

**Step 5 — Obsidian Export**

Target vault path:
```
/Users/aumen-server/Documents/Obsidian Vault/01-Aumen-Film-Co/Projects/MOUSE/Research/
```

Directory structure within the Research folder:

```
Research/
├── Articles/
│   ├── 1986-03-15_gettysburg-times_eagles-state-finals/
│   │   ├── screenshot.png
│   │   ├── page_image.jpg
│   │   ├── article.md          ← Obsidian-formatted note
│   │   ├── ocr_raw.md
│   │   ├── metadata.json
│   │   └── source.html
│   ├── 2024-11-20_ydr_mouse-50th-season/
│   │   └── ...
│   └── _index.md               ← Auto-generated master index
│
├── People/
│   ├── Dave McCollum.md         ← Auto-updated with article backlinks
│   ├── Trevor Byers.md
│   ├── Rick Schmelyun.md
│   └── ...
│
└── Sources/
    ├── Gettysburg Times.md      ← Auto-updated with article backlinks
    ├── York Daily Record.md
    ├── LancasterOnline.md
    └── The Evening Sun.md
```

**Article note format (`article.md`):**

```markdown
---
person: "[[Dave McCollum]]"
source: "[[Gettysburg Times]]"
date: 1986-03-15
url: https://www.newspapers.com/image/12345678/
tags:
  - wrestling
  - state-championship
  - 1986-season
captured: 2026-04-01
extraction: glm-ocr
---

# Bermudian Springs coach leads Eagles to state finals

![[screenshot.png]]

## Article Text

[Full extracted text here]

## Notes

[Empty section for Chris to add research notes]
```

**Person note auto-update (`People/Dave McCollum.md`):**
- If the person note doesn't exist, create it with a header and empty sections
- Append a backlink entry under an `## Articles` section:
  ```markdown
  - [[1986-03-15_gettysburg-times_eagles-state-finals/article|Bermudian Springs coach leads Eagles to state finals]] — Gettysburg Times, 1986-03-15
  ```
- Never overwrite existing content in the person note — append only

**Source note auto-update (`Sources/Gettysburg Times.md`):**
- Same pattern as person notes — append backlink under `## Articles`

**Master index (`Articles/_index.md`):**
- Auto-regenerated on each archive run
- Sorted reverse-chronological
- Grouped by person, with article count per person

### 4.3 Cookie Management

```bash
# First-time setup: interactive browser login
mouse-research login newspapers.com
mouse-research login lancasteronline.com
mouse-research login ydr.com

# Saves cookies to ~/.mouse-research/cookies/<domain>.json
# Playwright reuses these cookies for all subsequent fetches
# Cookies auto-refresh on each successful authenticated page load
```

- `login` command opens a visible (non-headless) Chromium window
- User logs in manually
- On successful login detection, cookies are saved and the browser closes
- Cookies stored at `~/.mouse-research/cookies/`

---

## 5. Phase 2: Newspapers.com Bulk Discovery

### 5.1 Command Interface

```bash
# Search Newspapers.com for all mentions of a person
mouse-research search "Dave McCollum" --years 1975-2025

# Search with filters
mouse-research search "Trevor Byers" --years 1984-1990 --location "Pennsylvania"

# Search and immediately archive all results
mouse-research search "Rick Schmelyun" --years 2000-2010 --auto-archive

# Review search results before archiving
mouse-research search "Bermudian Springs wrestling" --years 1975-2025 --output results.json
mouse-research archive --file results.json --person "Dave McCollum"
```

### 5.2 Pipeline Steps

**Step 1 — Search (newspapers-com-scraper via subprocess)**
- Python wrapper calls the Node.js scraper as a subprocess:
  ```python
  subprocess.run(["node", "scraper.js", "--keyword", keyword, "--years", year_range, ...])
  ```
- Scraper outputs JSON array of results to stdout, Python captures and parses it
- Each result contains: newspaper title, page number, date, location, keyword match count, Newspapers.com URL

**Step 2 — Deduplication & Filtering**
- Deduplicate against existing articles in the Obsidian vault (match on URL or date+source combo)
- Filter by target newspapers if desired (Gettysburg Times, York Daily Record, Evening Sun, LancasterOnline)
- Sort results chronologically

**Step 3 — Interactive Review (default) or Auto-Archive**
- **Default mode:** Print a numbered list of results to the terminal. User selects which to archive (e.g., `1,3,5-12,15` or `all`)
- **`--auto-archive` mode:** Feed all results directly into the Phase 1 pipeline
- Rate limiting: 5-second delay between page fetches to avoid triggering anti-bot measures

**Step 4 — Batch Archive**
- Feed selected URLs into the Phase 1 pipeline sequentially
- Progress bar showing `[12/87] Archiving: Gettysburg Times, 1986-03-15...`
- On failure, log the URL and continue with remaining items
- Generate a batch summary at the end: `Archived 82/87 articles. 5 failures logged to ~/.mouse-research/logs/`

### 5.3 Node.js Scraper Integration

The newspapers-com-scraper is installed as a local dependency, not globally:

```
~/.mouse-research/
├── cookies/
├── logs/
├── node_modules/
│   └── newspapers-com-scraper/
├── scraper-wrapper.js        ← Thin wrapper that reads args and writes JSON to stdout
└── package.json
```

- `mouse-research install` handles the Node.js dependency installation
- The Python CLI never asks the user to run npm commands directly
- If Node.js is not installed, the CLI detects this and prints setup instructions

---

## 6. GLM-OCR Integration

### 6.1 Setup

```bash
# Install Ollama (if not present)
brew install ollama

# Pull the GLM-OCR model
ollama pull glm-ocr

# Verify
mouse-research doctor
```

### 6.2 Runtime Architecture

- GLM-OCR runs as a persistent Ollama service (Ollama manages model loading/unloading)
- The pipeline sends images to Ollama's local HTTP API (`http://localhost:11434/api/generate`)
- Request format: base64-encoded image + prompt requesting Markdown output
- Prompt template:

```
Extract all text from this newspaper page image. Preserve the layout structure 
including headlines, subheadlines, bylines, and body text. Output as clean Markdown. 
If text is illegible, mark it as [illegible]. Do not guess or fabricate text 
that cannot be read.
```

- The `[illegible]` instruction is critical — it counteracts GLM-OCR's tendency to hallucinate on degraded text

### 6.3 Fallback Chain

```
GLM-OCR (Ollama) → Tesseract (local, if Ollama unavailable) → Queue for later
```

- Tesseract is installed as a backup only: `brew install tesseract`
- If neither is available, the image is queued and the article is archived without OCR text
- Queued items can be processed later: `mouse-research ocr-queue process`

---

## 7. Configuration

### 7.1 Config File

Location: `~/.mouse-research/config.yaml`

```yaml
# Obsidian vault paths
obsidian:
  vault_root: "/Users/aumen-server/Documents/Obsidian Vault"
  project_path: "01-Aumen-Film-Co/Projects/MOUSE/Research"

# Default person (optional — saves typing for focused research sessions)
default_person: null

# OCR settings
ocr:
  engine: "glm-ocr"              # "glm-ocr" | "tesseract" | "none"
  ollama_host: "http://localhost:11434"
  always_ocr_newspapers_com: true  # Always OCR Newspapers.com pages
  illegible_marker: "[illegible]"

# Playwright settings
browser:
  headless: true
  device_scale: 2                  # Screenshot resolution multiplier
  timeout_seconds: 30
  retry_count: 1

# Search settings
search:
  rate_limit_seconds: 5            # Delay between fetches
  default_location: "Pennsylvania"
  target_papers:                   # Filter search results to these
    - "Gettysburg Times"
    - "York Daily Record"
    - "The Evening Sun"
    - "Lancaster"

# Source domain mapping
sources:
  "newspapers.com": "auto-detect"
  "lancasteronline.com": "LancasterOnline"
  "ydr.com": "York Daily Record"
  "eveningsun.com": "The Evening Sun"
  "gettysburgtimes.com": "Gettysburg Times"
```

### 7.2 Health Check

```bash
mouse-research doctor
```

Checks and reports:
- Python version ≥ 3.11
- Node.js version ≥ 18
- Ollama running + glm-ocr model pulled
- Playwright browsers installed
- Newspapers.com cookies valid (test fetch)
- Obsidian vault path exists and is writable
- Disk space available
- All Python and Node.js dependencies installed

---

## 8. Error Handling & Logging

### 8.1 Failure Modes

| Failure | Behavior |
|---------|----------|
| Network timeout | Retry once, then skip and log |
| Paywall not bypassed (cookies expired) | Warn user, prompt to re-login |
| GLM-OCR / Ollama down | Fall back to Tesseract, then queue |
| newspaper4k extraction empty | Fall back to Trafilatura, then OCR |
| Newspapers.com scraper broken | Log error, suggest manual search |
| Obsidian vault path missing | Error and exit (don't create vault structure silently) |
| Duplicate article detected | Skip and log, don't overwrite existing |

### 8.2 Logging

- All logs to `~/.mouse-research/logs/YYYY-MM-DD.log`
- Log levels: INFO (default), DEBUG (with `--verbose`)
- Failed URLs logged to `~/.mouse-research/logs/failures.jsonl` for retry:
  ```bash
  mouse-research retry-failures
  ```

---

## 9. Install & Setup Sequence

```bash
# 1. Clone or install the tool
pip install mouse-research    # or: git clone ... && pip install -e .

# 2. Install Playwright browsers
playwright install chromium

# 3. Install Node.js scraper dependency
mouse-research install        # runs npm install in ~/.mouse-research/

# 4. Install and start Ollama + GLM-OCR
brew install ollama
ollama pull glm-ocr

# 5. Install Tesseract fallback
brew install tesseract

# 6. Login to newspaper sites
mouse-research login newspapers.com

# 7. Verify everything works
mouse-research doctor

# 8. Archive your first article
mouse-research archive "https://www.newspapers.com/image/12345678/" --person "Dave McCollum"
```

---

## 10. Data Model

### 10.1 Article Record

| Field | Type | Source | Required |
|-------|------|--------|----------|
| `id` | string | Generated slug | Yes |
| `person` | string | CLI arg or config | Yes |
| `source` | string | Auto-detected from URL | Yes |
| `date` | date | Extracted or CLI arg | Yes (best-effort) |
| `date_captured` | datetime | System clock | Yes |
| `url` | string | Input URL | Yes |
| `title` | string | Extracted | Best-effort |
| `authors` | string[] | Extracted | Best-effort |
| `tags` | string[] | CLI arg | Optional |
| `extraction_method` | enum | Pipeline | Yes |
| `text_length` | int | Computed | Yes |
| `files` | object | Pipeline | Yes |

### 10.2 Search Result Record (Phase 2)

| Field | Type | Source |
|-------|------|--------|
| `newspaper_title` | string | Scraper |
| `page_number` | int | Scraper |
| `date` | date | Scraper |
| `location` | string | Scraper |
| `keyword_matches` | int | Scraper |
| `url` | string | Scraper |
| `archived` | boolean | Pipeline |
| `archived_path` | string | Pipeline |

---

## 11. Future Considerations (Not in Scope)

- **RSS feed monitoring** for new articles from target papers (requires separate always-on service)
- **Full-text search** across the research library (Obsidian's built-in search may suffice)
- **ArchiveBox integration** for WARC-level archival (overkill for this project's needs)
- **Multi-project support** (currently hardcoded to MOUSE project path)
- **Web UI** (CLI is sufficient for a single-user research workflow)
- **Zotero integration** (Obsidian handles citation needs adequately for documentary research)
- **Newspapers.com login automation** (the scraper's search endpoint doesn't require auth; Playwright handles authenticated page viewing with saved cookies)

---

## 12. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Newspapers.com changes frontend, breaks scraper | Medium | Medium | Scraper is a convenience layer; manual URL input still works. Pin scraper version. |
| Newspapers.com blocks Playwright automation | Low-Medium | High | Rate limiting (5s delays), realistic browser fingerprint, cookie-based auth looks like normal user. If blocked, fall back to manual screenshot + OCR workflow. |
| GLM-OCR hallucinates on degraded scans | Medium | Medium | Prompt instructs `[illegible]` marking. Always save the original image alongside OCR text so Chris can verify. Tesseract as cross-reference. |
| Ollama not running when pipeline invoked | Low | Low | Graceful fallback to Tesseract, then queue. `doctor` command checks health. |
| Cookie expiration | Medium | Low | Auto-refresh on successful loads. Clear warning when auth fails. Re-login is fast. |
| Node.js scraper abandoned by maintainer | Medium | Low | It's 18 commits of simple Puppeteer code — if it breaks, we fork and fix. The search functionality is the simplest part of the pipeline. |

---

## 13. Success Criteria

- `mouse-research archive <url> --person "Dave McCollum"` produces a complete article folder in the Obsidian vault within 30 seconds
- `mouse-research search "Dave McCollum" --years 1975-2025` returns results in under 2 minutes
- GLM-OCR produces readable Markdown from a 1980s newspaper scan with multi-column layout
- Person notes and source notes in Obsidian contain accurate backlinks after archiving
- The pipeline runs unattended for batch jobs of 50+ articles with <5% failure rate
- `mouse-research doctor` passes all checks on a clean Mac Mini setup in under 15 minutes
