# Project Research Summary

**Project:** MOUSE Research Pipeline
**Domain:** Newspaper archiving + OCR pipeline CLI with Obsidian export
**Researched:** 2026-04-01
**Confidence:** MEDIUM (stack HIGH; two dependencies LOW/MEDIUM require early validation)

## Executive Summary

The MOUSE Research Pipeline is a single-user CLI tool that fetches newspaper articles (primarily 1970s–80s Pennsylvania regional papers from Newspapers.com), extracts or OCRs their content, and deposits structured research notes into an Obsidian vault for documentary research. This is a classic ETL pipeline — fetch, extract, transform, write — with a thin CLI entry point dispatching to well-isolated stages. The recommended approach is a strict layered architecture: Config → Cookie/Auth → Playwright Fetch → Text Extraction + OCR → Transform → Vault Writer, with the Node.js newspapers-com-scraper sitting as a validated subprocess behind the bulk search path. All OCR is local-first via GLM-OCR (Ollama), with Tesseract as a fallback; no cloud APIs are used.

The single highest-risk item in the project is `newspapers-com-scraper` — an 18-commit Node.js package wrapping Newspapers.com's undocumented internal API with no tests or changelog. It is the gating dependency for bulk discovery (the feature Chris needs most for active research) and must be validated against the live site before any surrounding code is written. The second risk is GLM-OCR hallucination on degraded 1970s microfilm scans: generative models fill in plausible text when visual signal is weak, which in documentary research means fabricated names and dates. Both risks are addressable with early empirical testing on real material — they are unknowns, not blockers, but they must become knowns before the bulk pipeline is built.

The recommended mitigation strategy is a Phase 1 that is explicitly a validation spike: prove the scraper returns correct JSON, prove GLM-OCR produces acceptable accuracy on actual Gettysburg Times scans from the 1970s, and prove the cookie auth flow works end-to-end. Only after Phase 1 confirms all three should the full pipeline be built. The architecture is well-understood, the Python stack is entirely verified against PyPI, and the Obsidian output pattern (direct file I/O, YAML frontmatter, wikilinks as f-strings) is the established correct approach. This is a buildable project with two front-loaded unknowns that must be resolved first.

## Key Findings

### Recommended Stack

The entire Python stack is verified on PyPI with recent release dates. Typer 0.24.1 + Rich 14.3.3 handle CLI and terminal output. Playwright 1.58.0 handles browser automation with `context.storage_state()` as the mandatory cookie persistence mechanism (the `launch_persistent_context()` alternative has a known upstream bug). Text extraction cascades newspaper4k 0.9.5 → trafilatura 2.0.0 fallback. OCR cascades GLM-OCR via ollama SDK 0.6.1 → pytesseract 0.3.13 fallback, with opencv-python 4.13.0.92 and Pillow 12.2.0 handling preprocessing. pydantic-settings 2.13.1 provides typed YAML config loading. python-frontmatter 1.1.0 handles Obsidian note frontmatter. The Node.js scraper runs as a subprocess; the Python side uses standard `subprocess.Popen()` with stdout JSON capture.

**Core technologies:**
- **Typer 0.24.1 + Rich 14.3.3**: CLI framework and terminal output — type-safe commands with first-class progress and table display
- **Playwright 1.58.0**: Authenticated browser fetch and screenshot — only tool that handles Newspapers.com's JS-rendered pages; `storage_state()` is the mandatory session persistence method
- **newspaper4k 0.9.5 + trafilatura 2.0.0**: Text extraction cascade — newspaper4k for news-specific parsing, trafilatura (F1=0.958) as fallback when body text is empty
- **GLM-OCR via ollama 0.6.1**: Primary OCR (94.62 OmniDocBench score, 0.9B params, Apple Silicon compatible) — runs locally via `ollama pull glm-ocr`; Tesseract via pytesseract as fallback
- **opencv-python 4.13.0.92 + Pillow 12.2.0**: Image preprocessing pipeline (deskew, CLAHE, denoise, adaptive threshold) before OCR
- **pydantic-settings 2.13.1**: Typed YAML config at `~/.mouse-research/config.yaml` — catches misconfiguration at startup
- **python-frontmatter 1.1.0**: Obsidian YAML frontmatter read/write — direct file I/O to vault path is the correct write pattern
- **newspapers-com-scraper (Node.js, subprocess)**: Bulk search via Newspapers.com's undocumented API — LOW confidence, must be validated in Phase 1

