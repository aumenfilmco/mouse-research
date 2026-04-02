# Phase 4: Research Graph + Hardening - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Every archived article automatically updates the relevant People notes, Source notes, and master index. The graph is built from explicit `--person` flags (no AI extraction). All vault writes are append-only and idempotent.

Requirements: GRAPH-01 through GRAPH-05

</domain>

<decisions>
## Implementation Decisions

### People & Source Note Format
- People note: `# <Name>` H1, `## Articles` section with backlinks as `- [[YYYY-MM-DD_slug|title]] (source, date)` — append-only, never overwrite existing content above `## Articles`
- Source note: `# <Publication>` H1, `## Articles` section with backlinks as `- [[YYYY-MM-DD_slug|title]] (date)` — append-only, same pattern as People notes
- When a People note already exists with custom content: append only to `## Articles` section — never touch anything above it (success criteria: "existing content is never overwritten")
- Graph update functions called from `archiver.py` after Step 5 (Export) — keeps all vault writes in the archive pipeline

### Master Index Format
- Group by person with article counts: `## Dave McCollum (12 articles)` then reverse-chronological article list — matches success criteria exactly
- Full regenerate on every archive run — scan all `Articles/*/metadata.json`, rebuild from scratch — ensures consistency even if manual edits happen
- Articles with no person tag grouped under `## Unlinked Articles` at the bottom
- Index file location: `Research/Articles/_index.md` (matches success criteria path exactly)

### Person Detection & Edge Cases
- Use the `person` field from article frontmatter (set by `--person` flag or existing metadata) — no NER/AI extraction, only explicit user-provided names
- If `--person` was not provided during archive: skip People note creation for that article — no guessing. Article still appears in Source note and index under "Unlinked"
- Before appending backlink, check if the exact article wikilink already exists in `## Articles` — skip if present (idempotent)
- New `graph.py` module — keeps vault-reading/writing (obsidian.py) separate from graph logic. Called from archiver.py

### Claude's Discretion
- Exact implementation of `## Articles` section parsing (regex vs string matching for existing backlinks)
- Error handling when vault directory structure is unexpected
- Whether to add `graph` as a standalone CLI command in addition to the auto-hook in archiver.py

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/mouse_research/obsidian.py` — `write_article_note()`, `write_metadata_json()`, `create_article_folder()`, `is_duplicate()`, `make_slug()` — all vault writing patterns established here
- `src/mouse_research/archiver.py` — `archive_url()` 5-step pipeline; graph hooks go after Step 5 (Export)
- `src/mouse_research/types.py` — `ArticleRecord` with `person: list[str]`, `source_name: str`, `slug: str`
- `src/mouse_research/config.py` — `AppConfig` with `vault.path` for vault root
- `python-frontmatter` — already used in obsidian.py for reading/writing YAML frontmatter

### Established Patterns
- Vault path: `config.vault.path` → `Research/Articles/<slug>/`
- People path will be: `config.vault.path` → `Research/People/<name>.md`
- Source path will be: `config.vault.path` → `Research/Sources/<publication>.md`
- Index path: `config.vault.path` → `Research/Articles/_index.md`
- All file writes use `Path.write_text(content, encoding="utf-8")`
- Metadata stored as JSON in `metadata.json` per article folder
- Wikilinks use `[[target]]` or `[[target|display]]` format (Obsidian standard)

### Integration Points
- `archiver.py` Step 5: after `write_article_note()` and `write_metadata_json()`, call graph update functions
- `ArticleRecord.person` — list of person names to create/update People notes for
- `ArticleRecord.source_name` — publication name to create/update Source note for
- `ArticleRecord.slug` — used in wikilink: `[[slug|title]]`
- All `Articles/*/metadata.json` files scanned for index regeneration

</code_context>

<specifics>
## Specific Ideas

- Success criteria #1: People notes at `Research/People/<name>.md` with backlink, never overwrite existing content
- Success criteria #2: Source notes at `Research/Sources/<publication>.md` with backlink under `## Articles`, append-only
- Success criteria #3: `Research/Articles/_index.md` sorted reverse-chronological, grouped by person with article counts
- Vault root: `/Users/aumen-server/Documents/Obsidian Vault/01-Aumen-Film-Co/Projects/MOUSE/Research/`

</specifics>

<deferred>
## Deferred Ideas

- NLP-based person name extraction from OCR text (v2 consideration)
- OCR confidence scoring and automatic Tesseract cross-reference (OCR-V2-01)
- Saved search profiles (SRCH-V2-01)

</deferred>
