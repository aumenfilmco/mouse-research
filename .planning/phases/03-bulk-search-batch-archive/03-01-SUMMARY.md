---
phase: 03-bulk-search-batch-archive
plan: 01
subsystem: search
tags: [subprocess, scraper, newspapers-com, dedup, location-mapping, selection-parsing]

requires:
  - phase: 02-single-url-archive-pipeline
    provides: is_duplicate() for vault dedup checking, AppConfig with vault.path

provides:
  - SearchResult dataclass with 6 typed fields
  - call_scraper() subprocess integration with Node.js scraper-wrapper.js
  - search_and_filter() with vault dedup via is_duplicate()
  - resolve_location() mapping state names to Newspapers.com region codes
  - parse_selection() for "1,3,5-12,all" user input parsing
  - ScraperError with Cloudflare detection and login hint

affects: [03-02-cli-search-command, 03-bulk-search-batch-archive]

tech-stack:
  added: []
  patterns:
    - "subprocess.run with timeout=300 for Node.js scraper integration"
    - "JSON-line stdout protocol: one dict per result line, skip malformed silently"
    - "Cloudflare detection in stderr triggers login hint error message"
    - "1-based display numbering assigned post-dedup-filter"

key-files:
  created:
    - src/mouse_research/searcher.py
    - tests/test_searcher.py
  modified: []

key-decisions:
  - "ScraperError wraps all subprocess failures; Cloudflare-specific branch adds login hint"
  - "resolve_location() strips/lowercases before lookup, passes through unknown codes unchanged"
  - "parse_selection() raises ValueError on out-of-bounds and non-numeric input (0 is invalid — 1-based user input)"

patterns-established:
  - "searcher.py is the sole Python-to-Node.js boundary — all scraper calls go through call_scraper()"
  - "search_and_filter() is the public entry point for CLI; call_scraper() is internal utility"

requirements-completed: [BULK-01, BULK-02, BULK-03]

duration: 4min
completed: 2026-04-02
---

# Phase 03 Plan 01: Searcher Module Summary

**Python scraper integration module with subprocess call to Node.js scraper-wrapper.js, JSON-line parsing, vault dedup filtering, location code mapping, and selection string parsing**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-02T15:18:33Z
- **Completed:** 2026-04-02T15:20:53Z
- **Tasks:** 1 (TDD: RED -> GREEN)
- **Files modified:** 2

## Accomplishments

- SearchResult dataclass importable and typed with all 6 fields
- call_scraper() invokes `node scraper-wrapper.js` via subprocess with correct CLI args, timeout=300, Cloudflare detection
- search_and_filter() deduplicates against Obsidian vault using is_duplicate(), returns (results, excluded_count) with 1-based numbering
- resolve_location() maps e.g. "Pennsylvania" -> "us-pa", passes through existing codes unchanged
- parse_selection() handles "all", comma-separated items, and ranges like "5-8" with full bounds validation
- 38 passing unit tests with subprocess and is_duplicate mocked

## Task Commits

1. **Task 1: Create searcher.py with scraper integration, dedup, location mapping, and selection parsing** - `57a6afa` (feat)

**Plan metadata:** (docs commit — see below)

_TDD: RED (import error) -> GREEN (38/38 passing)_

## Files Created/Modified

- `src/mouse_research/searcher.py` - Full search module: SearchResult, LOCATION_CODES, resolve_location, ScraperError, call_scraper, _parse_scraper_output, search_and_filter, parse_selection
- `tests/test_searcher.py` - 38 unit tests across 6 test classes, all mocked (no live subprocess calls)

## Decisions Made

- ScraperError wraps all subprocess failures; "Cloudflare" in stderr triggers a specific message with `mouse-research login newspapers.com` hint — consistent with existing Cloudflare handling in fetcher.py
- resolve_location() strips and lowercases before lookup, unknown inputs pass through unchanged — safe for callers passing already-resolved region codes
- parse_selection() treats 0 as invalid (user-facing 1-based input), raises descriptive ValueError for all invalid cases

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- searcher.py is fully functional and ready for CLI consumption in Plan 02
- All 6 exports (SearchResult, call_scraper, search_and_filter, parse_selection, resolve_location, LOCATION_CODES) are importable
- search_and_filter() is the intended entry point for cli.py `search` command
- Requires scraper-wrapper.js to be present at ~/.mouse-research/scraper-wrapper.js (installed by installer.py / doctor command)

---
*Phase: 03-bulk-search-batch-archive*
*Completed: 2026-04-02*
