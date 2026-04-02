# Phase 4: Research Graph + Hardening - Research

**Researched:** 2026-04-02
**Domain:** Python file I/O, Obsidian wikilink format, append-only vault writes
**Confidence:** HIGH

## Summary

Phase 4 adds a new `graph.py` module that hooks into the existing `archiver.py` pipeline after Step 5 (Export). The module performs three append-only vault operations: create/update a People note per person in `ArticleRecord.person`, create/update a Source note from `ArticleRecord.source_name`, and regenerate the master index `Research/Articles/_index.md` by scanning all `Articles/*/metadata.json` files.

All technical components are in-project: the patterns, data types, vault path, and file-write conventions are already established by `obsidian.py`. The only genuinely new problem is safe append-only section management — specifically, reading an existing `.md` file, finding the `## Articles` section, checking for duplicate wikilinks before appending, and writing back atomically. This is implemented via plain Python string parsing (no external libraries needed beyond `python-frontmatter` for People note header creation).

The index regeneration is a full-rebuild-from-scan pattern: read every `Articles/*/metadata.json`, group by person, sort reverse-chronological, and write `_index.md` from scratch. This is simpler than incremental updates and is the decided approach.

**Primary recommendation:** Implement `graph.py` with three public functions — `update_people_notes()`, `update_source_note()`, `regenerate_index()` — called sequentially from `archiver.py` after `write_metadata_json()`. All file writes use `Path.write_text(..., encoding="utf-8")` consistent with the rest of the codebase.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**People & Source Note Format**
- People note: `# <Name>` H1, `## Articles` section with backlinks as `- [[YYYY-MM-DD_slug|title]] (source, date)` — append-only, never overwrite existing content above `## Articles`
- Source note: `# <Publication>` H1, `## Articles` section with backlinks as `- [[YYYY-MM-DD_slug|title]] (date)` — append-only, same pattern as People notes
- When a People note already exists with custom content: append only to `## Articles` section — never touch anything above it (success criteria: "existing content is never overwritten")
- Graph update functions called from `archiver.py` after Step 5 (Export) — keeps all vault writes in the archive pipeline

**Master Index Format**
- Group by person with article counts: `## Dave McCollum (12 articles)` then reverse-chronological article list — matches success criteria exactly
- Full regenerate on every archive run — scan all `Articles/*/metadata.json`, rebuild from scratch — ensures consistency even if manual edits happen
- Articles with no person tag grouped under `## Unlinked Articles` at the bottom
- Index file location: `Research/Articles/_index.md` (matches success criteria path exactly)

**Person Detection & Edge Cases**
- Use the `person` field from article frontmatter (set by `--person` flag or existing metadata) — no NER/AI extraction, only explicit user-provided names
- If `--person` was not provided during archive: skip People note creation for that article — no guessing. Article still appears in Source note and index under "Unlinked"
- Before appending backlink, check if the exact article wikilink already exists in `## Articles` — skip if present (idempotent)
- New `graph.py` module — keeps vault-reading/writing (obsidian.py) separate from graph logic. Called from archiver.py

### Claude's Discretion
- Exact implementation of `## Articles` section parsing (regex vs string matching for existing backlinks)
- Error handling when vault directory structure is unexpected
- Whether to add `graph` as a standalone CLI command in addition to the auto-hook in archiver.py

