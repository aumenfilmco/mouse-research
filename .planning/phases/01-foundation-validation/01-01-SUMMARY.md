---
phase: 01-foundation-validation
plan: "01"
subsystem: infra
tags: [python, typer, rich, hatchling, pip, cli, packaging]

# Dependency graph
requires: []
provides:
  - pip-installable mouse-research Python package (src layout, hatchling backend)
  - Typer CLI entry point with stub install/doctor/login commands
  - All 12 Python dependencies declared in pyproject.toml
  - tests/ package structure
affects: [all subsequent plans — depends on pip-installable package existing]

# Tech tracking
tech-stack:
  added:
    - typer 0.24.1
    - rich 14.3.3
    - pydantic-settings 2.13.1
    - playwright 1.58.0
    - ollama 0.6.1
    - pytesseract 0.3.13
    - Pillow 12.2.0
    - httpx 0.28.1
    - opencv-python 4.13.0.92
    - newspaper4k 0.9.5
    - trafilatura 2.0.0
    - python-frontmatter 1.1.0
    - hatchling (build backend)
  patterns:
    - "src layout: src/mouse_research/ with wheel target in pyproject.toml"
    - "Typer app defined in cli.py, exported as `app`, wired via entry_points console_scripts"
    - "Virtual environment at .venv/ (required due to externally-managed macOS Python)"

key-files:
  created:
    - pyproject.toml
    - src/mouse_research/__init__.py
    - src/mouse_research/cli.py
    - tests/__init__.py
    - .gitignore
  modified: []

key-decisions:
  - "httpx pinned >=0.27.0 instead of >=0.28.1 — RESEARCH.md rated 0.28.1 MEDIUM confidence (not directly verified on PyPI); 0.27.0 is safe lower bound"
  - "Virtual environment (.venv/) required — macOS Python is externally-managed (PEP 668), direct pip install rejected by system"

patterns-established:
  - "Venv pattern: all Python commands use /Users/aumen-server/Projects/researchpapers/.venv/bin/ prefix"
  - "CLI structure: commands are top-level @app.command() functions in cli.py with Rich console output"

requirements-completed: [SETUP-02]

# Metrics
duration: 4min
completed: 2026-04-01
---

# Phase 01 Plan 01: Project Scaffold Summary

**pip-installable mouse-research CLI with Typer entry point wired via hatchling src layout, all 12 Python dependencies declared, and install/doctor/login stub commands working**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-01T23:03:56Z
- **Completed:** 2026-04-01T23:07:24Z
- **Tasks:** 2
- **Files modified:** 5 created, 0 modified

## Accomplishments
- pyproject.toml with hatchling build backend, all 12 Python dependencies, and mouse-research entry point
- src/mouse_research package with Typer CLI app exporting install, doctor, login stub commands
- `pip install -e .` succeeds in .venv; `mouse-research --help` shows all 3 commands
- tests/__init__.py package marker ready for pytest

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pyproject.toml** - `81b39ee` (chore)
2. **Task 2: Create src/mouse_research package with Typer CLI stub** - `a6d75f9` (feat)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified
- `pyproject.toml` - Build config, 12 Python deps, mouse-research entry point wired to mouse_research.cli:app
- `src/mouse_research/__init__.py` - Package marker, __version__ = "0.1.0"
- `src/mouse_research/cli.py` - Typer app with install/doctor/login stub commands
- `tests/__init__.py` - Empty test package marker
- `.gitignore` - Excludes .venv/, __pycache__, build artifacts

## Decisions Made
- **httpx pinned >=0.27.0**: RESEARCH.md flagged 0.28.1 as MEDIUM confidence (from WebSearch, not directly verified on PyPI). Using >=0.27.0 as safe lower bound — actual install resolved to 0.28.1 which is fine.
- **Virtual environment required**: macOS Python 3.14 is externally-managed (PEP 668) — direct `pip3 install -e .` rejected by system. Created .venv at project root; all subsequent plans must use `.venv/bin/` commands.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created Python virtual environment for externally-managed macOS Python**
- **Found during:** Task 2 (pip install -e . step)
- **Issue:** macOS Python 3.14 is externally-managed (PEP 668) — `pip3 install -e .` failed with "externally-managed-environment" error
- **Fix:** Created `.venv/` with `python3 -m venv .venv`, ran install via `.venv/bin/pip install -e .`, added `.venv/` to .gitignore
- **Files modified:** .gitignore (created)
- **Verification:** `mouse-research --help` prints all 3 commands from .venv binary
- **Committed in:** a6d75f9 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary infrastructure fix — all subsequent plans must use `.venv/bin/` prefix for Python/CLI commands.

## Issues Encountered
- pip wheel build for lxml (newspaper4k transitive dependency) took ~2 minutes to compile from source — expected on first install

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Package installable and CLI entry point working — all subsequent plans can `from mouse_research.X import Y`
- Key constraint for future plans: use `.venv/bin/mouse-research` and `.venv/bin/python3` (not system python3 or bare mouse-research)
- No blockers for Plan 02 (foundation modules: config, logging, cookie management)

## Self-Check: PASSED

- FOUND: pyproject.toml
- FOUND: src/mouse_research/__init__.py
- FOUND: src/mouse_research/cli.py
- FOUND: tests/__init__.py
- FOUND commit: 81b39ee (chore: pyproject.toml)
- FOUND commit: a6d75f9 (feat: CLI package)
