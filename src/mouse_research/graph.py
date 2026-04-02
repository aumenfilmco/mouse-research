"""Graph module for mouse-research pipeline.

Manages People notes, Source notes, and the master article index in the
Obsidian vault. All operations are append-only and idempotent.

Public API:
  update_graph(record, config)         -- Single entry point from archiver.py
  update_people_notes(record, vault)   -- Create/update Research/People/<Name>.md
  update_source_note(record, vault)    -- Create/update Research/Sources/<Pub>.md
  regenerate_index(vault)              -- Rebuild Research/Articles/_index.md

Design decisions (from 04-CONTEXT.md):
  - Person names normalized to title case to prevent duplicate notes (Pitfall 2)
  - Idempotency checked via slug presence ("[[slug|") not full line match (Pitfall 3)
  - Source filenames sanitized of filesystem-invalid chars; title uses original (Pitfall 4)
  - Graph failures are non-fatal — each sub-op wrapped in try/except (Anti-Pattern 3)
"""
import json
import logging
import re
from collections import defaultdict
from datetime import date as date_cls
from pathlib import Path

from mouse_research.config import AppConfig
from mouse_research.types import ArticleRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _safe_filename(name: str) -> str:
    """Sanitize filesystem-invalid characters from a name for use as a filename.

    Replaces /\\:*?"<>| with '-' and strips leading/trailing whitespace.
    The original name is preserved for note titles (H1 headings).
    """
    return re.sub(r'[/\\:*?"<>|]', "-", name).strip()


def _normalize_person(name: str) -> str:
    """Normalize a person name to title case.

    Prevents duplicate People notes from casing differences (e.g.
    "dave mccollum" and "Dave McCollum" map to the same file).
    """
    return name.strip().title()


def _append_backlink_to_note(
    note_path: Path,
    note_title: str,
    backlink_line: str,
    slug: str,
) -> None:
    """Core append-only logic for People and Source notes.

    1. Creates the note with header if it does not exist.
    2. Appends ## Articles section if missing.
    3. Checks for duplicate via slug ("[[slug|") — skips if already present.
    4. Appends the backlink line at end of file.

    Never overwrites existing content above ## Articles.
    """
    if not note_path.exists():
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(
            f"# {note_title}\n\n## Articles\n\n",
            encoding="utf-8",
        )

    content = note_path.read_text(encoding="utf-8")

    # Ensure ## Articles section exists
    articles_marker = "## Articles"
    marker_idx = content.find(articles_marker)
    if marker_idx == -1:
        content = content.rstrip("\n") + f"\n\n{articles_marker}\n\n"
        note_path.write_text(content, encoding="utf-8")
        marker_idx = content.find(articles_marker)

    # Idempotency: check for slug wikilink in the Articles section
    # Use "[[slug|" (not full line) — slug is stable; title/date may vary
    articles_section = content[marker_idx:]
    slug_wikilink = f"[[{slug}|"
    if slug_wikilink in articles_section:
        return  # Already present — skip

    # Append backlink at end of file
    updated = content.rstrip("\n") + f"\n{backlink_line}\n"
    note_path.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def update_people_notes(record: ArticleRecord, vault_path: str) -> None:
    """Create or update a People note for each person in record.person.

    Path: <vault_path>/People/<NormalizedName>.md
    Backlink format: - [[slug|title]] (source, date)

    If record.person is empty, returns immediately (no guessing).
    Person names are normalized to title case before use.
    """
    if not record.person:
        return

    date_str = (
        record.article_data.publish_date.isoformat()
        if record.article_data.publish_date
        else "undated"
    )
    backlink_line = (
        f"- [[{record.slug}|{record.article_data.title}]]"
        f" ({record.source_name}, {date_str})"
    )

    for person in record.person:
        normalized = _normalize_person(person)
        note_path = Path(vault_path) / "People" / f"{_safe_filename(normalized)}.md"
        _append_backlink_to_note(note_path, normalized, backlink_line, record.slug)