### Deferred Ideas (OUT OF SCOPE)
- NLP-based person name extraction from OCR text (v2 consideration)
- OCR confidence scoring and automatic Tesseract cross-reference (OCR-V2-01)
- Saved search profiles (SRCH-V2-01)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GRAPH-01 | People notes (`Research/People/<name>.md`) auto-created on first reference with header and empty sections | `_ensure_people_note()` creates `# <Name>\n\n## Articles\n` if file absent; `People/` dir created with `mkdir(parents=True, exist_ok=True)` |
| GRAPH-02 | People notes auto-updated with article backlink entry under `## Articles` section (append-only, never overwrite existing content) | `_append_backlink()` finds `## Articles` marker, checks for duplicate wikilink, appends new line — string-split approach documented in Code Examples |
| GRAPH-03 | Source notes (`Research/Sources/<name>.md`) auto-created on first reference | Same pattern as GRAPH-01 but targeting `Research/Sources/<publication>.md` |
| GRAPH-04 | Source notes auto-updated with article backlink entry under `## Articles` section (append-only) | Same `_append_backlink()` logic reused for Source notes — single utility function covers both GRAPH-02 and GRAPH-04 |
| GRAPH-05 | Master index (`Research/Articles/_index.md`) auto-regenerated on each archive run, sorted reverse-chronological, grouped by person with article counts | `regenerate_index()` scans all `Articles/*/metadata.json`, groups by person, sorts by date desc, writes from scratch |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-frontmatter | 1.1.0 | Reading existing People/Source note frontmatter (if any) during note creation | Already in pyproject.toml; used in obsidian.py for write_article_note() |
| pathlib (stdlib) | 3.11+ | All Path operations: mkdir, glob, read_text, write_text | Established pattern throughout codebase |
| json (stdlib) | 3.11+ | Reading `metadata.json` files during index regeneration | Already used in obsidian.py is_duplicate() |
| re (stdlib) | 3.11+ | Wikilink duplicate detection in `## Articles` section | Already imported in obsidian.py |

### No New Dependencies
Phase 4 requires **zero new pip dependencies**. All necessary libraries (`python-frontmatter`, `pathlib`, `json`, `re`) are already installed. `graph.py` is a pure Python module using only what exists.

**Installation:** None required.

## Architecture Patterns

### Recommended Project Structure
```
src/mouse_research/
├── graph.py            # NEW — public functions: update_people_notes(), update_source_note(), regenerate_index()
├── archiver.py         # MODIFIED — call graph functions after Step 5
├── obsidian.py         # UNCHANGED — vault write patterns already here
└── types.py            # UNCHANGED — ArticleRecord already has .person, .source_name, .slug
```

```
Research/               # vault root (config.vault.path)
├── Articles/
│   ├── _index.md       # regenerated every archive run
│   └── <slug>/
│       ├── article.md
│       └── metadata.json
├── People/             # CREATED by graph.py on first use
│   └── <Name>.md
└── Sources/            # CREATED by graph.py on first use
    └── <Publication>.md
```

### Pattern 1: People/Source Note — Create If Absent, Then Append

The single safe pattern for append-only section management in a flat Markdown file:

```python
# Source: codebase conventions (obsidian.py) + stdlib string operations

def _append_backlink_to_note(note_path: Path, note_title: str, backlink_line: str) -> None:
    """Create note with ## Articles section if absent; append backlink if not duplicate."""
    if not note_path.exists():
        # First reference — create the note with header and empty section
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(
            f"# {note_title}\n\n## Articles\n\n",
            encoding="utf-8",
        )

    content = note_path.read_text(encoding="utf-8")

    # Idempotency check: skip if exact wikilink already present under ## Articles
    # Extract slug from backlink_line (e.g. "- [[slug|title]] (...)")
    # Check for slug occurrence anywhere after ## Articles marker
    articles_marker = "## Articles"
    marker_idx = content.find(articles_marker)
    if marker_idx == -1:
        # Section missing — append it
        content = content.rstrip("\n") + f"\n\n{articles_marker}\n\n"
        marker_idx = content.find(articles_marker)

    articles_section = content[marker_idx:]
    if backlink_line.strip() in articles_section:
        return  # Already present — idempotent, skip

    # Append backlink at end of file (after ## Articles section)
    updated = content.rstrip("\n") + f"\n{backlink_line}\n"
    note_path.write_text(updated, encoding="utf-8")
```

### Pattern 2: Index Regeneration — Full Scan + Rebuild

