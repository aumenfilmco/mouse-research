---
phase: 03-bulk-search-batch-archive
plan: 02
subsystem: cli
tags: [typer, rich, search, batch-archive, retry, progress-bar, keyboard-interrupt]

requires:
  - phase: 03-bulk-search-batch-archive
    plan: 01
    provides: search_and_filter, parse_selection, ScraperError, SearchResult
  - phase: 02-single-url-archive-pipeline
    provides: archive_url, ArchiveResult, AppConfig

provides:
  - search command with Rich Table display, interactive selection, --auto-archive mode
  - retry-failures command reading/rewriting failures.jsonl
  - _display_results() helper
  - _batch_archive_with_progress() helper with rate limiting and Ctrl+C handling

affects: [03-bulk-search-batch-archive, cli.py]

tech-stack:
  added: []
  patterns:
    - "Lazy imports inside command function bodies (consistent with existing install/doctor/login/archive/ocr pattern)"
    - "Rich Progress with SpinnerColumn+BarColumn+TaskProgressColumn+TextColumn for batch archiving"
    - "KeyboardInterrupt caught inside progress context — exits with code 130"
    - "retry-failures rewrites FAILURE_LOG in-place: read all, retry all, write back only still_failed"

key-files:
  created: []
  modified:
    - src/mouse_research/cli.py

key-decisions:
  - "retry-failures uses inline loop (not _batch_archive_with_progress) to track per-record success/failure for FAILURE_LOG rewrite"
  - "result.skipped counts as archived/resolved in retry-failures (already in vault = resolved)"
  - "_display_results uses /image/ URL fragment detection for compact URL display in table"

requirements-completed: [BULK-04, BULK-05, BULK-06, BULK-07, BULK-08]

duration: 1min
completed: 2026-04-02
---

# Phase 03 Plan 02: Search and Retry-Failures CLI Commands Summary

**Typer search command with Rich Table results display, interactive selection, --auto-archive batch mode, rate-limited progress bar, Ctrl+C partial summary, and retry-failures command that rewrites failures.jsonl with only unresolved entries**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-04-02T15:22:44Z
- **Completed:** 2026-04-02T15:23:50Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- `search` command registered in Typer app with query, --years, --location, --auto-archive, --person, --tag, --verbose flags
- Rich Table display with columns: #, Newspaper, Date, Location, URL (compact /image/ snippet), Matches; footer shows excluded duplicate count
- Zero results path prints "No results found for '{query}'" and broadening suggestion
- Interactive mode: prompts "Enter selection (e.g. 1,3,5-12,all)", calls parse_selection(), archives selected articles
- --auto-archive mode: archives all results without interactive prompt
- `_batch_archive_with_progress()`: Rich Progress bar (Spinner+Bar+Task+Text), 5-second rate limiting, Ctrl+C prints partial summary and exits 130
- `retry-failures` command: reads failures.jsonl, deduplicates by URL, reprocesses via archive_url(), rewrites log with only still-failed records; prints resolved/still-failed counts
- All existing commands (install, doctor, login, archive, ocr) unchanged
- All 38 Plan 01 searcher tests still pass

## Task Commits

1. **Task 1: Add search and retry-failures CLI commands** - `5e760b9` (feat)

## Files Created/Modified

- `src/mouse_research/cli.py` — Extended with _display_results(), _batch_archive_with_progress(), search command, retry-failures command (211 lines added)

## Decisions Made

- retry-failures uses an inline loop rather than `_batch_archive_with_progress` in order to track per-record outcomes and rewrite failures.jsonl with only unresolved entries
- result.skipped treated as "resolved" in retry-failures (already in vault means the failure is no longer actionable)
- URL display in table uses `/image/` fragment detection for compact representation, truncates to 40 chars

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `src/mouse_research/cli.py` exists and contains all required functions
- Commit `5e760b9` present in git log
- `search --help` exits 0 and shows all flags
- `retry-failures --help` exits 0
- All 14 acceptance criteria checks passed
- All 38 Plan 01 tests pass