### Expected Features

**Must have (table stakes):**
- Single-URL archiving (Playwright fetch + screenshot + text extraction + OCR + Obsidian note)
- Cookie management for Newspapers.com with interactive login and re-login on expiry detection
- GLM-OCR via Ollama for scanned newspaper pages — without this, the 1970s–80s corpus is inaccessible
- Correct Obsidian frontmatter schema (title, date, publication, people, tags, source_url, ocr_method, archived)
- Embedded screenshot in article note as canonical source artifact
- Duplicate detection before archiving (URL normalization + content hash)
- `mouse-research doctor` health check for all 5+ external dependencies
- Rate limiting (5s default, configurable) between fetches
- YAML config file for vault paths, OCR settings, and rate limits
- Structured failure logging for batch runs

**Should have (differentiators):**
- Bulk search via newspapers-com-scraper with interactive review mode (y/n/skip per result)
- Auto-maintained People notes with backlinks from every article mentioning that person
- Auto-maintained Source notes tracking coverage per publication
- Auto-generated master article index sorted by date
- Structured retry mechanism with exponential backoff and retry queue file
- Standalone image OCR (`mouse-research ocr <image>`) for physical clippings
- Re-login prompt that resumes batch run after session refresh

**Defer (v2+):**
- Auto-tagging/NLP keyword extraction — newspaper4k quality too low for documentary precision
- RSS feed monitoring — overkill for active research workflow
- ArchiveBox/WARC archiving — too heavy; screenshot + text in Obsidian is sufficient
- Multi-project support — single vault path keeps scope manageable

### Architecture Approach

The system is a strict linear ETL pipeline with a thin CLI dispatch layer. Each stage returns a typed dataclass (`FetchResult`, `ArticleData`, `OcrResult`, `ArticleRecord`) — no shared mutable state, no fat CLI commands, no business logic in the command handlers. The Node.js scraper runs as a process boundary (stdout JSON), not as a library. The Vault Writer is the only component with filesystem side effects on the Obsidian vault, and it must upsert (never overwrite) People and Source notes. Batch runs accumulate `ArticleRecord` objects in memory and write to the vault in a single commit-like operation at the end to prevent partial index state.

**Major components:**
1. **Config loader** — YAML parsing with pydantic-settings; read-only after init; all components depend on it; build first
2. **Cookie store** — Playwright `storage_state()` JSON persistence at `~/.config/mouse-research/cookies.json`; explicit auth check before every session
3. **Playwright fetcher** — Returns `FetchResult(html, screenshot_path, url, status)`; rate limiter is shared state within this layer
4. **Text extractor** — Pure function: HTML string in, `ArticleData` out; newspaper4k primary, trafilatura fallback
5. **OCR engine** — Pure function: image path in, `OcrResult(text, confidence, engine_used)` out; GLM-OCR primary, Tesseract fallback; content-type heuristic determines whether OCR runs at all
6. **Transform layer** — Pure function: merges ArticleData + OcrResult, normalizes metadata, extracts people entities, assembles `ArticleRecord`
7. **Vault writer** — All Obsidian filesystem writes; article note + upsert People/Source notes + append index; upsert logic required, never overwrite
8. **Node.js bridge** — `subprocess.Popen()` wrapper; captures stdout JSON and stderr separately; validates exit code explicitly
9. **Doctor command** — Validates Ollama, Playwright, Node.js, Tesseract, vault path, scraper `node_modules`, GLM-OCR model loaded

