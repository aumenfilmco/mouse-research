---
phase: 04-research-graph-hardening
verified: 2026-04-02T00:00:00Z
status: passed
score: 10/10 must-haves verified
re_verification: false
---

# Phase 4: Research Graph Hardening — Verification Report

**Phase Goal:** Every archived article automatically updates the relevant People notes, Source notes, and master index; failed batches can be retried; and the system prompts for re-login when a session expires mid-run
**Verified:** 2026-04-02
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A new People note is created at Research/People/<Name>.md when a person is referenced for the first time | VERIFIED | `update_people_notes` creates `Path(vault_path) / "People" / f"{_safe_filename(normalized)}.md"` on first call; `test_people_note_created_when_not_exists` passes |
| 2 | An existing People note receives a new backlink under ## Articles without losing any content above that section | VERIFIED | `_append_backlink_to_note` finds `## Articles` marker and appends only below it; `test_people_note_preserves_existing_content` and `test_people_note_appends_articles_section_when_missing` pass |
| 3 | A new Source note is created at Research/Sources/<Publication>.md when a source is referenced for the first time | VERIFIED | `update_source_note` creates `Path(vault_path) / "Sources" / f"{_safe_filename(record.source_name)}.md"`; `test_source_note_created_when_not_exists` passes |
| 4 | An existing Source note receives a new backlink under ## Articles without losing any content above that section | VERIFIED | Same `_append_backlink_to_note` helper; `test_source_note_idempotent` confirms no duplication |
| 5 | Running update_graph twice with the same article does not create duplicate backlinks (idempotent) | VERIFIED | Idempotency check via `f"[[{slug}|"` substring in Articles section; `test_people_note_idempotent` and `test_source_note_idempotent` pass, `content.count(f"[[{slug}|") == 1` asserted |
| 6 | Master index at Research/Articles/_index.md lists all articles grouped by person with counts, reverse-chronological | VERIFIED | `regenerate_index` full-rebuilds from `Articles/*/metadata.json`; `test_regenerate_index_groups_by_person_with_count` and `test_regenerate_index_reverse_chronological` pass |
| 7 | Articles with no person appear under Unlinked Articles in the index | VERIFIED | `by_person["__unlinked__"]` bucket; `test_regenerate_index_unlinked_articles` passes |
| 8 | archive_url() automatically calls update_graph() after Step 5 Export — no manual graph command needed | VERIFIED | `archiver.py` lines 209-214: lazy import + call inside `try/except Exception` after `write_metadata_json`; grep confirms 2 lines |
| 9 | A graph failure in archiver.py does not fail the archive — the ArchiveResult is still success=True | VERIFIED | `try/except Exception` block in archiver.py lines 210-214 catches all errors before `return ArchiveResult(... success=True)`; `test_update_graph_does_not_raise_on_failure` passes |
| 10 | mouse-research graph rebuilds the index and optionally re-scans People/Source notes | VERIFIED | `cli.py` lines 467-486: `@app.command() def graph(...)` calls `regenerate_index(config.vault.path)` with `--verbose` flag; CLI loads OK |