```python
# Source: codebase conventions (obsidian.py is_duplicate()) + stdlib

def regenerate_index(vault_path: str) -> None:
    """Scan all Articles/*/metadata.json, rebuild _index.md from scratch."""
    articles_dir = Path(vault_path) / "Articles"
    records: list[dict] = []

    for meta_file in sorted(articles_dir.glob("*/metadata.json")):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            records.append(meta)
        except (json.JSONDecodeError, OSError):
            continue

    # Sort reverse-chronological (None dates sort to bottom)
    records.sort(
        key=lambda r: r.get("date") or "0000-00-00",
        reverse=True,
    )

    # Group by person
    from collections import defaultdict
    by_person: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        persons = r.get("person") or []
        if persons:
            for p in persons:
                by_person[p].append(r)
        else:
            by_person["__unlinked__"].append(r)

    lines = ["# Article Index", "", f"_Last updated: {date_cls.today().isoformat()}_", ""]

    for person in sorted(p for p in by_person if p != "__unlinked__"):
        articles = by_person[person]
        # Re-sort this person's articles reverse-chronological
        articles_sorted = sorted(
            articles, key=lambda r: r.get("date") or "0000-00-00", reverse=True
        )
        lines.append(f"## {person} ({len(articles_sorted)} articles)")
        lines.append("")
        for r in articles_sorted:
            slug = r.get("slug", "unknown")
            title = r.get("title") or slug
            date = r.get("date") or "undated"
            source = r.get("source") or ""
            lines.append(f"- [[{slug}|{title}]] ({source}, {date})")
        lines.append("")

    if "__unlinked__" in by_person:
        unlinked = by_person["__unlinked__"]
        unlinked_sorted = sorted(
            unlinked, key=lambda r: r.get("date") or "0000-00-00", reverse=True
        )
        lines.append(f"## Unlinked Articles ({len(unlinked_sorted)} articles)")
        lines.append("")
        for r in unlinked_sorted:
            slug = r.get("slug", "unknown")
            title = r.get("title") or slug
            date = r.get("date") or "undated"
            source = r.get("source") or ""
            lines.append(f"- [[{slug}|{title}]] ({source}, {date})")
        lines.append("")

    index_path = articles_dir / "_index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
```

### Pattern 3: archiver.py Integration Point

After `write_metadata_json()` at the end of Step 5, add:

```python
# After Step 5 Export — graph hooks
from mouse_research.graph import update_graph

update_graph(record, config)
```

Where `update_graph()` is a single public entry point in `graph.py` that calls the three sub-operations in sequence, with per-operation exception handling so a graph failure never fails the archive.

### Anti-Patterns to Avoid
- **Overwriting entire People notes:** Read the file, find the section, append only — never `write_text()` the full content unless creating a new file. Existing content above `## Articles` (custom research notes) must survive every archive run.
- **Using frontmatter.loads() to parse People notes:** People notes may be plain Markdown without YAML frontmatter (user-created notes). Use plain string operations, not frontmatter library, for section detection.
- **Raising exceptions from graph operations into archiver:** Graph failures are non-fatal — archive must succeed even if graph update fails. Wrap each graph operation in try/except and log errors.
- **Accumulating a person's articles list in memory across articles:** Each `archive_url()` call is independent. The index always rebuilds from the full metadata.json scan — don't try to maintain a cumulative in-memory state.
- **Glob ordering assumption:** `articles_dir.glob("*/metadata.json")` order is filesystem-dependent. Always sort explicitly before processing for deterministic output.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown section parsing | Custom parser/AST | Plain string `find("## Articles")` + slice | No structured Markdown parsing needed — the section structure is fixed and user-controlled |
| Wikilink duplicate detection | Regex + state machine | `backlink_line.strip() in articles_section` | The exact backlink line format is deterministic (`[[slug|title]]`) — substring check is sufficient and correct |
| Sorted group-by | Custom sort/group logic | Python `sorted()` + `collections.defaultdict` | stdlib covers all needed cases |
| Atomic file writes | tmpfile + rename pattern | Direct `write_text()` | Single-user CLI tool on local filesystem — atomic rename adds complexity with no benefit |

**Key insight:** This phase is almost entirely string manipulation on local files. The hard problems (YAML frontmatter, Playwright, OCR, subprocess) were solved in prior phases. Phase 4 is simple I/O composition.

## Common Pitfalls

### Pitfall 1: Missing `## Articles` Section in Existing Notes
**What goes wrong:** User creates a People note manually in Obsidian without an `## Articles` section. `graph.py` calls `content.find("## Articles")` and gets `-1`, then either crashes or appends to the wrong place.
**Why it happens:** User-created notes don't follow the auto-generated template.
**How to avoid:** Always check `marker_idx == -1` and append the section if missing, then proceed normally.
**Warning signs:** `find()` returns -1 on a non-empty file.

