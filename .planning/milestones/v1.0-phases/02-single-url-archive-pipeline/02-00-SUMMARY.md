---
phase: 02-single-url-archive-pipeline
plan: "00"
subsystem: pipeline
tags: [lxml-html-clean, newspaper4k, trafilatura, dataclasses, types, python]

# Dependency graph
requires: []
provides:
  - lxml-html-clean installed in .venv (unblocks newspaper4k and trafilatura imports)
  - FetchResult dataclass (Playwright fetch output contract)
  - ArticleData dataclass (text extraction output contract)
  - OcrResult dataclass (OCR output contract)
  - ArticleRecord dataclass (complete article for Obsidian export)
affects:
  - 02-01 (fetcher — uses FetchResult)
  - 02-02 (extractor — uses ArticleData)
  - 02-03 (ocr — uses OcrResult)
  - 02-04 (archiver — uses ArticleRecord)
  - 02-05 (obsidian — uses ArticleRecord)
  - 02-06 (orchestrator — uses all dataclasses)

# Tech tracking
tech-stack:
  added:
    - lxml-html-clean>=0.4.4
  patterns:
    - "Shared pipeline contracts in src/mouse_research/types.py — all modules import from here"

key-files:
  created:
    - src/mouse_research/types.py
  modified:
    - pyproject.toml

key-decisions:
  - "lxml-html-clean placed after trafilatura in pyproject.toml for logical grouping — both newspaper4k and trafilatura require it"
  - "types.py fields match RESEARCH.md Pattern 1 exactly — no additional fields added to preserve downstream contract stability"

patterns-established:
  - "Pipeline contract pattern: all stage outputs are typed dataclasses in mouse_research.types — no ad-hoc dicts or untyped returns"

requirements-completed:
  - ARCH-01
  - ARCH-02
  - ARCH-03
  - ARCH-04
  - ARCH-05
  - ARCH-06
  - ARCH-07
  - ARCH-08
  - ARCH-09
  - ARCH-10
  - ARCH-11

# Metrics
duration: 1min
completed: 2026-04-02
---

# Phase 02 Plan 00: Dependencies and Pipeline Dataclass Contracts Summary

**lxml-html-clean installed in .venv and four typed pipeline dataclasses (FetchResult, ArticleData, OcrResult, ArticleRecord) defined as shared contracts for all Phase 2 modules**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-04-02T13:04:55Z
- **Completed:** 2026-04-02T13:05:53Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- lxml-html-clean>=0.4.4 added to pyproject.toml and installed — unblocks newspaper4k and trafilatura imports in all downstream plans
- src/mouse_research/types.py created with all four pipeline dataclasses matching RESEARCH.md Pattern 1 exactly
- Full wave 0 verification passed: all imports resolve cleanly in .venv

## Task Commits

Each task was committed atomically:

1. **Task 1: Add lxml-html-clean to pyproject.toml and install** - `9031146` (feat)
2. **Task 2: Create src/mouse_research/types.py with pipeline dataclasses** - `232a681` (feat)

## Files Created/Modified

- `pyproject.toml` - Added `lxml-html-clean>=0.4.4` dependency after trafilatura entry
- `src/mouse_research/types.py` - Four pipeline dataclasses: FetchResult, ArticleData, OcrResult, ArticleRecord

## Decisions Made

- lxml-html-clean placed after trafilatura in pyproject.toml for logical grouping (both newspaper4k and trafilatura require it as a dependency)
- types.py fields match RESEARCH.md Pattern 1 exactly — no additional fields added to preserve downstream contract stability across all six subsequent plans

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- nltk UserWarning emitted by newspaper4k on import ("nltk is not installed. Some NLP features will be unavailable.") — benign, NLP features are optional and not used by the pipeline. No action required.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 1 plans (02-01 fetcher, 02-02 extractor) can proceed immediately
- All four pipeline dataclasses are importable via `from mouse_research.types import ...`
- lxml-html-clean, newspaper4k, and trafilatura all verified importable in .venv
- No blockers

---
*Phase: 02-single-url-archive-pipeline*
*Completed: 2026-04-02*

## Self-Check: PASSED

- FOUND: src/mouse_research/types.py
- FOUND: pyproject.toml (with lxml-html-clean>=0.4.4)
- FOUND: 02-00-SUMMARY.md
- FOUND commit: 9031146 (feat: lxml-html-clean)
- FOUND commit: 232a681 (feat: types.py dataclasses)
- FOUND commit: 3ab3f55 (docs: plan metadata)
