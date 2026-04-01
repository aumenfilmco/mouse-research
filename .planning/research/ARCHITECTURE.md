# Architecture Patterns

**Domain:** Newspaper research archiving and OCR pipeline
**Project:** MOUSE Research Pipeline
**Researched:** 2026-04-01

## Recommended Architecture

The system is a **linear extract-transform-load (ETL) pipeline** with a CLI entry point and two primary input modes: single URL archiving and bulk search. The architecture separates concerns cleanly across six layers: command dispatch, fetching, extraction, OCR, transformation, and output.

```
┌─────────────────────────────────────────────────────────┐
│  CLI Layer (Typer/Click)                                │
│  Commands: archive, search, ocr, doctor, login          │
└──────────────┬──────────────────┬───────────────────────┘
               │                  │
    ┌──────────▼──────┐  ┌────────▼────────────────────┐
    │  Fetch Layer    │  │  Search Layer               │
    │  Playwright     │  │  Node.js subprocess         │
    │  Cookie store   │  │  (newspapers-com-scraper)   │
    │  Rate limiter   │  │  JSON stdout → Python       │
    └──────────┬──────┘  └────────┬────────────────────┘
               │                  │ (list of URLs)
               │◄─────────────────┘
    ┌──────────▼──────────────────────────────────────┐
    │  Extraction Layer                               │
    │  newspaper4k (primary text)                     │
    │  Trafilatura (fallback text)                    │
    │  Playwright screenshots + HTML capture          │
    └──────────┬──────────────────────────────────────┘
               │
    ┌──────────▼──────────────────────────────────────┐
    │  OCR Layer                                      │
    │  GLM-OCR via Ollama API (primary)               │
    │  Tesseract pytesseract (fallback)               │
    │  Confidence check → route to fallback           │
    └──────────┬──────────────────────────────────────┘
               │
    ┌──────────▼──────────────────────────────────────┐
    │  Transform Layer                                │
    │  Metadata normalization (title, date, source)   │
    │  People/entity extraction                       │
    │  Frontmatter assembly                           │
    │  Wikilink resolution                            │
    └──────────┬──────────────────────────────────────┘
               │
    ┌──────────▼──────────────────────────────────────┐
    │  Output Layer (Obsidian Vault Writer)           │
    │  Article note (.md) with embedded screenshots  │
    │  People notes with backlinks                    │
    │  Source notes with backlinks                    │
    │  Master article index                           │
    └─────────────────────────────────────────────────┘
```

## Component Boundaries

| Component | Responsibility | Communicates With | Isolation Boundary |
|-----------|---------------|-------------------|--------------------|
| CLI (Typer) | Command dispatch, argument validation, progress display | All layers via direct call | Entry point only — no business logic |
| Config loader | YAML config parsing, path resolution, default injection | All components at startup | Read-only after init |
| Cookie store | Session persistence, cookie load/save, expiry detection, re-login prompt | Playwright fetcher only | File-backed JSON in `~/.config/mouse-research/` |
| Rate limiter | Inter-request delay enforcement | Playwright fetcher only | Shared state, not a service |
| Playwright fetcher | Browser automation, screenshot capture, HTML capture, authenticated page load | Cookie store, rate limiter | Returns `FetchResult(html, screenshot_path, url, status)` |
| Node.js search subprocess | Newspapers.com keyword/date/location search | Called by CLI search command; returns JSON via stdout | Process boundary — no shared memory |
| Node.js bridge | Python-side subprocess launcher and stdout JSON parser | Node.js search subprocess, CLI search command | Wraps `subprocess.run()` + JSON decode |
| Text extractor | newspaper4k primary → Trafilatura fallback; returns clean article text + metadata | Playwright fetcher output (HTML string) | Pure function: HTML in, `ArticleData` out |
| OCR engine | GLM-OCR via Ollama API (primary) → Tesseract (fallback); confidence threshold routing | Screenshot files from fetcher | Pure function: image path in, `OcrResult(text, confidence, engine_used)` out |
| Transform layer | Merge text extraction + OCR output, normalize metadata, extract people/entities | Text extractor, OCR engine outputs | Pure function: raw data in, `ArticleRecord` out |
| Vault writer | Write article note, upsert People notes, upsert Source notes, update index | Transform layer `ArticleRecord`, filesystem only | Filesystem boundary — all vault writes here |
| Doctor command | Dependency health checks (Ollama, Playwright, Node, Tesseract, vault path) | All external dependencies (read-only checks) | Diagnostic only, no mutations |
| Structured logger | Rotating log file, failure tracking, retry queue | All components emit to it | Write-only from components; read only by retry logic |