def update_source_note(record: ArticleRecord, vault_path: str) -> None:
    """Create or update the Source note for record.source_name.

    Path: <vault_path>/Sources/<SafeSourceName>.md
    Backlink format: - [[slug|title]] (date)  — no source in parenthetical

    The filename uses a sanitized version of source_name; the H1 heading uses
    the original unsanitized name for readability.
    """
    date_str = (
        record.article_data.publish_date.isoformat()
        if record.article_data.publish_date
        else "undated"
    )
    backlink_line = (
        f"- [[{record.slug}|{record.article_data.title}]]"
        f" ({date_str})"
    )

    note_path = (
        Path(vault_path) / "Sources" / f"{_safe_filename(record.source_name)}.md"
    )
    _append_backlink_to_note(
        note_path, record.source_name, backlink_line, record.slug
    )


def regenerate_index(vault_path: str) -> None:
    """Rebuild Research/Articles/_index.md from all Articles/*/metadata.json.

    Groups articles by person (alphabetical), then Unlinked Articles at the
    bottom. Within each group, articles are sorted reverse-chronological.
    Full rebuild on every call — ensures consistency even after manual vault edits.

    Handles missing or empty Articles directory gracefully.
    """
    articles_dir = Path(vault_path) / "Articles"
    index_path = articles_dir / "_index.md"

    # Gather all metadata records
    records: list[dict] = []
    if articles_dir.exists():
        for meta_file in sorted(articles_dir.glob("*/metadata.json")):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                records.append(meta)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Skipping unreadable metadata file %s: %s", meta_file, exc)

    # Handle empty case
    if not records:
        articles_dir.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            "# Article Index\n\n_No articles archived yet._\n",
            encoding="utf-8",
        )
        return

    # Sort all records reverse-chronological
    records.sort(key=lambda r: r.get("date") or "0000-00-00", reverse=True)

    # Group by person
    by_person: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        persons = r.get("person") or []
        if persons:
            for p in persons:
                by_person[p].append(r)
        else:
            by_person["__unlinked__"].append(r)

    # Build output
    lines = [
        "# Article Index",
        "",
        f"_Last updated: {date_cls.today().isoformat()}_",
        "",
    ]

    for person in sorted(p for p in by_person if p != "__unlinked__"):
        articles = by_person[person]
        articles_sorted = sorted(
            articles, key=lambda r: r.get("date") or "0000-00-00", reverse=True
        )
        lines.append(f"## {person} ({len(articles_sorted)} articles)")
        lines.append("")
        for r in articles_sorted:
            slug = r.get("slug", "unknown")
            title = r.get("title") or slug
            date_val = r.get("date") or "undated"
            source = r.get("source") or ""
            lines.append(f"- [[{slug}|{title}]] ({source}, {date_val})")
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
            date_val = r.get("date") or "undated"
            source = r.get("source") or ""
            lines.append(f"- [[{slug}|{title}]] ({source}, {date_val})")
        lines.append("")

    articles_dir.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines), encoding="utf-8")


def update_graph(record: ArticleRecord, config: AppConfig) -> None:
    """Single entry point called from archiver.py after Step 5 (Export).

    Calls update_people_notes, update_source_note, and regenerate_index in
    sequence. Each operation is wrapped in its own try/except — graph failures
    are non-fatal and must never fail the archive.
    """
    vault_path = config.vault.path

    try:
        update_people_notes(record, vault_path)
    except Exception:
        logger.error(
            "update_people_notes failed for slug=%s (non-fatal)", record.slug, exc_info=True
        )

    try:
        update_source_note(record, vault_path)
    except Exception:
        logger.error(
            "update_source_note failed for slug=%s (non-fatal)", record.slug, exc_info=True
        )

    try:
        regenerate_index(vault_path)
    except Exception:
        logger.error(
            "regenerate_index failed for slug=%s (non-fatal)", record.slug, exc_info=True
        )