### Critical Pitfalls

1. **newspapers-com-scraper is untested and wraps an undocumented API** — Run a smoke test (known search query, assert expected JSON fields returned) before writing any code that depends on it. Pin the npm version. Capture raw stdout before parsing. If it fails, the entire bulk discovery phase must be redesigned.

2. **GLM-OCR hallucinates on degraded 1970s microfilm scans** — Generative models fill in plausible text when visual signal is weak; names, dates, and statistics can be fabricated. Always embed the original screenshot alongside OCR output. Label OCR text as unverified. Test on 5–10 actual Gettysburg Times / York Daily Record 1970s scans before committing to GLM-OCR as primary engine; Tesseract with preprocessing may outperform it on this specific degraded corpus.

3. **Stale Newspapers.com session proceeds silently, archiving empty/broken content** — Playwright `storageState` has no expiry awareness. A stale session fetches login wall pages without raising an error, and the pipeline stores garbage. Implement an explicit auth check (fetch a known authenticated URL, assert logged-in indicator) as a precondition to every Playwright session — not optional.

4. **Multi-column 1970s newspaper layouts break OCR reading order** — Neither GLM-OCR nor Tesseract reliably handles 6–8 column historical layouts. Text mixes across columns producing incoherent output. Verify that Newspapers.com article pages present pre-cropped article images (not full pages); document that the standalone `ocr` command degrades on full-page multi-column scans.

5. **newspaper4k resource exhaustion on bulk runs (confirmed GitHub issue)** — After hundreds of articles, `article.parse()` raises "article was not downloaded" for all subsequent items due to temp directory accumulation. Mitigation: use Playwright for all fetching; pass pre-fetched HTML to newspaper4k for parsing only. Add checkpoint markers per article so reruns skip completed items.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Validation Spike + Foundation
**Rationale:** Three critical unknowns must become knowns before building anything: (1) does newspapers-com-scraper return usable JSON from the live site, (2) does GLM-OCR produce acceptable accuracy on actual 1970s Pennsylvania newspaper scans, (3) does the Playwright cookie flow work end-to-end on Newspapers.com. These are all or nothing — a "no" on any of them requires a redesign before the pipeline is built. Simultaneously, Config loader, Cookie store, and Structured logger have no upstream dependencies and unblock everything downstream.

**Delivers:** Validated scraper integration, GLM-OCR accuracy baseline on real corpus, working auth flow, config/cookie/logger foundation, `mouse-research doctor` command.

**Addresses:** newspapers-com-scraper validation, GLM-OCR accuracy, cookie management foundation, doctor command, YAML config.

**Avoids:** Building the bulk pipeline on an unvalidated scraper (Pitfall 1), committing to a hallucinatory OCR engine (Pitfall 2), silent stale-session failures (Pitfall 3).

### Phase 2: Single-URL Archive Pipeline
**Rationale:** With dependencies validated in Phase 1, build the complete single-URL pipeline end-to-end. This is the core value proposition and validates the entire data flow: fetch → text extract → OCR → transform → vault write. Building this before bulk search ensures the per-article logic is solid before it is called in a batch loop.

**Delivers:** `mouse-research archive <url>` producing a complete, OCR'd, frontmatter-correct Obsidian note with embedded screenshot. Includes rate limiting, duplicate detection, and failure logging.

**Uses:** Playwright fetcher, newspaper4k + trafilatura cascade, GLM-OCR + Tesseract cascade, OpenCV preprocessing, Transform layer, Vault writer.

**Implements:** Full ETL pipeline (Layers 3–7 from architecture diagram). Establishes typed dataclass interfaces between stages.

**Avoids:** Stale session silent failure (auth check precondition), screenshot capturing overlays (dismiss modals before screenshot), filename collisions (canonical slug format established here — Pitfall 6).

