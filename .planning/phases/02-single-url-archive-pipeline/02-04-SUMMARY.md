---
phase: 02-single-url-archive-pipeline
plan: "04"
subsystem: obsidian-writer
tags: [obsidian, vault, frontmatter, duplicate-detection, slug]
dependency_graph:
  requires:
    - 02-00  # types.py — ArticleRecord dataclass
  provides:
    - obsidian.py — Obsidian vault folder creation, note writing, metadata, duplicate detection
  affects:
    - 02-05  # archiver.py — calls create_article_folder, write_article_note, write_metadata_json, is_duplicate
tech_stack:
  added:
    - python-frontmatter 1.1.0 — YAML frontmatter generation via frontmatter.dumps()
  patterns:
    - frontmatter.Post(body, **meta) + frontmatter.dumps(post) for note writing
    - Path.glob("*/metadata.json") for duplicate scanning
    - urllib.parse.urlparse for URL normalization (strip query params, keep path)
key_files:
  created:
    - src/mouse_research/obsidian.py
  modified: []
decisions:
  - "frontmatter.dumps() used (not frontmatter.dump()) — dumps() returns a string; dump() requires a binary file handle and is not suitable for write_text() workflow"
  - "person field passed as list to frontmatter.Post — locked by user decision D-04 in 02-CONTEXT.md"
  - "_normalize_url strips query params but keeps path intact — Newspapers.com article ID is embedded in the URL path, not query string"
metrics:
  duration: 69s
  completed: 2026-04-02
  tasks_completed: 1
  files_changed: 1
---

# Phase 02 Plan 04: Obsidian Vault Writer Summary

## One-liner

Obsidian vault writer using python-frontmatter with person-as-list frontmatter, wikilinks in body, embedded screenshot, and URL-normalized duplicate detection via metadata.json scanning.

## What Was Built

`src/mouse_research/obsidian.py` implements the final output stage of the pipeline — transforming a complete `ArticleRecord` into the on-disk folder structure that Obsidian reads.

### Functions Exported

| Function | Purpose |
|----------|---------|
| `make_slug(pub_date, source_name, title)` | Generates `YYYY-MM-DD_source-slug_title-slug` folder name |
| `create_article_folder(vault_path, slug)` | Creates `<vault>/Articles/<slug>/` with `exist_ok=True` |
| `write_article_note(folder, record)` | Writes `article.md` with YAML frontmatter + locked note format |
| `write_metadata_json(folder, record)` | Writes `metadata.json` for duplicate detection |
| `is_duplicate(vault_path, url)` | Scans `vault/Articles/*/metadata.json` for matching normalized URL |
| `_normalize_url(url)` | Strips query params, keeps path (Newspapers.com ID in path) |

### Locked Note Format (from 02-CONTEXT.md decisions)

- YAML frontmatter: `person` (list), `source` (string), `date`, `url`, `tags` (list), `captured` (date), `extraction` (method)
- H1 title heading
- `**People:**` wikilinks in body (not frontmatter)
- `**Source:**` wikilink in body
- `![[screenshot.png]]` embedded below title
- `## Article Text` section (OCR primary for Newspapers.com; web extract otherwise)
- `## Web Extract` section only when BOTH OCR and web text are present
- `## Notes` section (empty) at bottom for research notes

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all functions are fully implemented. Note that `write_article_note` always uses `screenshot.png` as the embed filename; the actual screenshot file copy is handled by the archiver (plan 02-05).

## Self-Check: PASSED

- `src/mouse_research/obsidian.py` exists: FOUND
- Commit `4681e03` exists: FOUND
- Import verification passed: `obsidian ok`
- `frontmatter.dumps()` is the only frontmatter call (comment mentions `.dump()` but no code uses it)
- `person=record.person` passes list value
- `## Notes` present in `body_parts`
- `![[screenshot.png]]` present in `body_parts`
- `*/metadata.json` glob pattern present in `is_duplicate`
