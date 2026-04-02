---
phase: 03-bulk-search-batch-archive
verified: 2026-04-02T16:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 3: Bulk Search + Batch Archive Verification Report

**Phase Goal:** Users can search Newspapers.com from the CLI, review results interactively, and send selected articles (or all results) into the archive pipeline with progress tracking and deduplication against the existing vault
**Verified:** 2026-04-02T16:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Calling `call_scraper('Dave McCollum', '1975-1985', 'Pennsylvania')` invokes `node scraper-wrapper.js` with `--keyword`, `--years`, `--location us-pa` and returns a list of SearchResult dataclasses | VERIFIED | `searcher.py:108` builds cmd with all args; `searcher.py:119` resolves "Pennsylvania" to "us-pa"; `call_scraper` returns list of dicts, `search_and_filter` returns `list[SearchResult]`; test `test_calls_node_with_keyword`, `test_location_appended_after_resolve` pass |
| 2  | Results with URLs already in the Obsidian vault are filtered out before being returned | VERIFIED | `searcher.py:166` calls `is_duplicate(config.vault.path, url)` for each result; `excluded_count` tracks filtered items; test `test_filters_duplicates_and_returns_count` passes |
| 3  | Location strings like 'Pennsylvania' are mapped to 'us-pa' before passing to the scraper | VERIFIED | `searcher.py:60-61` `resolve_location()` normalizes and looks up `LOCATION_CODES`; `LOCATION_CODES["pennsylvania"] = "us-pa"`; tests `test_pennsylvania_maps_to_us_pa`, `test_case_insensitive`, `test_whitespace_stripped` pass |
| 4  | `parse_selection('1,3,5-12,all', 20)` returns correct 0-based index lists | VERIFIED | `searcher.py:183-246` handles "all", comma-separated, ranges; tests `test_all_returns_full_range`, `test_single_items`, `test_range_and_items` pass; bounds-validation tests pass |
| 5  | `mouse-research search 'Dave McCollum'` displays a Rich Table with columns #, Newspaper, Date, Location, URL, Matches and a footer showing excluded duplicate count | VERIFIED | `cli.py:248-281` `_display_results()` creates Table with all 6 columns and prints excluded count if > 0; `search --help` exits 0 |
| 6  | `mouse-research search 'McCollum' --years 1975-1985 --location Pennsylvania` passes correct filters to the scraper | VERIFIED | `cli.py:333-334` declares `--years` and `--location` options; `cli.py:357` passes them directly to `search_and_filter()`; `search_and_filter` passes to `call_scraper` which resolves location and appends all flags |
| 7  | After results display, user is prompted with 'Enter selection (e.g. 1,3,5-12,all):' and selected articles are archived with a Rich Progress bar | VERIFIED | `cli.py:374` `Prompt.ask("Enter selection (e.g. 1,3,5-12,all)")`; `cli.py:376` calls `parse_selection`; `cli.py:382` calls `_batch_archive_with_progress`; progress bar uses `Progress(SpinnerColumn, BarColumn, TaskProgressColumn, TextColumn)` at `cli.py:299-306` |
| 8  | `mouse-research search 'McCollum' --auto-archive` archives all results without interactive prompt, with progress bar and completion summary | VERIFIED | `cli.py:369-371` `if auto_archive:` path skips Prompt, builds `urls_and_titles` from all results, calls `_batch_archive_with_progress`; summary printed at `cli.py:325` |
| 9  | `mouse-research retry-failures` reads failures.jsonl, reprocesses URLs, removes successes from the log, and prints archived/still-failed counts | VERIFIED | `cli.py:385-456` reads FAILURE_LOG, deduplicates by URL, loops with progress bar calling `archive_url`, populates `still_failed` list, rewrites FAILURE_LOG with only unresolved records at `cli.py:451-454`; prints counts at `cli.py:456` |
| 10 | Ctrl+C during batch archive prints partial summary without corrupting failures.jsonl | VERIFIED | `cli.py:319-323` `except KeyboardInterrupt:` prints partial archived/failed/remaining counts then `raise typer.Exit(code=130)`; FAILURE_LOG is not written inside the batch loop — only `archive_url` in `archiver.py` writes to it on individual failure, leaving prior log intact |
| 11 | Zero results prints 'No results found' with suggestion to broaden search | VERIFIED | `cli.py:362-365` `if not results:` prints `"No results found for '{query}'."` and `"Try broadening your search — remove --years or --location filters."` |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mouse_research/searcher.py` | Search subprocess call, result parsing, dedup filtering, location mapping, selection parsing | VERIFIED | 246 lines; exports `SearchResult`, `call_scraper`, `search_and_filter`, `parse_selection`, `resolve_location`, `LOCATION_CODES`, `ScraperError`, `_parse_scraper_output` |
| `src/mouse_research/cli.py` | search command, retry_failures command, `_batch_archive_with_progress`, `_display_results` | VERIFIED | 460 lines (211 lines added in Plan 02); all 4 new functions present; both commands registered in Typer app |
| `tests/test_searcher.py` | Unit tests covering all Plan 01 behaviors | VERIFIED | 305 lines; 38 tests across 6 test classes; all pass in 0.06s |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/mouse_research/searcher.py` | `~/.mouse-research/scraper-wrapper.js` | `subprocess.run(['node', scraper_wrapper_path, '--keyword', ...])` | WIRED | `searcher.py:21` defines `SCRAPER_WRAPPER = Path.home() / ".mouse-research" / "scraper-wrapper.js"`; `searcher.py:108` builds cmd with it; `searcher.py:124` calls `subprocess.run(cmd, ..., timeout=300)` |
| `src/mouse_research/searcher.py` | `src/mouse_research/obsidian.py` | `is_duplicate(vault_path, url)` for dedup filtering | WIRED | `searcher.py:19` imports `from mouse_research.obsidian import is_duplicate`; `searcher.py:166` calls `is_duplicate(config.vault.path, url)` in filter loop |
| `src/mouse_research/cli.py` | `src/mouse_research/searcher.py` | `from mouse_research.searcher import search_and_filter, parse_selection` | WIRED | `cli.py:349` lazy import inside `search()` function; both `search_and_filter` and `parse_selection` called at `cli.py:357` and `cli.py:376` |
| `src/mouse_research/cli.py` | `src/mouse_research/archiver.py` | `archive_url(url, config, person=persons, tags=tags)` in batch loop | WIRED | `cli.py:292` lazy import inside `_batch_archive_with_progress`; `cli.py:313` calls `archive_url(url, config, person=persons, tags=tags)` |
| `src/mouse_research/cli.py` | `src/mouse_research/logger.py` | `FAILURE_LOG` path for retry-failures reading | WIRED | `cli.py:393` lazy import `from mouse_research.logger import setup_logging, FAILURE_LOG`; `cli.py:400,406,451` uses `FAILURE_LOG` to check existence, read, and rewrite |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `cli.py:_display_results()` | `results: list[SearchResult]` | `search_and_filter()` → `call_scraper()` → `subprocess.run(node scraper-wrapper.js)` | Yes — live subprocess call to Node.js scraper; JSON-line stdout parsed into SearchResult dataclasses | FLOWING |
| `cli.py:retry_failures()` | `records: list[dict]` | `FAILURE_LOG.read_text()` → real file at `~/.mouse-research/logs/failures.jsonl` | Yes — reads actual JSONL file written by `log_failure()` in archiver | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `search --help` exits 0 and shows all flags | `typer.testing.CliRunner().invoke(app, ['search', '--help'])` | Exit 0; shows --years, --location, --auto-archive, --person, --tag, --verbose | PASS |
| `retry-failures --help` exits 0 | `typer.testing.CliRunner().invoke(app, ['retry-failures', '--help'])` | Exit 0; shows --verbose | PASS |
| All searcher unit tests pass | `pytest tests/test_searcher.py -x -v` | 38 passed in 0.06s | PASS |
| Import of all 8 exports from searcher.py | `from mouse_research.searcher import SearchResult, call_scraper, search_and_filter, parse_selection, resolve_location, LOCATION_CODES, ScraperError, _parse_scraper_output` | Import succeeds (verified by test file importing all 8) | PASS |

