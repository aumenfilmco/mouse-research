# Feature Landscape

**Domain:** Newspaper archiving and research pipeline CLI (documentary research)
**Project:** MOUSE Research Pipeline
**Researched:** 2026-04-01

---

## Table Stakes

Features users expect. Missing = tool feels incomplete or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Single-URL archiving | Core value proposition — one command, one article, done | Medium | Playwright fetch + screenshot + HTML capture |
| Text extraction from HTML | Articles have live HTML; extracting body text is baseline | Low | newspaper4k primary, Trafilatura fallback. Trafilatura F1=0.958 vs newspaper4k F1=0.949 |
| OCR for scanned newspaper images | 1970s-80s papers exist only as scans; without OCR the tool is useless for core research period | High | GLM-OCR (0.9B via Ollama) is SOTA at 94.62 on OmniDocBench; processes 0.67 img/sec on-device |
| Obsidian-native output | Target workflow is Obsidian; non-native output requires manual reformatting every time | Medium | YAML frontmatter + wikilinks + embedded screenshot |
| Correct frontmatter schema | Obsidian's dataview, search, and sorting depend on consistent field names | Low | Fields: title, date, publication, people, tags, source_url |
| Embedded screenshot in note | Screenshot is the canonical artifact for scanned articles; proves source fidelity | Low | Markdown embed syntax `![[filename.png]]` |
| Duplicate detection before archiving | Without dedup, bulk runs produce redundant notes and corrupt the index | Medium | URL normalization + hash-based dedup on content |
| Failure logging | Long batch runs will have failures; silent failures leave gaps in research | Low | Structured log with URL, error type, timestamp |
| YAML config file | Vault path, OCR settings, and rate limits change per machine; hardcoding breaks portability | Low | Single `config.yaml`; document every field |
| Cookie management for Newspapers.com | Site requires Publisher Extra auth; without robust cookie handling, scraping fails silently after session expiry | High | `browser.storage_state()` to JSON; detect 401/redirect and prompt re-login |
| Rate limiting between requests | Newspapers.com will block IPs without delays; loss of access would be catastrophic | Low | 5-second default delay; configurable |
| `doctor` health check command | 5+ external dependencies (Ollama, Chrome, Node, GLM-OCR model); without validation, debugging failures is slow | Low | Check each dep, report version, warn on missing |

---

## Differentiators

Features that set this tool apart. Not assumed, but high value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| GLM-OCR via Ollama (local, offline) | No cloud API costs, no data leaving the machine, works on studio network without internet | High | 0.9B model, ~2GB on disk, Apple Silicon compatible; Tesseract fallback for when Ollama is unavailable |
| Auto-maintained People notes | Articles about the same wrestler connect automatically; builds a research graph without manual linking | Medium | On archive, parse `people` frontmatter field, upsert People note with backlink list |
| Auto-maintained Source notes | One note per publication tracks all archived articles from that source; surfaces coverage density | Low | Same pattern as People notes; keyed on publication name |
| Auto-generated master article index | Single `Articles.md` with every archived article sorted by date; gives documentary overview | Low | Append on archive; re-generate from scratch on demand |
| Interactive review mode for bulk search | Researcher reviews search results before committing to archive; prevents archiving irrelevant hits | Medium | Display title/date/snippet, keyboard y/n/s(skip), then batch the accepted set |
| Bulk search via newspapers-com-scraper | Single command to search by keyword + date range + location across Pennsylvania regional papers | High | Wraps Node.js subprocess; untested dependency needs early validation |
| Auto-archive mode | Skip review for trusted queries (e.g., exact name searches); archive all results automatically | Low | `--auto` flag on bulk command; requires dedup to be solid first |
| Progress display for batch runs | Long bulk runs (50+ articles) need visual feedback to confirm work is happening | Low | `tqdm`-style progress bar with ETA and current URL |
| Standalone image OCR command | Researcher has physical clippings photographed on phone; needs to OCR these without a URL | Low | `mouse-research ocr <image>` — runs GLM-OCR, outputs markdown text |
| Structured retry mechanism | Transient failures (network, rate limit 429, Ollama timeout) should not require manual re-run of entire batch | Medium | Exponential backoff with jitter; max 3 retries; write failed URLs to retry queue file |
| Re-login prompt on cookie expiry | Newspapers.com session duration is unknown; expired cookies produce silent wrong results without a clear prompt | Medium | Detect auth redirect in Playwright, pause batch, open interactive login, resume |

---

## Anti-Features