### Phase 3: Bulk Search + Batch Archive
**Rationale:** Depends on Phase 1 scraper validation and Phase 2 single-URL archive being solid. The batch archiver is a loop over the single-URL flow; it can only be reliable if that flow is reliable first. Interactive review mode (y/n/skip) is built here because it depends on search results being available.

**Delivers:** `mouse-research search <keywords> [--date-range] [--location]` with interactive review, dedup across existing vault, batch archiving with progress display, rate limiting, and failure log. `--auto` flag for unattended runs.

**Uses:** Node.js bridge (subprocess.Popen + stdout JSON), batch archiver with Rich progress bar, retry queue file.

**Implements:** Node.js bridge component, batch archiver, interactive review UI.

**Avoids:** Subprocess interop failures (stderr captured, exit code checked — Pitfall 5), newspaper4k resource exhaustion (Playwright-fetched HTML only — Pitfall 7), rate limit IP flagging (5–15s delays, batch size cap — Pitfall 10), partial vault state on interruption (accumulate ArticleRecords, write in batch — Architecture anti-pattern 5).

### Phase 4: Research Graph + Hardening
**Rationale:** People notes, Source notes, and the master index add high value but depend on the per-article archive flow being stable and the frontmatter schema being locked. Building them last prevents schema churn from breaking backlink indexes. Hardening (retry mechanism, re-login prompt mid-batch, `--retry-failed` flag) also belongs here once the happy path is proven.

**Delivers:** Auto-maintained People notes with article backlinks, Source notes per publication, master `Articles.md` index sorted by date, structured retry with exponential backoff, re-login prompt that resumes batch runs, standalone `mouse-research ocr <image>` command.

**Addresses:** Auto-maintained People/Source notes, master article index, retry mechanism, re-login on cookie expiry, standalone image OCR.

**Avoids:** Overwriting manually-edited People/Source notes (upsert pattern — Architecture decision), duplicate person notes from filename variations (canonical slug + existence check — Pitfall 6).

### Phase Ordering Rationale

- Phase 1 before everything else because two of the three critical unknowns (scraper, OCR accuracy) cannot be mitigated by design — they require empirical validation on real material.
- Phase 2 before Phase 3 because batch archive is a loop over single-URL archive; a fragile single-URL flow means a fragile batch.
- Phase 3 before Phase 4 because People/Source notes and indexes are downstream outputs of the archive event — building them on a stable per-article record is far cleaner than retrofitting.
- The Config loader, Cookie store, and Structured logger are built in Phase 1 not because they are experimental but because they have zero upstream dependencies and everything else requires them.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** newspapers-com-scraper behavior needs live testing against Newspapers.com — cannot be researched further from documentation alone; must be run.
- **Phase 1:** GLM-OCR accuracy on 1970s degraded microfilm needs empirical benchmarking on the actual target corpus (Gettysburg Times, York Daily Record) — benchmark numbers from OmniDocBench do not cover this specific material.
- **Phase 3:** Newspapers.com anti-bot fingerprinting with headless Chromium — real Chrome binary vs. Playwright Chromium behavior in 2026 needs live testing; stealth plugin applicability unclear.

Phases with standard patterns (skip research-phase):
- **Phase 2 (text extraction):** newspaper4k + trafilatura cascade is a well-documented pattern with verified benchmarks.
- **Phase 2 (Obsidian output):** Direct file I/O + python-frontmatter + f-string wikilinks is the established correct approach; no novel patterns needed.
- **Phase 4 (upsert logic):** Standard file existence check + append pattern; well-understood.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All Python packages verified on PyPI with recent release dates; one exception: httpx version from WebSearch only (MEDIUM). Node.js subprocess pattern is standard and well-documented. |
| Features | HIGH | Feature set is well-defined in PROJECT.md and cross-confirmed by FEATURES.md research. Anti-features are explicitly scoped out with clear rationale. |
| Architecture | HIGH | ETL pipeline pattern is well-established. Component boundaries, data flow, and build order are explicit. Key decisions (upsert not overwrite, single process no queue, storage_state for cookies) are all HIGH confidence. OCR routing heuristic is MEDIUM. |
| Pitfalls | HIGH | Critical pitfalls are sourced from peer-reviewed literature (arXiv), official GitHub issues, and official Playwright documentation. The two highest-risk items (scraper, GLM-OCR accuracy) are correctly flagged as requiring empirical validation. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **newspapers-com-scraper live behavior**: Does it require a Newspapers.com auth session? Does it return consistent JSON across searches? Does it respect rate limits or need throttling on the Python side? Does it find system Chrome or require `executablePath` config? Cannot be answered without running it — must be the first Phase 1 task.

