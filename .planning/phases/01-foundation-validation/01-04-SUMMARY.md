---
phase: 01-foundation-validation
plan: "04"
subsystem: auth
tags: [python, playwright, cookies, authentication, cli]

# Dependency graph
requires:
  - 01-01 (pip-installable package, .venv setup, Typer CLI stubs)
  - 01-02 (get_config(), AppConfig with browser settings)
  - 01-03 (cli.py with install and doctor wired)
provides:
  - interactive_login(): opens visible Chromium for manual login, saves via storage_state()
  - load_cookies(): returns cookie file path when present, None otherwise
  - check_auth(): headless pre-flight session validity check
  - COOKIE_DIR constant (Path.home() / ".mouse-research" / "cookies")
  - Working `mouse-research login <domain>` command
affects:
  - Phase 2 fetching — load_cookies() and check_auth() are prerequisites for authenticated Playwright sessions

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Playwright storage_state() for cookie save/load: pass path= at context.storage_state() to save; pass storage_state= at browser.new_context() to load — NOT launch_persistent_context() (Playwright bug #36139)"
    - "Lazy imports in CLI commands: `from mouse_research.cookies import interactive_login` inside command body keeps startup fast"
    - "Pre-flight auth check via URL redirect detection: navigate to domain root, check if current_url contains 'sign-in', 'login', or 'signin'"

key-files:
  created:
    - src/mouse_research/cookies.py
  modified:
    - src/mouse_research/cli.py

key-decisions:
  - "storage_state() over launch_persistent_context(): Playwright bug #36139 causes session cookies not to persist with launch_persistent_context(); storage_state() save/load is the correct approach per official auth docs"

# Metrics
duration: 2min
completed: 2026-04-01
---

# Phase 01 Plan 04: Cookie Management Summary

**interactive_login() opens visible Chromium at the domain's login page and saves session cookies via Playwright storage_state(); load_cookies() and check_auth() provide authenticated context loading and pre-flight session validation for Phase 2 fetching**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-01T23:21:00Z
- **Completed:** 2026-04-01T23:22:14Z
- **Tasks:** 2
- **Files modified:** 1 created, 1 modified

## Accomplishments

- `src/mouse_research/cookies.py` — COOKIE_DIR constant, LOGIN_URLS mapping for 4 domains, cookie_path(), interactive_login() (opens headless=False Chromium, waits for manual login, saves via storage_state()), load_cookies() (returns path string or None), check_auth() (headless pre-flight check for login redirects, refreshes cookies on success)
- `src/mouse_research/cli.py` — login stub replaced with real implementation using lazy import of interactive_login; passes console instance; exits code 1 on failure
- `mouse-research login --help` confirmed: shows `DOMAIN` argument with help text

## Task Commits

1. **Task 1: Create cookies.py** — `441e91c` (feat)
2. **Task 2: Wire login command in cli.py** — `cdcd9a2` (feat)

## Files Created/Modified

- `src/mouse_research/cookies.py` — COOKIE_DIR, LOGIN_URLS, cookie_path(), interactive_login(), load_cookies(), check_auth()
- `src/mouse_research/cli.py` — login command wired to cookies.interactive_login

## Decisions Made

- **storage_state() over launch_persistent_context()**: Playwright GitHub issue #36139 documents that launch_persistent_context() does not persist session cookies correctly. The storage_state() save/load pattern is the official recommendation for auth state management. This is a hard constraint from CLAUDE.md technology stack docs.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — the login command is now fully wired. Actual browser behavior (cookie persistence, session duration) requires a live manual test with a real Newspapers.com account, which is by design (interactive login cannot be automated in tests).

## Self-Check: PASSED

- FOUND: src/mouse_research/cookies.py
- FOUND: src/mouse_research/cli.py (login wired)
- FOUND commit 441e91c (cookies.py)
- FOUND commit cdcd9a2 (cli.py login wiring)
- `mouse-research login --help` shows DOMAIN argument — verified
