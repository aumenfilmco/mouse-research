---
phase: 02-single-url-archive-pipeline
plan: "06"
subsystem: cli
tags: [cli, archive, ocr, batch, typer]
dependency_graph:
  requires:
    - 02-05 (archiver.archive_url)
    - 02-04 (obsidian write_article_note, write_metadata_json)
    - 02-03 (ocr.ocr_image)
    - 02-02 (types.ArticleRecord, ArticleData, OcrResult)
    - 02-01 (config.get_config)
    - 02-00 (logger.setup_logging)
  provides:
    - archive Typer command (single URL + --file batch mode)
    - ocr Typer command (local image scan export)
  affects:
    - src/mouse_research/cli.py (sole file modified)
tech_stack:
  added: []
  patterns:
    - thin CLI layer — no business logic in command functions
    - all logic delegated to archiver.archive_url and ocr.ocr_image
    - lazy imports inside command bodies (avoids startup cost)
key_files:
  created: []
  modified:
    - src/mouse_research/cli.py
decisions:
  - "archive and ocr commands use lazy imports (inside function body) — consistent with existing install/doctor/login pattern"
  - "tag option named --tag (not --tags) to match Typer convention for repeatable options"
  - "_archive_file() continues on failure — does not call raise typer.Exit; logged by archiver"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-02"
  tasks_completed: 1
  tasks_checkpointed: 1
  files_modified: 1
---

# Phase 02 Plan 06: CLI Archive and OCR Commands Summary

**One-liner:** Typer `archive` (single URL + batch --file) and `ocr` commands wired to archiver.archive_url and ocr_image, completing the user-facing CLI layer.

## What Was Built

Added two Typer commands to `src/mouse_research/cli.py`, preserving all existing commands (install, doctor, login):

### `archive` command (ARCH-10, ARCH-11)

- **Single URL mode:** `mouse-research archive <url> --person "Name" --tags "tag1"`
  - Delegates entirely to `archiver.archive_url()`
  - Prints slug + folder path on success
  - Prints "Skipped: URL already in vault" on duplicate (exit 0)
  - Prints error and exits 1 on failure

- **Batch --file mode:** `mouse-research archive --file urls.txt`
  - Reads one URL per line, ignores blank lines and `#` comments
  - 5-second delay between fetches via `time.sleep(config.rate_limit_seconds)`
  - Prints `[N/total]` progress per URL
  - Continues on per-URL failure (no `raise typer.Exit` per URL)
  - Summarizes archived/skipped/failed counts at end
  - Points to `~/.mouse-research/logs/failures.jsonl` when failures exist

### `ocr` command

- **Usage:** `mouse-research ocr scan.jpg --person "Dave McCollum" --date 1986-03-15 --source "Gettysburg Times"`
- Validates image file exists before proceeding
- Validates date format (YYYY-MM-DD) with clear error message
- Calls `ocr_image()` for GLM-OCR/Tesseract/queue fallback
- Extracts title from first OCR line (falls back to filename stem)
- Creates vault folder, copies original image, writes ocr_raw.md
- Assembles `ArticleRecord` and calls `write_article_note` + `write_metadata_json`
- Prints slug, folder path, and OCR engine used

## Verification (Automated — Task 1)

All automated checks passed:

```
.venv/bin/python3 -m mouse_research.cli --help  → exit 0
```

Output confirmed all 5 commands listed: install, doctor, login, archive, ocr.

- `archive --help` shows: --file, --person, --tag, --verbose options
- `ocr --help` shows: --person, --source, --date, --tag, --verbose options
- `_archive_file()` contains `time.sleep(config.rate_limit_seconds)` — confirmed
- `_archive_file()` does NOT call `raise typer.Exit` on per-URL failure — confirmed

## Checkpoint: Human Verification Required (Task 2)

Task 2 is a `checkpoint:human-verify` gate requiring live end-to-end testing:

**Steps for the user to verify:**

1. `mouse-research --help` — confirms all 5 commands listed
2. `mouse-research archive "https://www.newspapers.com/image/46677507/" --person "Test Person" --verbose`
   — expects spinner, then "Archived: YYYY-MM-DD_newspapers-com_..." and folder path
3. Check vault folder contains: screenshot.png, article.md, ocr_raw.md, metadata.json, source.html
4. Re-run same URL — expects "Skipped: URL already in vault" (exit 0)
5. `mouse-research archive --file /tmp/test-urls.txt` with that URL — expects skip + summary
6. `mouse-research ocr --help` — confirms --person, --source, --date, --tag options

**Resume signal:** User types "approved" if all steps pass, or describes failures.

## Commits

| Task | Description | Commit |
|------|-------------|--------|
| Task 1 | Add archive and ocr commands to cli.py | 0add2ca |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — no hardcoded empty values or placeholder text in the added commands.

## Self-Check: PASSED

- `src/mouse_research/cli.py` exists and is modified
- Commit `0add2ca` exists in git log
- `--help` output confirms all 5 commands: install, doctor, login, archive, ocr