Note: Live search behavior (actual Newspapers.com query) cannot be spot-checked without network access and a valid session — flagged in Human Verification section.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BULK-01 | 03-01 | `mouse-research search "<query>"` calls newspapers-com-scraper as Node.js subprocess and returns structured search results | SATISFIED | `searcher.py:82-135` `call_scraper()` invokes `node scraper-wrapper.js`; `search_and_filter()` returns `list[SearchResult]` |
| BULK-02 | 03-01 | Search results deduplicated against existing articles in Obsidian vault | SATISFIED | `searcher.py:164-168` filters via `is_duplicate(config.vault.path, url)`; returns excluded count |
| BULK-03 | 03-01 | Search results filterable by year range (`--years`), location (`--location`) | SATISFIED | `call_scraper()` accepts `years` and `location` params; `searcher.py:110-119` appends `--years` and `--location` to subprocess cmd |
| BULK-04 | 03-02 | Interactive review mode displays numbered results; user selects which to archive | SATISFIED | `cli.py:248-281` displays Rich Table with 1-based numbers; `cli.py:373-382` prompts for selection with `parse_selection()` |
| BULK-05 | 03-02 | `--auto-archive` flag feeds all search results directly into archiving pipeline | SATISFIED | `cli.py:335` `--auto-archive` option; `cli.py:369-371` auto-archive path bypasses prompt |
| BULK-06 | 03-02 | Batch archiving with 5-second rate limiting, progress bar, failure continuation | SATISFIED | `cli.py:310` `time.sleep(config.rate_limit_seconds)` (5s default); `cli.py:299-306` Rich Progress bar; loop continues on failure at `cli.py:314-317` |
| BULK-07 | 03-02 | Batch summary at completion showing archived/failed counts | SATISFIED | `cli.py:325` prints `"Done: {archived} archived, {failed} failed"`; `cli.py:456` for retry-failures |
| BULK-08 | 03-02 | `mouse-research retry-failures` reprocesses URLs from failures.jsonl | SATISFIED | `cli.py:385-456` reads FAILURE_LOG, retries via `archive_url()`, rewrites log with unresolved entries only |