## Data Flow

### Single URL Archive Flow

```
CLI: archive <url>
  │
  ├─► Config loader → injects vault path, OCR settings, browser settings
  │
  ├─► Cookie store → loads Newspapers.com session cookies
  │
  ├─► Playwright fetcher
  │     ├─ Loads cookies into browser context
  │     ├─ Navigates to URL with rate limiter
  │     ├─ Captures full-page screenshot → saves to /tmp/mouse-research/<uuid>.png
  │     ├─ Captures page HTML
  │     └─► Returns FetchResult
  │
  ├─► Text extractor (receives FetchResult.html)
  │     ├─ newspaper4k attempts extraction
  │     ├─ If confidence low or failure → Trafilatura fallback
  │     └─► Returns ArticleData(title, author, date, text, source)
  │
  ├─► OCR engine (receives FetchResult.screenshot_path)
  │     ├─ Sends image to Ollama GLM-OCR API
  │     ├─ If Ollama unavailable or confidence < threshold → Tesseract fallback
  │     └─► Returns OcrResult(text, confidence, engine_used)
  │
  ├─► Transform layer (receives ArticleData + OcrResult)
  │     ├─ Merges text: prefer OCR text for scanned images, text extractor for digital
  │     ├─ Normalizes date format, source name
  │     ├─ Extracts people entities from text
  │     └─► Returns ArticleRecord(frontmatter dict, body_text, people[], source_name, screenshot_path)
  │
  └─► Vault writer (receives ArticleRecord)
        ├─ Writes <slug>.md to Articles/ folder
        ├─ Upserts each person in People/ folder (appends backlink)
        ├─ Upserts source entry in Sources/ folder (appends backlink)
        └─ Appends row to _index.md
```

### Bulk Search Flow

```
CLI: search <keywords> [--date-range] [--location] [--auto-archive]
  │
  ├─► Node.js bridge
  │     ├─ Spawns: node newspapers-com-scraper/index.js <args>
  │     ├─ Reads stdout line-by-line (newline-delimited JSON)
  │     └─► Yields SearchResult(title, date, location, url, keyword_matches)
  │
  ├─► [If interactive mode] Review UI
  │     ├─ Displays results in terminal (Rich table)
  │     ├─ User selects which URLs to archive
  │     └─► Returns selected URL list
  │
  └─► Batch archiver (receives URL list)
        ├─ Deduplication check against existing vault articles
        ├─ For each URL: runs single-URL archive flow (above)
        ├─ Enforces rate limiting between fetches
        ├─ Logs failures to retry queue
        └─► Progress bar via Rich
```

### Cookie Session Flow

```
Playwright fetcher (any request)
  │
  ├─► Cookie store: load cookies from disk
  │     ├─ File exists + not expired → inject into browser context → proceed
  │     └─ File missing or expired
  │           └─► Prompt: "Newspapers.com session expired. Run: mouse-research login"
  │                 CLI: login command
  │                   ├─ Opens browser via Playwright
  │                   ├─ Navigates to Newspapers.com login page
  │                   ├─ Waits for user to log in manually
  │                   ├─ Detects successful auth (URL change or element presence)
  │                   └─► Saves context.storage_state() to cookie store file
```

## Component Build Order

Build order follows data flow dependencies: nothing downstream can be built until its upstream supplier has a stable interface.

### Phase 1 — Foundation (no dependencies between components; build in parallel)

1. **Config loader** — No upstream deps. All other components depend on it. Build first.
2. **Structured logger** — No upstream deps. Required by all error-handling paths.
3. **Cookie store** — No upstream deps. Needed before any authenticated fetch.

