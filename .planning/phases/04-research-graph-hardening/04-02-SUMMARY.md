---
phase: 04-research-graph-hardening
plan: "02"
subsystem: graph
tags: [graph, archiver, cli, pipeline-integration, non-fatal]
dependency_graph:
  requires: [graph.py — update_graph, regenerate_index]
  provides: [archiver.py — graph hook after Step 5, cli.py — graph command, cli.py — ocr graph hook]
  affects: [archive pipeline, ocr command]
tech_stack:
  added: []
  patterns:
    - Lazy import inside try/except for non-fatal graph hook (consistent with existing cli.py lazy import pattern)
    - Graph failures logged at ERROR level but never propagate — ArchiveResult.success=True preserved
key_files:
  created: []
  modified:
    - src/mouse_research/archiver.py
    - src/mouse_research/cli.py
decisions:
  - Graph hook uses lazy import inside try/except — consistent with Phase 2 decision (archive and ocr commands use lazy imports inside function body)
  - graph CLI command calls only regenerate_index (not People/Source updates) — People/Source notes are article-specific and require an ArticleRecord; index is the only standalone rebuild operation
metrics:
  duration: "37s"
  completed: "2026-04-02"
  tasks_completed: 1
  files_created: 0
  files_modified: 2
  tests_added: 0
---

# Phase 04 Plan 02: Graph Pipeline Integration and CLI Command Summary

**One-liner:** Non-fatal graph hook wired after archiver Step 5 and ocr command export, plus standalone `mouse-research graph` command for manual index rebuilds.

## What Was Built

Modified `src/mouse_research/archiver.py`:
- Added Step 6 graph hook after `write_metadata_json(folder, record)`, BEFORE the `return ArchiveResult` line
- Hook uses lazy import (`from mouse_research.graph import update_graph`) inside a `try/except Exception` block
- Graph failure is caught and logged at ERROR level — `ArchiveResult(success=True)` return is unchanged

Modified `src/mouse_research/cli.py`:
- Added identical graph hook after `write_metadata_json(folder, record)` in the `ocr` command, using same lazy import + try/except pattern
- Added new `graph` command (`@app.command()`) after `retry_failures`, before `if __name__ == "__main__":`
- `graph` command calls `regenerate_index(config.vault.path)` with `--verbose` flag support
- Displays: `[green]Index rebuilt:[/green] Research/Articles/_index.md` on success

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all hooks and commands are fully wired to real graph.py functions.

## Self-Check: PASSED

- `src/mouse_research/archiver.py` — FOUND, contains `update_graph(record, config)` after Step 5
- `src/mouse_research/cli.py` — FOUND, contains `update_graph` in ocr and `def graph` command
- Commit `87c74fb` — FOUND
- All 65 tests pass: `pytest tests/ -x` exits 0
- `grep "update_graph" src/mouse_research/archiver.py` — returns 2 lines (import + call)
- `grep "def graph" src/mouse_research/cli.py` — returns 1 line
- `grep "regenerate_index" src/mouse_research/cli.py` — returns 1 line inside graph command
- Graph hook in archiver.py is inside `try/except Exception` block — confirmed
- Graph hook appears AFTER `write_metadata_json` and BEFORE `return ArchiveResult` — confirmed
- `ArchiveResult` return unchanged — confirmed