All 8 requirements SATISFIED. No orphaned requirements — every BULK-0x ID claimed in plan frontmatter maps to verified implementation.

---

### Anti-Patterns Found

No anti-patterns found. Scanned `src/mouse_research/searcher.py` and `src/mouse_research/cli.py` for TODO/FIXME/placeholder comments, empty return stubs, and hardcoded empty data — none present.

---

### Human Verification Required

#### 1. Live Search Result Display

**Test:** With scraper-wrapper.js installed (`mouse-research install`), run `mouse-research search 'Dave McCollum' --years 1975-1985 --location Pennsylvania --max-pages 1` from a terminal with an active Newspapers.com session.
**Expected:** Rich Table appears with columns #, Newspaper, Date, Location, URL, Matches. Results show Pennsylvania newspapers from 1975-1985. Footer shows excluded count if any already in vault.
**Why human:** Requires live Node.js scraper subprocess, active Newspapers.com browser session (cookies), and network access — cannot be verified programmatically.

#### 2. Interactive Selection Flow

**Test:** Run a search that returns results, then enter `1,3` at the selection prompt.
**Expected:** Two articles archive, progress bar advances twice with 5-second delay between, completion summary shows `Done: 2 archived, 0 failed`.
**Why human:** Requires real interactive TTY prompt input, live archiver, and observable progress bar rendering.

#### 3. Ctrl+C Partial Summary

**Test:** Start `mouse-research search 'test' --auto-archive` with multiple results and press Ctrl+C after the first article archives.
**Expected:** Terminal prints `Interrupted. Partial results:` with correct counts; failures.jsonl not corrupted.
**Why human:** Requires live signal delivery during subprocess execution; cannot simulate KeyboardInterrupt in a non-interactive test runner reliably.

#### 4. retry-failures Log Rewrite

**Test:** Manually populate `~/.mouse-research/logs/failures.jsonl` with two entries, one with a URL that now exists in the vault (would skip) and one genuinely failed. Run `mouse-research retry-failures`.
**Expected:** The resolved/skipped URL is removed from failures.jsonl; the genuinely failed URL remains; output shows `1 resolved, 1 still failed`.
**Why human:** Requires a populated failures log and vault state; involves file mutation that should be visually confirmed.

---

### Gaps Summary

No gaps. All must-haves verified across both plans. The phase goal is fully achieved: the CLI supports `mouse-research search` with Rich Table display, interactive selection, `--auto-archive`, 5-second rate-limited progress bar, Ctrl+C partial summary, zero-results guidance, and `mouse-research retry-failures` with FAILURE_LOG rewrite. Deduplication against the vault and location code mapping are implemented and unit-tested at 38/38.

---

_Verified: 2026-04-02T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
