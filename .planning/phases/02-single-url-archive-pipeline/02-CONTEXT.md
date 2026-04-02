# Phase 2: Single-URL Archive Pipeline - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can run `mouse-research archive <url>` against any Newspapers.com article and receive a complete Obsidian note with YAML frontmatter, embedded screenshot, OCR'd body text, and correct file structure deposited directly into the vault. Also: `mouse-research ocr <image>` for local scans, and `mouse-research archive --file urls.txt` for multi-URL input.

Requirements: ARCH-01 through ARCH-11

</domain>

<decisions>
## Implementation Decisions

### Article Image Extraction
- Download full page JPG from Newspapers.com (via Playwright fetching the page image URL, not the Print/Download UI)
- Crop to article area before OCR (user explicitly chose this over viewport screenshot or Clip feature)
- Store both the full-page image and the cropped article image in the article folder
- Resize article crop to 500px max dimension before sending to GLM-OCR (Phase 1 validated <5% CER at this size)

### OCR Strategy (informed by Phase 1 validation)
- GLM-OCR primary for Newspapers.com article crops (500px max, via Ollama HTTP API)
- Tesseract fallback when Ollama is unavailable — runs on full page at original resolution
- OCR queue: save image path to ~/.mouse-research/ocr-queue.jsonl when neither engine is available; archive without OCR text
- OpenCV preprocessing before OCR: grayscale → CLAHE contrast → denoise → deskew

### Text Source Priority
- For Newspapers.com (scanned pages): OCR is primary text source → `## Article Text`
- For modern web articles (LancasterOnline, YDR, etc.): newspaper4k/trafilatura is primary → `## Article Text`
- When both OCR and web extraction produce text: store web extract in `## Web Extract` section
- Trigger OCR when: source is Newspapers.com (always), or text extraction returns < 50 chars

### Obsidian Note Format
- Frontmatter person field: list format — `person: ["Dave McCollum"]` (supports multi-person, avoids wikilink issues in frontmatter)
- Wikilinks for person/source in note body (not frontmatter)
- Screenshot embedded below title: `![[screenshot.png]]`
- Empty `## Notes` section at bottom for Chris's research notes
- Frontmatter fields: person (list), source (string), date, url, tags (list), captured (date), extraction (method)

### Duplicate Detection
- Match on URL (normalized — strip query params except Newspapers.com image ID)
- If existing folder has matching URL in metadata.json: print warning and skip (don't overwrite)

### Error Handling
- `--file` mode: log failed URL to failures.jsonl, print warning, continue with next URL
- Pages with no extractable text: archive with screenshot + metadata, mark as "no text extracted"
- Rate limiting: 5-second delay between fetches in `--file` mode

### Claude's Discretion
- Exact article crop detection logic (how to identify article boundaries on the full page)
- HTML parsing details for extracting Newspapers.com page image URLs
- Slug generation algorithm details
- Internal module structure (single module vs. separate fetcher/extractor/exporter modules)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/mouse_research/config.py` — AppConfig with vault path, OCR settings, browser settings, rate limit
- `src/mouse_research/logger.py` — setup_logging(), log_failure(), get_logger()
- `src/mouse_research/cookies.py` — load_cookies(), check_auth(), interactive_login()
- `src/mouse_research/installer.py` — MOUSE_DIR path constant
- `src/mouse_research/cli.py` — Typer app with existing install/doctor/login commands

### Established Patterns
- pydantic-settings for config (BaseSettings + YamlConfigSettingsSource)
- Rich Console for terminal output (console = Console() in cli.py)
- Playwright storage_state for cookie management (channel="chrome" on macOS)
- log_failure(url, reason, phase) for failure tracking

### Integration Points
- CLI: add `archive` and `ocr` commands to cli.py Typer app
- Config: read vault.path, ocr.ollama_url, browser settings, rate_limit_seconds
- Cookies: load_cookies("newspapers.com") before Playwright fetch
- Logging: setup_logging() at CLI entry, log_failure() on errors
- Vault output: write to config.vault.path / "Articles" / {slug}/

### Phase 1 Findings (CRITICAL)
- GLM-OCR crashes on images > ~500px (GGML bug in Ollama 0.19.0) — MUST resize before OCR
- GLM-OCR hallucinates on full-page images even when they don't crash — MUST crop to article
- Playwright Chromium has macOS launch issues — use channel="chrome" for non-headless
- Tesseract works on full pages at original resolution — good fallback
- .venv/ required — macOS Python 3.14 is externally-managed

</code_context>

<specifics>
## Specific Ideas

- PRD Section 4.2 defines the exact 5-step pipeline: Fetch → Extract → OCR → Metadata → Export
- PRD Section 4.2 Step 4 defines the metadata.json schema
- PRD Section 4.2 Step 5 defines the article.md note format and folder structure
- Source auto-detection from URL domain mapping is defined in PRD Section 4.2 Step 4
- Obsidian vault target: /Users/aumen-server/Documents/Obsidian Vault/01-Aumen-Film-Co/Projects/MOUSE/Research/

</specifics>

<deferred>
## Deferred Ideas

- People notes and Source notes auto-linking (Phase 4: Research Graph)
- Master article index generation (Phase 4)
- Batch search and interactive review (Phase 3: Bulk Search)
- Retry failures command (Phase 3)

</deferred>