### Pitfall 2: Person Name Casing Inconsistency Causing Duplicate Notes
**What goes wrong:** `--person "Dave McCollum"` creates `People/Dave McCollum.md`. A later run with `--person "dave mccollum"` creates `People/dave mccollum.md`. Two notes, no cross-linking.
**Why it happens:** `ArticleRecord.person` values come directly from `--person` CLI flags — no normalization.
**How to avoid:** Normalize person names to title case before constructing the file path: `name.strip().title()`. Document this normalization in graph.py. Alternatively, use the exact casing from the first archival — but normalization is more predictable.
**Warning signs:** Multiple People notes for the same person with different casing.

### Pitfall 3: Backlink Line Format Drift Breaking Idempotency Check
**What goes wrong:** Backlink format changes between runs (e.g., trailing space, date format changes), so the `in` check fails to detect the duplicate and appends a second copy.
**Why it happens:** The backlink line is assembled from `ArticleRecord` fields. If any field changes (title gets updated, date format changes), the assembled string differs from what was written previously.
**How to avoid:** Check for the slug wikilink `[[slug|` specifically, not the full line. The slug is stable; the title and date may vary.
**Warning signs:** Multiple entries for the same slug in a People or Source note.

### Pitfall 4: Source Name as Filename on macOS
**What goes wrong:** `source_name` values like "Lancaster New Era / Intelligencer Journal" contain `/` which is invalid in filenames. `Path(vault_path) / "Sources" / f"{source_name}.md"` raises an error or creates nested directories.
**Why it happens:** `detect_source()` in extractor.py returns human-readable publication names that may contain filesystem-invalid characters.
**How to avoid:** Sanitize the source name to a safe filename using the same pattern as `make_slug()` in obsidian.py — or use a simpler `re.sub(r'[/\\:*?"<>|]', '-', source_name)` for just the dangerous characters while preserving readability.
**Warning signs:** `FileNotFoundError` or unexpected directory creation when archiving Lancaster-sourced articles.

### Pitfall 5: Index Regeneration When Articles Directory Is Empty
**What goes wrong:** `regenerate_index()` is called on the first-ever archive run. `Articles/` exists (created in Phase 2) but may have no `metadata.json` files yet (article folder creation happens before graph hooks, so the just-archived article IS present — but this is a timing concern for the test environment).
**Why it happens:** Empty glob result — `list(articles_dir.glob("*/metadata.json"))` returns `[]`.
**How to avoid:** Handle empty result gracefully: write a minimal `_index.md` with a "No articles archived yet" message rather than crashing. The current-run article folder is written before graph hooks run, so in production the index always includes at least the current article.

## Code Examples

### Backlink Line Format (People note)
```python
# Source: 04-CONTEXT.md locked decision
# Format: - [[YYYY-MM-DD_slug|title]] (source, date)
backlink = f"- [[{record.slug}|{record.article_data.title}]] ({record.source_name}, {date_str})"
```

### Backlink Line Format (Source note)
```python
# Source: 04-CONTEXT.md locked decision
# Format: - [[YYYY-MM-DD_slug|title]] (date)
backlink = f"- [[{record.slug}|{record.article_data.title}]] ({date_str})"
```

### Safe Filename for Source Name
```python
# Re-use obsidian.py pattern; or a minimal sanitizer:
import re
def _safe_filename(name: str) -> str:
    """Strip filesystem-invalid chars from source/person names for use as filenames."""
    return re.sub(r'[/\\:*?"<>|]', '-', name).strip()
```

### People/Source Note Paths
```python
# Consistent with vault structure in 04-CONTEXT.md
people_dir = Path(config.vault.path) / "People"
source_dir = Path(config.vault.path) / "Sources"
people_note = people_dir / f"{_safe_filename(person_name)}.md"
source_note = source_dir / f"{_safe_filename(record.source_name)}.md"
```

