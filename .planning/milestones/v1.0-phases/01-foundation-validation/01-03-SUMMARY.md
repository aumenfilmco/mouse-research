---
phase: 01-foundation-validation
plan: "03"
subsystem: infra
tags: [python, node, npm, rich, installer, doctor, health-check, cli]

# Dependency graph
requires:
  - 01-01 (pip-installable package, .venv setup, Typer CLI stubs)
  - 01-02 (get_config(), AppConfig with vault/ocr/browser settings)
provides:
  - install_node_deps() creating ~/.mouse-research/package.json and running npm install
  - MOUSE_DIR constant (Path.home() / ".mouse-research")
  - run_doctor() printing Rich table with 10 dependency checks
  - Working `mouse-research install` and `mouse-research doctor` commands
affects:
  - all subsequent plans — doctor validates the environment before pipeline work

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy imports in CLI commands: `from mouse_research.X import Y` inside command body keeps startup fast"
    - "sys.executable for subprocess checks: ensures Playwright check uses the same venv Python, not system python3"
    - "statvfs for disk space: os.statvfs(Path.home()) gives free bytes on the home partition"

key-files:
  created:
    - src/mouse_research/installer.py
    - src/mouse_research/doctor.py
  modified:
    - src/mouse_research/cli.py

key-decisions:
  - "sys.executable instead of 'python3' in _check_playwright_browsers(): ensures subprocess uses the venv Python where playwright is installed, not the externally-managed system Python"

# Metrics
duration: 4min
completed: 2026-04-01
---

# Phase 01 Plan 03: Install and Doctor Commands Summary

**install_node_deps() sets up ~/.mouse-research/node_modules via npm, and run_doctor() prints a Rich table checking Python, Node.js, npm, Ollama, GLM-OCR, Tesseract, Playwright, scraper, vault path, and disk space**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-01T23:16:11Z
- **Completed:** 2026-04-01T23:20:00Z
- **Tasks:** 3
- **Files modified:** 2 created, 1 modified

## Accomplishments

- `src/mouse_research/installer.py` — MOUSE_DIR constant, install_node_deps() creates ~/.mouse-research/package.json (newspapers-com-scraper 1.1.0) and runs npm install with 120s timeout; returns bool success
- `src/mouse_research/doctor.py` — 10 health checks via _check_command, _check_ollama_running, _check_glm_ocr, _check_playwright_browsers, _check_vault_path, _check_disk_space, _check_node_scraper; run_doctor() prints Rich table with green/red indicators, returns bool
- `src/mouse_research/cli.py` — install and doctor stubs replaced with real implementations using lazy imports; typer.Exit(code=1) on failure
- `mouse-research doctor` confirmed running: Python 3.14, Node.js v24.14.1, npm 11.11.0, Playwright chromium, and 101.6 GB disk all pass; Ollama/Tesseract/scraper/vault fail as expected (not yet installed)

## Task Commits

1. **Task 1: Create installer.py** — `61fe343` (feat)
2. **Task 2: Create doctor.py** — `f7e81cc` (feat)
3. **Task 3: Wire install and doctor in cli.py** — `909240a` (feat)

## Files Created/Modified

- `src/mouse_research/installer.py` — MOUSE_DIR, PACKAGE_JSON, install_node_deps()
- `src/mouse_research/doctor.py` — 8 private check functions + run_doctor()
- `src/mouse_research/cli.py` — install and doctor commands wired to real implementations

## Decisions Made

- **sys.executable in _check_playwright_browsers()**: Plan used `"python3"` as the subprocess command which would invoke the externally-managed system Python (not the venv where playwright is installed). Changed to `sys.executable` so the check runs in the correct Python environment. This is a Rule 1 (bug) fix — the check would always fail or check the wrong installation with system python3.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used sys.executable instead of "python3" in _check_playwright_browsers()**
- **Found during:** Task 2 (writing doctor.py)
- **Issue:** Plan specified `subprocess.run(["python3", "-c", ...])` but macOS python3 is the externally-managed system Python (PEP 668) — playwright is installed in .venv, not system Python. The check would always fail or silently check the wrong environment.
- **Fix:** Changed to `sys.executable` which resolves to the running venv Python at runtime.
- **Files modified:** src/mouse_research/doctor.py
- **Commit:** f7e81cc

## Known Stubs

- `login` command in cli.py remains a stub (plan 01-04 will implement it) — this is intentional, not a blocker for this plan's goals.

## Self-Check: PASSED

- FOUND: src/mouse_research/installer.py
- FOUND: src/mouse_research/doctor.py
- FOUND commit 61fe343 (installer.py)
- FOUND commit f7e81cc (doctor.py)
- FOUND commit 909240a (cli.py wiring)
- `mouse-research doctor` runs without import errors, prints 10-row Rich table