### Phase 2 — Fetch (depends on Phase 1)

4. **Playwright fetcher** — Depends on config, logger, cookie store. Core pipeline input. Until this works, nothing downstream can be tested with real data.
5. **Doctor command** — Depends on config. Can validate Ollama, Playwright, Node.js, vault path early. Useful for CI and onboarding.

### Phase 3 — Extraction (depends on Phase 2)

6. **Text extractor** — Depends on fetcher output (HTML string). Pure function, easy to unit test with saved HTML fixtures.
7. **OCR engine** — Depends on fetcher output (screenshot path). Requires Ollama running. Needs fallback path tested independently with Tesseract before GLM-OCR integration.

### Phase 4 — Transform + Output (depends on Phase 3)

8. **Transform layer** — Depends on text extractor and OCR engine outputs. Pure function; testable with fixture data.
9. **Vault writer** — Depends on transform output. High value: this is where research artifacts land. Test with a scratch vault directory.

### Phase 5 — Search + Batch (depends on Phase 2, Phase 4)

10. **Node.js bridge** — Depends on Node.js subprocess being installed and functional. Must validate `newspapers-com-scraper` works before building the bridge wrapper.
11. **Batch archiver** — Depends on single-URL archive flow (Phases 2–4) and Node.js bridge.
12. **Interactive review UI** — Depends on search results from Node.js bridge. Build last; purely presentational.

## Key Architectural Decisions

### OCR Routing Strategy
Do not blindly route all pages through OCR. Use a **content-type heuristic** at the transform layer:
- If the page is a scanned image (newspaper4k returns low-confidence or near-empty text, or URL matches Newspapers.com viewer pattern) → use OCR result as primary text.
- If the page is a digital article (newspaper4k returns high-confidence text) → use text extractor result, skip OCR or run OCR in background.

This matters because GLM-OCR takes ~1.5 seconds/image and Tesseract is slower on multi-column layouts. Unnecessary OCR on already-digital text wastes time.

**Confidence:** MEDIUM (based on GLM-OCR throughput benchmarks of 0.67 images/sec and Tesseract known slowness on column layouts)

### Node.js Bridge: stdout JSON, not file intermediary
The newspapers-com-scraper emits events (article, progress, complete). When called as a subprocess, the bridge should capture newline-delimited JSON from stdout rather than writing intermediate CSV/JSON files. This keeps the integration stateless and avoids temp file cleanup.

The bridge must handle two failure modes: Node.js not installed (surface as clear error in `doctor`), and the scraper returning zero results (normal condition, not an error).

**Confidence:** MEDIUM (based on scraper README event architecture; subprocess stdout JSON is the standard pattern for Python-Node IPC per multiple sources)

