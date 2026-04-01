# Requirements: MOUSE Research Pipeline

**Defined:** 2026-04-01
**Core Value:** `mouse-research archive <url>` produces a complete, OCR'd, Obsidian-linked article note from any newspaper URL — accurately and reliably.

## v1 Requirements

### Foundation

- [ ] **FOUND-01**: `mouse-research doctor` validates all external dependencies (Python, Node.js, Ollama, GLM-OCR, Playwright, Tesseract, vault path, disk space) and reports status
- [ ] **FOUND-02**: YAML config file at `~/.mouse-research/config.yaml` controls vault paths, OCR settings, browser settings, rate limits, and source domain mapping
- [ ] **FOUND-03**: Structured logging to `~/.mouse-research/logs/YYYY-MM-DD.log` with INFO/DEBUG levels and `--verbose` flag
- [ ] **FOUND-04**: Failed URLs logged to `~/.mouse-research/logs/failures.jsonl` for retry
- [ ] **FOUND-05**: `mouse-research login <domain>` opens visible browser for manual login and saves cookies to `~/.mouse-research/cookies/<domain>.json`
- [ ] **FOUND-06**: Saved cookies auto-loaded for all Playwright sessions with pre-flight auth check detecting expired sessions

### Archiving

- [ ] **ARCH-01**: `mouse-research archive <url>` fetches page via headless Playwright with saved cookies, captures article-focused screenshot (2x scale) and raw HTML — for Newspapers.com, extracts the clipped article image (not the full newspaper page)
- [ ] **ARCH-02**: Text extraction via newspaper4k (title, author, date, body) with Trafilatura fallback when extraction returns < 50 characters
- [ ] **ARCH-03**: GLM-OCR via Ollama processes the target article image (not the full newspaper page) with `[illegible]` markers for unreadable text, Markdown-formatted output
- [ ] **ARCH-04**: Tesseract fallback when Ollama/GLM-OCR is unavailable; images queued for later OCR if neither is available
- [ ] **ARCH-05**: OCR preprocessing (deskew, contrast enhancement via OpenCV) for degraded 1970s-80s scans before GLM-OCR processing
- [ ] **ARCH-06**: Auto-detect newspaper source from URL domain (newspapers.com → parse page metadata, lancasteronline.com → "LancasterOnline", etc.)
- [ ] **ARCH-07**: Auto-detect article date from metadata, URL patterns, or OCR output
- [ ] **ARCH-08**: Generate article folder with slug `YYYY-MM-DD_source-slug_title-slug` containing screenshot, page image, article.md, ocr_raw.md, metadata.json, source.html
- [ ] **ARCH-09**: Article note exported as Obsidian-formatted Markdown with YAML frontmatter (person, source, date, url, tags), wikilinks, and embedded screenshot
- [ ] **ARCH-10**: `mouse-research ocr <image-path>` OCRs a local image (newspaper scan, photo of clipping) with `--person`, `--date`, `--source` flags and exports to vault
- [ ] **ARCH-11**: `mouse-research archive --file urls.txt` archives multiple URLs from a file sequentially

### Bulk Search

- [ ] **BULK-01**: `mouse-research search "<query>"` calls newspapers-com-scraper as Node.js subprocess and returns structured search results (newspaper, date, location, URL, match count)
- [ ] **BULK-02**: Search results deduplicated against existing articles in Obsidian vault (match on URL or date+source combination)
- [ ] **BULK-03**: Search results filterable by year range (`--years`), location (`--location`), and target newspapers
- [ ] **BULK-04**: Interactive review mode displays numbered results; user selects which to archive (e.g., `1,3,5-12,all`)
- [ ] **BULK-05**: `--auto-archive` flag feeds all search results directly into the archiving pipeline
- [ ] **BULK-06**: Batch archiving with 5-second rate limiting between fetches, progress bar, and failure continuation
- [ ] **BULK-07**: Batch summary at completion showing archived/failed counts
- [ ] **BULK-08**: `mouse-research retry-failures` reprocesses URLs from failures.jsonl