**Score:** 10/10 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mouse_research/graph.py` | People/Source note management and index regeneration; exports update_graph, update_people_notes, update_source_note, regenerate_index | VERIFIED | File exists, 271 lines, all 4 public functions present, imports from types.py and config.py |
| `tests/test_graph.py` | Unit tests for all graph operations; min 80 lines | VERIFIED | File exists, 375 lines, 22 test functions — all pass |
| `src/mouse_research/archiver.py` | Graph hook after Step 5; contains update_graph | VERIFIED | Lines 209-214 confirmed: lazy import + call inside try/except, BEFORE return ArchiveResult |
| `src/mouse_research/cli.py` | graph CLI command; contains def graph | VERIFIED | Lines 467-486 confirmed: `@app.command() def graph(...)` with regenerate_index call |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `src/mouse_research/graph.py` | `src/mouse_research/types.py` | ArticleRecord import | WIRED | `from mouse_research.types import ArticleRecord` at line 27 |
| `src/mouse_research/graph.py` | `src/mouse_research/config.py` | AppConfig import | WIRED | `from mouse_research.config import AppConfig` at line 26 |
| `src/mouse_research/archiver.py` | `src/mouse_research/graph.py` | lazy import of update_graph | WIRED | `from mouse_research.graph import update_graph` at line 211 inside try/except |
| `src/mouse_research/cli.py` | `src/mouse_research/graph.py` | lazy import of regenerate_index | WIRED | `from mouse_research.graph import regenerate_index` at line 478 inside graph command |
| `src/mouse_research/cli.py` (ocr) | `src/mouse_research/graph.py` | lazy import of update_graph | WIRED | `from mouse_research.graph import update_graph` at line 245 inside ocr command try/except |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `graph.py: regenerate_index` | `records` (list of dicts) | `articles_dir.glob("*/metadata.json")` — reads all metadata.json from vault Articles/ | Yes — filesystem glob + json.loads per file | FLOWING |
| `graph.py: update_people_notes` | `record.person`, `record.article_data`, `record.slug` | `ArticleRecord` passed from archiver.py after real archive pipeline | Yes — record is assembled from real fetch/extract/OCR pipeline | FLOWING |
| `graph.py: update_source_note` | `record.source_name`, `record.article_data.publish_date` | Same real `ArticleRecord` | Yes | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| graph.py imports all 4 public functions | `python -c "from mouse_research.graph import update_graph, update_people_notes, update_source_note, regenerate_index; print('imports OK')"` | "imports OK" | PASS |
| All 22 graph unit tests pass | `pytest tests/test_graph.py -x -v` | 22 passed, 0 failed | PASS |
| Full test suite passes (no regressions) | `pytest tests/ -x` | 65 passed, 0 failed | PASS |
| CLI loads with graph command present | `python -c "from mouse_research.cli import app; print('CLI loads OK')"` | "CLI loads OK" | PASS |
| update_graph wired in archiver.py | `grep -n "update_graph" archiver.py` | Lines 211-212 confirmed | PASS |
| graph command in cli.py | `grep -n "def graph" cli.py` | Line 468 confirmed | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| GRAPH-01 | 04-01-PLAN, 04-02-PLAN | People notes auto-created on first reference with header and empty sections | SATISFIED | `update_people_notes` creates `People/<Name>.md` with `# Name\n\n## Articles\n\n` header; test_people_note_created_when_not_exists passes |
| GRAPH-02 | 04-01-PLAN, 04-02-PLAN | People notes auto-updated with article backlink entry under ## Articles (append-only, never overwrite) | SATISFIED | `_append_backlink_to_note` appends only below ## Articles marker; idempotency via slug check; content-preservation test passes |
| GRAPH-03 | 04-01-PLAN, 04-02-PLAN | Source notes auto-created on first reference | SATISFIED | `update_source_note` creates `Sources/<SafeName>.md`; filename sanitized; H1 uses original name |
| GRAPH-04 | 04-01-PLAN, 04-02-PLAN | Source notes auto-updated with article backlink entry under ## Articles (append-only) | SATISFIED | Same `_append_backlink_to_note` path; idempotency confirmed; format is `- [[slug|title]] (date)` (no source in parens) |
| GRAPH-05 | 04-01-PLAN, 04-02-PLAN | Master index auto-regenerated on each archive run, sorted reverse-chronological, grouped by person with article counts | SATISFIED | `regenerate_index` called from `update_graph` which is called from archiver.py after every successful archive; full rebuild from metadata.json scan; groups with counts and reverse-chron sort |

No orphaned requirements. All 5 GRAPH requirement IDs are claimed by both 04-01-PLAN and 04-02-PLAN and have implementation evidence.

**Note on phase goal scope:** The phase goal statement references "failed batches can be retried" (BULK-08 / `retry-failures`) and "re-login when a session expires mid-run" (FOUND-05/FOUND-06). These were implemented in Phases 3 and 1 respectively — they are not GRAPH-series requirements and no plan in Phase 4 claims them. The PLAN frontmatter correctly scopes Phase 4 to GRAPH-01 through GRAPH-05 only. Both retry-failures and session re-login are verified present in the codebase (cli.py lines 393-464 and cookies.py respectively) from prior phases.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No TODOs, FIXMEs, placeholders, empty return stubs, or hardcoded empty data found in any of the three Phase 4 files.

---

### Human Verification Required

None. All must-haves are verifiable programmatically. The vault write behavior (creating real .md files in Obsidian) is covered by unit tests using tmp_path as a fake vault root.

---

## Gaps Summary

No gaps. All 10 observable truths verified, all 4 artifacts exist and are substantive and wired, all 5 key links confirmed, all 5 GRAPH requirements satisfied, 65 tests pass with no regressions.

---

_Verified: 2026-04-02_
_Verifier: Claude (gsd-verifier)_