### Vault Writer: Upsert, Not Overwrite
People notes and Source notes must be **upserted** (append backlink if note exists, create with backlink if it doesn't). Overwriting would destroy manually-added content in the vault. Article notes should error if the slug already exists — never silently overwrite a previously archived article.

**Confidence:** HIGH (standard Obsidian automation practice; destructive overwrite is the most common reported failure mode in vault automation)

### Single Process, No Queue
This is a single-user CLI on a local machine. There is no need for a task queue (Celery, RQ) or async job system. The batch archiver runs synchronously with a progress bar. If a fetch fails, it logs to a failure file and continues. A `--retry-failed` flag can replay the failure log.

**Confidence:** HIGH (aligns with project constraints; complexity of a queue system not justified for single-user workflow)

### Cookie Storage Location
Use `~/.config/mouse-research/cookies.json` (XDG-compliant). Use Playwright's `context.storage_state()` format natively — it includes cookies, localStorage, and sessionStorage, which is more reliable than cookie-only approaches for modern auth flows.

**Confidence:** HIGH (Playwright documentation; storage_state is the canonical approach for session reuse)

## Anti-Patterns to Avoid

### Anti-Pattern 1: Fat CLI Commands
**What:** Putting fetch/extract/OCR/write logic directly inside Click/Typer command functions.
**Why bad:** Makes unit testing impossible without invoking the full CLI. Creates tight coupling between argument parsing and business logic.
**Instead:** CLI commands are thin dispatchers. Each calls a service function (`archive_url(url, config)`) that can be imported and tested directly.

### Anti-Pattern 2: Shared Mutable State Between Pipeline Stages
**What:** Using module-level globals or a shared dict to pass data between stages.
**Why bad:** Makes stage ordering implicit, creates debugging hell when a stage mutates upstream data.
**Instead:** Each stage returns a typed dataclass (`FetchResult`, `ArticleData`, `OcrResult`, `ArticleRecord`). Data flows forward explicitly.

### Anti-Pattern 3: OCR on Every Page Regardless of Content
**What:** Always running GLM-OCR even on digital HTML articles.
**Why bad:** ~1.5 sec/page overhead for zero quality gain on modern HTML articles.
**Instead:** Route based on content-type heuristic in the transform layer (see OCR Routing Strategy above).

### Anti-Pattern 4: Blocking the Main Thread During Node.js Subprocess
**What:** Using `subprocess.run()` with no timeout for the Node.js search subprocess.
**Why bad:** If the scraper hangs (network timeout, anti-bot block), the entire CLI hangs with no feedback.
**Instead:** Use `subprocess.Popen()` with streaming stdout and a configurable timeout. Surface progress via the 'progress' events the scraper emits.

### Anti-Pattern 5: Writing Directly to Obsidian Vault During Batch Runs
**What:** Writing each article note immediately during batch processing.
**Why bad:** If the batch run is interrupted mid-way, the index and backlinks are in a partially-updated state.
**Instead:** Accumulate all `ArticleRecord` objects in memory during the batch, then write all vault files in a single commit-like operation at the end. For very large batches (>50 articles), write in chunks with a checkpoint file.

## Scalability Considerations

This is a single-user local tool. Scalability concerns are about reliability and maintainability, not distributed scale.

| Concern | At 10 articles | At 100 articles | At 1000 articles |
|---------|---------------|-----------------|------------------|
| OCR throughput | Negligible (~15s) | ~2.5 min (GLM-OCR) | ~25 min — consider batch OCR with progress |
| Vault index size | Trivial | Small markdown table | May need pagination or split index files |
| Cookie expiry | Manual check OK | Need proactive expiry warning | Same — session duration unlikely to change |
| Duplicate detection | In-memory set OK | In-memory set OK | Read existing note slugs from vault on startup |
| Node.js scraper | Single search fine | Multiple searches — dedup across runs | Persistent dedup store (SQLite or JSON) |

## Sources

- [Structured OCR for Newspapers: YOLOX and Vision LLMs](https://webkul.com/blog/structured-ocr-newspaper-pipeline/) (MEDIUM confidence — WebSearch)
- [GLM-OCR: Tiny 0.9B Vision-Language Model](https://medium.com/@gsaidheeraj/glm-ocr-the-tiny-0-9b-vision-language-model-that-reads-documents-like-a-human-e79c458319cc) (MEDIUM confidence — WebSearch)
- [GLM-OCR Ollama library page](https://ollama.com/library/glm-ocr) (HIGH confidence — official)
- [newspapers-com-scraper GitHub](https://github.com/njraladdin/newspapers-com-scraper) (HIGH confidence — official source)
- [Playwright cookie/storage state documentation](https://webscraping.ai/faq/playwright/how-do-i-handle-cookies-and-sessions-in-playwright) (HIGH confidence — Playwright docs)
- [Python-Node.js IPC via stdout JSON](https://www.sohamkamani.com/nodejs/python-communication/) (MEDIUM confidence — WebSearch, standard pattern)
- [Trafilatura evaluation documentation](https://trafilatura.readthedocs.io/en/latest/evaluation.html) (HIGH confidence — official docs)
- [newspaper4k PyPI](https://pypi.org/project/newspaper4k/) (HIGH confidence — official)
- [obsidiantools Python package](https://github.com/mfarragher/obsidiantools) (HIGH confidence — official source)
- [Data pipeline ETL patterns — Dagster](https://dagster.io/guides/data-pipeline-architecture-5-design-patterns-with-examples) (HIGH confidence)
