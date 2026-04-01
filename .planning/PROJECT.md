# MOUSE Research Pipeline

## What This Is

A CLI-driven newspaper research pipeline for the MOUSE documentary project ("MOUSE: 50 Years on the Mat"). The tool searches for articles about people and events related to the documentary, downloads them as images, extracts text via OCR, and deposits organized research files directly into Chris's Obsidian vault. One command, one language interface (Python), everything lands in the right folder.

## Core Value

`mouse-research archive <url>` produces a complete, OCR'd, Obsidian-linked article note from any newspaper URL — accurately and reliably.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Single URL archiving with Playwright fetch, screenshot, and HTML capture
- [ ] Text extraction via newspaper4k with Trafilatura fallback
- [ ] High-accuracy OCR via GLM-OCR (Ollama) for scanned newspaper pages, with Tesseract fallback
- [ ] Obsidian export with frontmatter, wikilinks, and embedded screenshots
- [ ] Auto-maintained People notes with article backlinks
- [ ] Auto-maintained Source notes with article backlinks
- [ ] Auto-generated master article index
- [ ] Cookie management for authenticated Newspapers.com access (interactive login, saved cookies)
- [ ] Bulk discovery via newspapers-com-scraper (Node.js) with search, dedup, and filtering
- [ ] Interactive review mode for search results (select which to archive)
- [ ] Auto-archive mode for batch processing search results
- [ ] Batch archiving with progress display, rate limiting, and failure logging
- [ ] Local image OCR (`mouse-research ocr <image>`) for newspaper clippings and photos
- [ ] Health check command (`mouse-research doctor`) validating all dependencies
- [ ] YAML configuration for vault paths, OCR settings, browser settings, and source mapping
- [ ] Structured logging and failure retry mechanism

### Out of Scope

- RSS feed monitoring — requires separate always-on service, overkill for research workflow
- Full-text search — Obsidian's built-in search is sufficient
- ArchiveBox/WARC archival — too heavy for this project's needs
- Multi-project support — hardcoded to MOUSE project path
- Web UI — CLI is sufficient for single-user workflow
- Zotero integration — Obsidian handles citation needs for documentary research
- Newspapers.com login automation — scraper search doesn't need auth; Playwright handles authenticated viewing

## Context

- **Runtime environment:** Mac Mini (Apple Silicon), always-on studio machine
- **Obsidian vault:** `/Users/aumen-server/Documents/Obsidian Vault/01-Aumen-Film-Co/Projects/MOUSE/Research/` — partially exists, structure needs formalization
- **Target newspapers:** Gettysburg Times, York Daily Record, The Evening Sun, LancasterOnline (Pennsylvania regional papers)
- **Time period:** Primarily 1975–2025, heavy focus on 1970s-80s wrestling coverage
- **OCR challenge:** 1970s-80s newspaper scans with multi-column layouts — high accuracy is important for searching and quoting
- **newspapers-com-scraper:** Untested Node.js dependency — needs early validation
- **Cookie behavior:** Newspapers.com session duration unknown — cookie management must be robust with clear re-login prompts
- **Chris has:** Newspapers.com Publisher Extra subscription, possibly LancasterOnline and York Daily Record digital subscriptions

## Constraints

- **Language:** Python 3.11+ for CLI and orchestration; Node.js 18+ only for newspapers-com-scraper subprocess
- **OCR engine:** GLM-OCR via Ollama (primary), Tesseract (fallback) — both local, no cloud APIs
- **Storage:** ~5 GB for tooling (GLM-OCR model ~2 GB, Playwright browsers, Node deps, Python deps)
- **Rate limiting:** 5-second delays between fetches to avoid anti-bot detection on Newspapers.com
- **Dependencies:** Ollama, Playwright, Google Chrome, Node.js — all must be installable via Homebrew

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python as primary language | Single language for CLI, pipeline, and OCR integration — simpler than polyglot | — Pending |
| GLM-OCR over cloud OCR | Local processing, no API costs, works offline on studio machine | — Pending |
| Node.js scraper as subprocess | Reuses existing newspapers-com-scraper rather than reimplementing in Python | — Pending |
| Obsidian-native output | Wikilinks, frontmatter, embeds — integrates with existing research workflow | — Pending |
| Full pipeline in v1 | Both URL archiving and bulk search — Chris needs both for active research | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-01 after initialization*