### Research Graph

- [ ] **GRAPH-01**: People notes (`Research/People/<name>.md`) auto-created on first reference with header and empty sections
- [ ] **GRAPH-02**: People notes auto-updated with article backlink entry under `## Articles` section (append-only, never overwrite existing content)
- [ ] **GRAPH-03**: Source notes (`Research/Sources/<name>.md`) auto-created on first reference
- [ ] **GRAPH-04**: Source notes auto-updated with article backlink entry under `## Articles` section (append-only)
- [ ] **GRAPH-05**: Master index (`Research/Articles/_index.md`) auto-regenerated on each archive run, sorted reverse-chronological, grouped by person with article counts

### Setup

- [ ] **SETUP-01**: `mouse-research install` handles Node.js newspapers-com-scraper dependency installation in `~/.mouse-research/`
- [x] **SETUP-02**: `pip install mouse-research` or `pip install -e .` installs the tool with all Python dependencies

## v2 Requirements

### Enhanced OCR

- **OCR-V2-01**: OCR confidence scoring with automatic Tesseract cross-reference on low-confidence results
- **OCR-V2-02**: OCR queue management UI for reviewing and reprocessing queued images

### Enhanced Search

- **SRCH-V2-01**: Saved search profiles for frequently-searched people/queries
- **SRCH-V2-02**: Search history with dedup across sessions

## Out of Scope

| Feature | Reason |
|---------|--------|
| RSS feed monitoring | Requires separate always-on service, overkill for research workflow |
| Full-text search across library | Obsidian's built-in search is sufficient |
| ArchiveBox/WARC archival | Too heavy for this project's needs |
| Multi-project support | Hardcoded to MOUSE project path — single documentary |
| Web UI | CLI is sufficient for single-user research workflow |
| Zotero integration | Obsidian handles citation needs for documentary research |
| Newspapers.com login automation | Search doesn't need auth; Playwright handles authenticated viewing with saved cookies |
| Full-page OCR | OCR should target the specific article, not the entire newspaper page — avoids capturing unrelated articles from the same page |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Pending |
| FOUND-02 | Phase 1 | Pending |
| FOUND-03 | Phase 1 | Pending |
| FOUND-04 | Phase 1 | Pending |
| FOUND-05 | Phase 1 | Pending |
| FOUND-06 | Phase 1 | Pending |
| ARCH-01 | Phase 2 | Pending |
| ARCH-02 | Phase 2 | Pending |
| ARCH-03 | Phase 2 | Pending |
| ARCH-04 | Phase 2 | Pending |
| ARCH-05 | Phase 2 | Pending |
| ARCH-06 | Phase 2 | Pending |
| ARCH-07 | Phase 2 | Pending |
| ARCH-08 | Phase 2 | Pending |
| ARCH-09 | Phase 2 | Pending |
| ARCH-10 | Phase 2 | Pending |
| ARCH-11 | Phase 2 | Pending |
| BULK-01 | Phase 3 | Pending |
| BULK-02 | Phase 3 | Pending |
| BULK-03 | Phase 3 | Pending |
| BULK-04 | Phase 3 | Pending |
| BULK-05 | Phase 3 | Pending |
| BULK-06 | Phase 3 | Pending |
| BULK-07 | Phase 3 | Pending |
| BULK-08 | Phase 3 | Pending |
| GRAPH-01 | Phase 4 | Pending |
| GRAPH-02 | Phase 4 | Pending |
| GRAPH-03 | Phase 4 | Pending |
| GRAPH-04 | Phase 4 | Pending |
| GRAPH-05 | Phase 4 | Pending |
| SETUP-01 | Phase 1 | Pending |
| SETUP-02 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-01*
*Last updated: 2026-04-01 after roadmap creation*
