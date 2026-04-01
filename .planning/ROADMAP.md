# Roadmap: MOUSE Research Pipeline

## Overview

Four phases deliver the complete research pipeline. Phase 1 resolves the two critical unknowns (newspapers-com-scraper live behavior and GLM-OCR accuracy on 1970s microfilm) before any dependent code is written — a no on either requires redesign, so they must become knowns first. Phase 2 builds the core single-URL archive pipeline that delivers the project's stated core value. Phase 3 adds bulk search and batch archiving on top of the validated single-URL flow. Phase 4 adds the research graph (People notes, Source notes, master index) and hardens the system with retry, re-login, and standalone OCR.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation + Validation** - Install the tool, validate all high-risk dependencies, establish config/cookie/logging foundation
- [ ] **Phase 2: Single-URL Archive Pipeline** - `mouse-research archive <url>` produces a complete, OCR'd, Obsidian-linked article note
- [ ] **Phase 3: Bulk Search + Batch Archive** - `mouse-research search` with interactive review and batch archiving
- [ ] **Phase 4: Research Graph + Hardening** - Auto-maintained People/Source notes, master index, retry mechanism, standalone OCR

## Phase Details

### Phase 1: Foundation + Validation
**Goal**: The tool is installable, all external dependencies are confirmed working, the two highest-risk unknowns (newspapers-com-scraper and GLM-OCR accuracy on 1970s scans) are empirically validated, and the config/cookie/logging foundation is in place
**Depends on**: Nothing (first phase)
**Requirements**: SETUP-01, SETUP-02, FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06
**Success Criteria** (what must be TRUE):
  1. `pip install -e .` and `mouse-research install` complete without errors and install all dependencies
  2. `mouse-research doctor` reports green status for all external dependencies (Python, Node.js, Ollama, GLM-OCR model, Playwright, Tesseract, vault path, disk space)
  3. `mouse-research login newspapers.com` opens a visible browser, accepts a manual login, and saves cookies that a subsequent Playwright session loads and uses for authenticated access
  4. newspapers-com-scraper returns valid structured JSON for a known search query against the live Newspapers.com site
  5. GLM-OCR via Ollama produces acceptable text extraction on at least 3 actual Gettysburg Times / York Daily Record 1970s scans, with Character Error Rate documented
**Plans**: TBD

### Phase 2: Single-URL Archive Pipeline
**Goal**: Users can run `mouse-research archive <url>` against any Newspapers.com article and receive a complete Obsidian note with YAML frontmatter, embedded screenshot, OCR'd body text, and correct file structure deposited directly into the vault
**Depends on**: Phase 1
**Requirements**: ARCH-01, ARCH-02, ARCH-03, ARCH-04, ARCH-05, ARCH-06, ARCH-07, ARCH-08, ARCH-09, ARCH-10, ARCH-11
**Success Criteria** (what must be TRUE):
  1. `mouse-research archive <url>` on a Newspapers.com article creates a folder `YYYY-MM-DD_source-slug_title-slug` in the vault containing screenshot, article.md, ocr_raw.md, metadata.json, and source.html
  2. The generated article.md has correct YAML frontmatter (person, source, date, url, tags), wikilinks, and an embedded screenshot; OCR text targets the article image, not the full newspaper page
  3. Running the same URL twice does not create a duplicate — the command detects the existing article and skips or reports
  4. `mouse-research ocr <image-path>` OCRs a local image and exports a note to the vault with `--person`, `--date`, `--source` metadata applied
  5. `mouse-research archive --file urls.txt` archives multiple URLs sequentially with 5-second rate limiting and logs failures to failures.jsonl without halting the batch
**Plans**: TBD
**UI hint**: yes

### Phase 3: Bulk Search + Batch Archive
**Goal**: Users can search Newspapers.com from the CLI, review results interactively, and send selected articles (or all results) into the archive pipeline with progress tracking and deduplication against the existing vault
**Depends on**: Phase 2
**Requirements**: BULK-01, BULK-02, BULK-03, BULK-04, BULK-05, BULK-06, BULK-07, BULK-08
**Success Criteria** (what must be TRUE):
  1. `mouse-research search "<query>"` returns a numbered list of results showing newspaper, date, location, URL, and match count, filtered to exclude articles already in the vault
  2. Search results can be filtered with `--years` and `--location` flags to narrow results to the target time period and Pennsylvania papers
  3. From interactive review mode, the user can enter selections like `1,3,5-12,all` and those articles are archived with progress display
  4. `mouse-research search "<query>" --auto-archive` archives all results in a single unattended batch with 5-second rate limiting, a progress bar, and a completion summary showing archived/failed counts
  5. `mouse-research retry-failures` reads failures.jsonl and reprocesses failed URLs
**Plans**: TBD

### Phase 4: Research Graph + Hardening
**Goal**: Every archived article automatically updates the relevant People notes, Source notes, and master index; failed batches can be retried; and the system prompts for re-login when a session expires mid-run
**Depends on**: Phase 3
**Requirements**: GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04, GRAPH-05
**Success Criteria** (what must be TRUE):
  1. Archiving an article that references a person creates or updates `Research/People/<name>.md` with a backlink to the article — existing content in the People note is never overwritten
  2. Archiving an article creates or updates `Research/Sources/<publication>.md` with a backlink entry under `## Articles` — append-only, never overwrites
  3. After any archive run, `Research/Articles/_index.md` reflects all articles in the vault sorted reverse-chronological and grouped by person with article counts
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation + Validation | 1/5 | In Progress|  |
| 2. Single-URL Archive Pipeline | 0/? | Not started | - |
| 3. Bulk Search + Batch Archive | 0/? | Not started | - |
| 4. Research Graph + Hardening | 0/? | Not started | - |