- **GLM-OCR accuracy on target corpus**: The 94.62 OmniDocBench score is on a clean benchmark, not 1970s Pennsylvania microfilm scans. Character Error Rate on actual material is unknown. If CER is unacceptable, Tesseract with aggressive OpenCV preprocessing may be the better primary engine for this corpus specifically.

- **Newspapers.com session duration**: The project notes session duration is unknown. The re-login prompt and 7-day cookie age warning are conservative defaults; actual expiry behavior needs one cycle of observation during Phase 1 auth testing.

- **Newspapers.com article page image structure**: The architecture assumes Newspapers.com article pages present pre-cropped article images (not full newspaper pages). This is critical for OCR reading order. Must be confirmed during Phase 1 single-URL testing before multi-column layout mitigation is scoped.

## Sources

### Primary (HIGH confidence)
- [Playwright Python auth docs](https://playwright.dev/python/docs/auth) — storage_state pattern, known launch_persistent_context bug
- [GLM-OCR Ollama library page](https://ollama.com/library/glm-ocr) — model availability, size, Apple Silicon support
- [GLM-OCR GitHub (zai-org)](https://github.com/zai-org/GLM-OCR) — OmniDocBench 94.62 score, 0.67 img/sec throughput
- [trafilatura evaluation docs](https://trafilatura.readthedocs.io/en/latest/evaluation.html) — F1=0.958 benchmark
- [newspapers-com-scraper GitHub](https://github.com/njraladdin/newspapers-com-scraper) — source review, output format, 18-commit history
- [newspaper4k GitHub issue #546](https://github.com/AndyTheFactory/newspaper4k/issues/546) — confirmed resource exhaustion on bulk runs
- [Obsidian wikilink forum](https://forum.obsidian.md/t/inconsistent-treatment-of-wikilink-path/112694) — filename collision behavior
- PyPI pages for all Python packages (Playwright, newspaper4k, trafilatura, Typer, Rich, pydantic-settings, python-frontmatter, ollama, pytesseract, Pillow, opencv-python)

### Secondary (MEDIUM confidence)
- [arXiv 2501.11623](https://arxiv.org/html/2501.11623v1) — LLM OCR hallucination on degraded historical documents
- [arXiv 2502.01205](https://arxiv.org/html/2502.01205v1) — LLM OCR post-correction failure modes
- [arXiv 2202.01414](https://arxiv.org/abs/2202.01414) — multi-column layout OCR reading order problems
- [Springer — Enhancing OCR in Historical Documents](https://link.springer.com/article/10.1007/s00799-025-00413-z) — historical newspaper OCR pipeline patterns
- [BrowserStack — Playwright bot detection](https://www.browserstack.com/guide/playwright-bot-detection) — headless fingerprinting risks
- [Playwright storageState — BrowserStack](https://www.browserstack.com/guide/playwright-storage-state) — cookie expiry behavior

### Tertiary (LOW confidence)
- newspapers-com-scraper functionality in production — confirmed via GitHub README only; live behavior unvalidated
- GLM-OCR accuracy on 1970s Pennsylvania newspaper microfilm — inferred from general benchmark; not tested on target corpus

---
*Research completed: 2026-04-01*
*Ready for roadmap: yes*
