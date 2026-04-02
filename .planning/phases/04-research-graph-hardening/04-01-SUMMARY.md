---
phase: 04-research-graph-hardening
plan: "01"
subsystem: graph
tags: [graph, obsidian, people-notes, source-notes, index, idempotent]
dependency_graph:
  requires: [types.py, config.py, obsidian.py]
  provides: [graph.py — update_graph, update_people_notes, update_source_note, regenerate_index]
  affects: [archiver.py — integration point after Step 5]
tech_stack:
  added: []
  patterns:
    - Append-only section management via plain string find() + slice (no Markdown AST)
    - Slug-based idempotency check ("[[slug|") — more robust than full-line match
    - TestConfig subclass with init_settings-first source order for config override in tests
key_files:
  created:
    - src/mouse_research/graph.py
    - tests/test_graph.py
  modified: []
decisions:
  - Person names normalized to title case via .strip().title() before filename construction — prevents duplicate notes from casing differences
  - Idempotency detected by "[[slug|" substring in ## Articles section, not full backlink line — slug is stable; title/date may vary
  - Source filename sanitized with re.sub(r'[/\\:*?"<>|]', '-', name); H1 uses original unsanitized name for readability
  - update_graph wraps each sub-operation in independent try/except — graph failures are non-fatal per RESEARCH.md anti-patterns
metrics:
  duration: "2min"
  completed: "2026-04-02"
  tasks_completed: 1
  files_created: 2
  files_modified: 0
  tests_added: 22
---

# Phase 04 Plan 01: graph.py People/Source Notes and Index Regeneration Summary

**One-liner:** Append-only, idempotent People/Source note management and full-rebuild index regeneration using plain string operations on local Markdown files.

## What Was Built

Created `src/mouse_research/graph.py` with four public functions implementing GRAPH-01 through GRAPH-05:

- `update_people_notes(record, vault_path)` — Creates `Research/People/<Name>.md` per person, normalizes to title case, appends backlink `- [[slug|title]] (source, date)` under `## Articles`. Idempotent via slug check.
- `update_source_note(record, vault_path)` — Creates `Research/Sources/<SafeName>.md`, appends backlink `- [[slug|title]] (date)` (no source in parens — it IS the source). Filename sanitized; H1 uses original name.
- `regenerate_index(vault_path)` — Full rebuild of `Research/Articles/_index.md` from scanning all `Articles/*/metadata.json`. Groups by person alphabetically with article counts, Unlinked Articles at bottom, reverse-chronological within groups.
- `update_graph(record, config)` — Single entry point for archiver.py. Calls all three sub-operations with independent try/except; graph failures are non-fatal.

Created `tests/test_graph.py` with 22 tests covering all behaviors: creation, append, idempotency, multi-person, empty lists, missing sections, title case normalization, filename sanitization, index structure, unlinked articles, empty/missing directories, and failure tolerance.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TestConfig subclass needed for update_graph integration tests**
- **Found during:** Task 1 GREEN phase
- **Issue:** `AppConfig.settings_customise_sources` puts YamlConfigSettingsSource first, so `AppConfig(vault=VaultSettings(path=str(tmp_path)))` constructor kwargs were overridden by the real `~/.mouse-research/config.yaml`, causing `update_graph` to write to the real vault path instead of `tmp_path`.
- **Fix:** Used `TestConfig(AppConfig)` subclass with `settings_customise_sources` returning only `(init_settings,)` — same pattern documented in STATE.md Phase 1 decisions ("YAML override test uses TestConfig subclass").
- **Files modified:** `tests/test_graph.py`
- **Commit:** d48302e

## Known Stubs

None — all four public functions are fully implemented and wired. No placeholder data.

## Self-Check: PASSED

- `src/mouse_research/graph.py` — FOUND
- `tests/test_graph.py` — FOUND
- RED commit `bdb3194` — FOUND
- GREEN commit `d48302e` — FOUND
- All 22 tests pass: `pytest tests/test_graph.py` exits 0