Features to deliberately NOT build, with explicit rationale.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Web UI | Single user (Chris), CLI is sufficient, web UI adds deployment complexity and maintenance burden | Stay CLI; use rich terminal output for usability |
| RSS feed monitoring / always-on daemon | Requires a persistent service, launchd config, log rotation — overkill for active research workflow | Run searches on demand when researching a new subject |
| ArchiveBox / WARC format archiving | Too heavy: stores full browser state, screenshots, JS, CSS — gigabytes per article | Screenshot + extracted text in Obsidian is sufficient for quoting and citation |
| Full-text search engine | Obsidian's built-in search is sufficient for a single-user vault | Ensure OCR text lands in note body so Obsidian can index it |
| Zotero integration | Obsidian handles citation needs for documentary research; two systems creates sync complexity | Frontmatter fields cover publication metadata |
| Multi-project support | Hardcoded to MOUSE vault path keeps the tool simple and avoids config complexity | If another project needs this, fork or parameterize vault path in config |
| Cloud OCR APIs | Costs money per page, requires internet, sends historical newspaper images to third parties | GLM-OCR local is SOTA; Tesseract is sufficient fallback for clean scans |
| Automatic login / credential storage in code | Storing Newspapers.com credentials in plaintext is a security risk | Interactive browser login + saved storage state; user authenticates manually, cookies persist |
| Auto-tagging / NLP keyword extraction | newspaper4k supports this but output quality is too low for documentary research where precision matters | Researcher adds tags manually; frontmatter `tags` field is available |
| Newspaper layout segmentation (article boundary detection) | Segmenting multi-column scans into individual articles is a research-grade CV problem; high failure rate | Archive full page; let OCR extract all text; researcher identifies article boundaries in the note |

---

## Feature Dependencies

```
Cookie management → Bulk search (search requires auth session)
Cookie management → Single-URL archiving of Newspapers.com pages
Bulk search → Interactive review mode (search must return results to review)
Bulk search → Auto-archive mode (search must return results to archive)
Duplicate detection → Auto-archive mode (auto mode is only safe with dedup)
Duplicate detection → Bulk search pipeline (dedup at ingest, not after)
GLM-OCR (Ollama) → Standalone image OCR command
GLM-OCR (Ollama) → OCR during single-URL archiving (for scanned pages)
Text extraction (newspaper4k) → Single-URL archiving (for live HTML pages)
Failure logging → Retry mechanism (retry reads from failure log)
People notes → Master article index (both maintained by same archive event)
Source notes → Master article index (same)
YAML config → All commands (vault path must resolve before any write)
`doctor` command → none (standalone validation; no deps on other features)
```

---

## MVP Recommendation

Prioritize for first working version:

1. **Single-URL archiving** — core value, validates the full pipeline (fetch → OCR → Obsidian output)
2. **Cookie management** — required for Newspapers.com; must be solved early or nothing else works
3. **GLM-OCR via Ollama** — differentiator and primary use case; test on 1970s scan quality before committing
4. **Correct Obsidian output** (frontmatter + wikilinks + embed) — output correctness is non-negotiable
5. **`doctor` command** — 5+ external dependencies make environment validation essential from day one
6. **Bulk search** — Chris needs this for active research; but validate newspapers-com-scraper works first

Defer until bulk search is validated:
- **Interactive review mode** — can ship with auto-archive only initially; add review UX after scraper is stable
- **Structured retry mechanism** — useful but can be a manual re-run initially
- **Auto-maintained People/Source notes** — useful but not blocking; can be added after core pipeline works

---

## Phase-Specific Feature Notes

| Phase | Features | Key Risk |
|-------|----------|----------|
| Foundation / single-URL | Fetch, OCR, Obsidian export, cookie mgmt, doctor | GLM-OCR accuracy on 1970s scans; newspapers-com-scraper subprocess |
| Bulk pipeline | Bulk search, dedup, batch archive, progress, retry | newspapers-com-scraper reliability; rate limit detection |
| Research graph | People notes, Source notes, master index | Schema consistency across all previously archived articles |
| Hardening | Retry mechanism, re-login prompt, failure log | Cookie expiry behavior on Newspapers.com is unknown |

---

## Sources

- [newspapers-com-scraper GitHub (njraladdin)](https://github.com/njraladdin/newspapers-com-scraper) — search params, output format, concurrency options
- [GLM-OCR on Ollama](https://ollama.com/library/glm-ocr) — model availability, deployment
- [GLM-OCR GitHub (zai-org)](https://github.com/zai-org/GLM-OCR) — benchmarks (94.62 OmniDocBench), throughput specs
- [Trafilatura evaluation docs](https://trafilatura.readthedocs.io/en/latest/evaluation.html) — F1 score comparison vs newspaper4k
- [Structured OCR for Newspapers: YOLOX + Vision LLMs (Webkul)](https://webkul.com/blog/structured-ocr-newspaper-pipeline/) — newspaper OCR pipeline patterns
- [Playwright cookie/session management (ScrapingAnt)](https://scrapingant.com/blog/playwright-set-cookies) — storage_state pattern for session persistence
- [Obsidian OCR plugins landscape](https://publish.obsidian.md/hub/02+-+Community+Expansions/02.04+Auxiliary+Tools+by+Category/OCR+Tools) — confirmed Obsidian-native OCR patterns