### archiver.py integration (after write_metadata_json)
```python
# In archive_url(), after Step 5 write calls:
try:
    from mouse_research.graph import update_graph
    update_graph(record, config)
except Exception as e:
    logger.error("Graph update failed (non-fatal): %s", e, exc_info=True)
```

### Slug-based idempotency check (more robust than full-line match)
```python
# Check for slug presence in the ## Articles section, not the full formatted line
slug_wikilink = f"[[{record.slug}|"
articles_section = content[content.find("## Articles"):]
if slug_wikilink in articles_section:
    return  # Already present
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled Markdown AST for section management | Plain string `find()` + slice | Always | Markdown is too free-form for AST parsing at this scale; string ops are sufficient for fixed-structure notes |
| Separate graph update CLI command | Auto-hook in archiver pipeline | Decision in 04-CONTEXT.md | Graph always stays consistent; no manual graph rebuild step needed |

## Environment Availability

Phase 4 is code-only, modifying Python source files with zero external tool dependencies. All runtime dependencies are already installed from Phases 1-3.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python-frontmatter | People note creation | Yes | 1.1.0 (in pyproject.toml) | — |
| pathlib (stdlib) | All file I/O | Yes | 3.11+ | — |
| json (stdlib) | metadata.json reading | Yes | 3.11+ | — |
| Vault directory | Writing People/Source/Index | Yes | Exists at configured path | — |

**Missing dependencies with no fallback:** None.

## Open Questions

1. **Person name normalization policy**
   - What we know: `ArticleRecord.person` values come from `--person` CLI flags with no normalization
   - What's unclear: Should graph.py normalize to title case, or preserve the exact casing the user typed?
   - Recommendation: Apply `.strip().title()` normalization in `graph.py` before constructing the filename and note title. This prevents duplicate notes from casing accidents. Document the normalization behavior.

2. **Source note filename sanitization scope**
   - What we know: `detect_source()` returns human-readable names that may contain `/`, `:`, or other filesystem-invalid characters
   - What's unclear: Whether existing `source_name` values in the vault (from Phases 1-3 testing) already contain problem characters
   - Recommendation: Apply minimal sanitizer `re.sub(r'[/\\:*?"<>|]', '-', name)` for the filename, but use the original `source_name` as the note title (`# <source_name>`) for readability

3. **`graph` standalone CLI command**
   - What we know: CONTEXT.md marks this as Claude's discretion
   - What's unclear: Whether a `mouse-research graph` command would be useful for rebuilding graph notes after manual vault edits
   - Recommendation: Implement as a standalone `mouse-research graph` CLI command that calls `regenerate_index()` and optionally re-scans People/Source notes. Low implementation cost, high utility when user manually moves/edits vault files

## Sources

### Primary (HIGH confidence)
- `/Users/aumen-server/Projects/researchpapers/src/mouse_research/obsidian.py` — vault write patterns, Path conventions, `make_slug()`, `is_duplicate()` implementation
- `/Users/aumen-server/Projects/researchpapers/src/mouse_research/archiver.py` — 5-step pipeline structure, integration point after Step 5
- `/Users/aumen-server/Projects/researchpapers/src/mouse_research/types.py` — `ArticleRecord` field names (`person: list[str]`, `source_name: str`, `slug: str`)
- `/Users/aumen-server/Projects/researchpapers/src/mouse_research/config.py` — `config.vault.path` access pattern
- `.planning/phases/04-research-graph-hardening/04-CONTEXT.md` — locked format decisions, integration points, file paths

### Secondary (MEDIUM confidence)
- Python stdlib `collections.defaultdict`, `pathlib.Path.glob()`, `json.loads()` — standard patterns, no external verification needed

### Tertiary (LOW confidence)
- None — all findings are derived directly from existing codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; all patterns from existing codebase
- Architecture: HIGH — integration points explicitly specified in CONTEXT.md; code examples derived from live source files
- Pitfalls: HIGH — derived from codebase analysis (filename chars, section parsing, idempotency); one MEDIUM item is person name normalization (depends on real-world `source_name` values not yet observed)

**Research date:** 2026-04-02
**Valid until:** 2026-06-01 (stable stdlib + no external dependencies; very long shelf life)
