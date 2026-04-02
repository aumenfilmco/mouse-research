"""Tests for graph.py — People notes, Source notes, and master index regeneration.

All tests use tmp_path as a fake vault root.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from mouse_research.graph import (
    regenerate_index,
    update_graph,
    update_people_notes,
    update_source_note,
)
from mouse_research.types import ArticleData, ArticleRecord, OcrResult


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_record(
    slug: str = "2024-01-15_gettysburg-times_wrestler-wins",
    title: str = "Wrestler Wins Championship",
    source: str = "Gettysburg Times",
    person: list[str] | None = None,
    pub_date: date | None = date(2024, 1, 15),
) -> ArticleRecord:
    """Return an ArticleRecord with the given fields and sensible defaults."""
    return ArticleRecord(
        slug=slug,
        url="https://example.com/article",
        source_name=source,
        article_data=ArticleData(
            title=title,
            publish_date=pub_date,
        ),
        ocr_result=OcrResult(),
        screenshot_path=Path("/tmp/screenshot.png"),
        page_image_path=None,
        article_image_path=None,
        person=person if person is not None else [],
        tags=[],
        captured=date(2024, 1, 20),
    )


# ---------------------------------------------------------------------------
# update_people_notes tests
# ---------------------------------------------------------------------------

def test_people_note_created_when_not_exists(tmp_path):
    """A new People note is created with header when person has no file yet."""
    record = _make_record(person=["Dave Mccollum"])
    update_people_notes(record, str(tmp_path))

    note = tmp_path / "People" / "Dave Mccollum.md"
    assert note.exists()
    content = note.read_text(encoding="utf-8")
    assert content.startswith("# Dave Mccollum\n")
    assert "## Articles" in content
    assert "[[2024-01-15_gettysburg-times_wrestler-wins|Wrestler Wins Championship]]" in content
    assert "(Gettysburg Times, 2024-01-15)" in content


def test_people_note_backlink_format(tmp_path):
    """Backlink line format: - [[slug|title]] (source, date)."""
    record = _make_record(person=["Dave Mccollum"])
    update_people_notes(record, str(tmp_path))

    note = tmp_path / "People" / "Dave Mccollum.md"
    content = note.read_text(encoding="utf-8")
    expected_line = "- [[2024-01-15_gettysburg-times_wrestler-wins|Wrestler Wins Championship]] (Gettysburg Times, 2024-01-15)"
    assert expected_line in content


def test_people_note_multiple_persons(tmp_path):
    """Multiple persons each get their own People note."""
    record = _make_record(person=["Dave Mccollum", "Jane Smith"])
    update_people_notes(record, str(tmp_path))

    assert (tmp_path / "People" / "Dave Mccollum.md").exists()
    assert (tmp_path / "People" / "Jane Smith.md").exists()


def test_people_note_empty_person_list(tmp_path):
    """Empty person list creates no People notes."""
    record = _make_record(person=[])
    update_people_notes(record, str(tmp_path))

    people_dir = tmp_path / "People"
    assert not people_dir.exists() or not any(people_dir.iterdir())


def test_people_note_idempotent(tmp_path):
    """Calling update_people_notes twice does not duplicate the backlink."""
    record = _make_record(person=["Dave Mccollum"])
    update_people_notes(record, str(tmp_path))
    update_people_notes(record, str(tmp_path))

    note = tmp_path / "People" / "Dave Mccollum.md"
    content = note.read_text(encoding="utf-8")
    slug = record.slug
    # Should appear exactly once
    assert content.count(f"[[{slug}|") == 1


def test_people_note_preserves_existing_content(tmp_path):
    """Existing content above ## Articles is not overwritten."""
    people_dir = tmp_path / "People"
    people_dir.mkdir(parents=True)
    note = people_dir / "Dave Mccollum.md"
    existing = "# Dave Mccollum\n\nCustom research notes about Dave.\n\n## Articles\n\n"
    note.write_text(existing, encoding="utf-8")

    record = _make_record(person=["Dave Mccollum"])
    update_people_notes(record, str(tmp_path))

    content = note.read_text(encoding="utf-8")
    assert "Custom research notes about Dave." in content
    assert "[[2024-01-15_gettysburg-times_wrestler-wins|" in content


def test_people_note_appends_articles_section_when_missing(tmp_path):
    """A People note without ## Articles section gets the section appended."""
    people_dir = tmp_path / "People"
    people_dir.mkdir(parents=True)
    note = people_dir / "Dave Mccollum.md"
    note.write_text("# Dave Mccollum\n\nSome notes here.\n", encoding="utf-8")

    record = _make_record(person=["Dave Mccollum"])
    update_people_notes(record, str(tmp_path))

    content = note.read_text(encoding="utf-8")
    assert "## Articles" in content
    assert "Some notes here." in content
    assert "[[2024-01-15_gettysburg-times_wrestler-wins|" in content


def test_people_note_person_name_normalized_to_title_case(tmp_path):
    """Person name from lowercase input is normalized to title case."""
    record = _make_record(person=["dave mccollum"])
    update_people_notes(record, str(tmp_path))

    note = tmp_path / "People" / "Dave Mccollum.md"
    assert note.exists()
    content = note.read_text(encoding="utf-8")
    assert content.startswith("# Dave Mccollum\n")


# ---------------------------------------------------------------------------
# update_source_note tests
# ---------------------------------------------------------------------------

def test_source_note_created_when_not_exists(tmp_path):
    """A new Source note is created with header when source has no file yet."""
    record = _make_record(source="Gettysburg Times")
    update_source_note(record, str(tmp_path))

    note = tmp_path / "Sources" / "Gettysburg Times.md"
    assert note.exists()
    content = note.read_text(encoding="utf-8")
    assert content.startswith("# Gettysburg Times\n")
    assert "## Articles" in content
    assert "[[2024-01-15_gettysburg-times_wrestler-wins|Wrestler Wins Championship]]" in content
    # Source note backlink has no source in parenthetical (it IS the source)
    assert "(2024-01-15)" in content
    assert "Gettysburg Times, 2024-01-15" not in content


def test_source_note_backlink_format_no_source_in_parens(tmp_path):
    """Source note backlink format: - [[slug|title]] (date) — no source name."""
    record = _make_record(source="Gettysburg Times")
    update_source_note(record, str(tmp_path))

    note = tmp_path / "Sources" / "Gettysburg Times.md"
    content = note.read_text(encoding="utf-8")
    expected_line = "- [[2024-01-15_gettysburg-times_wrestler-wins|Wrestler Wins Championship]] (2024-01-15)"
    assert expected_line in content


def test_source_note_idempotent(tmp_path):
    """Calling update_source_note twice does not duplicate the backlink."""
    record = _make_record(source="Gettysburg Times")
    update_source_note(record, str(tmp_path))
    update_source_note(record, str(tmp_path))

    note = tmp_path / "Sources" / "Gettysburg Times.md"
    content = note.read_text(encoding="utf-8")
    slug = record.slug
    assert content.count(f"[[{slug}|") == 1


def test_source_note_sanitizes_invalid_chars(tmp_path):
    """Source name with '/' gets sanitized in the filename."""
    record = _make_record(source="Lancaster / Intelligencer")
    update_source_note(record, str(tmp_path))

    note = tmp_path / "Sources" / "Lancaster - Intelligencer.md"
    assert note.exists()
    content = note.read_text(encoding="utf-8")
    # H1 title uses original unsanitized name
    assert "# Lancaster / Intelligencer" in content


def test_source_note_undated(tmp_path):
    """Source note for an undated article uses 'undated' in backlink."""
    record = _make_record(source="Gettysburg Times", pub_date=None)
    update_source_note(record, str(tmp_path))

    note = tmp_path / "Sources" / "Gettysburg Times.md"
    content = note.read_text(encoding="utf-8")
    assert "(undated)" in content


# ---------------------------------------------------------------------------
# regenerate_index tests
# ---------------------------------------------------------------------------

def _write_metadata(articles_dir: Path, slug: str, person: list[str], title: str, source: str, date_str: str | None) -> None:
    """Helper to create a fake article folder with metadata.json."""
    folder = articles_dir / slug
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "slug": slug,
        "title": title,
        "source": source,
        "date": date_str,
        "person": person,
        "url": f"https://example.com/{slug}",
    }
    (folder / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def test_regenerate_index_creates_index_file(tmp_path):
    """regenerate_index creates Articles/_index.md."""
    articles_dir = tmp_path / "Articles"
    _write_metadata(articles_dir, "2024-01-15_gt_wrestler", ["Dave Mccollum"], "Wrestler Wins", "Gettysburg Times", "2024-01-15")
    regenerate_index(str(tmp_path))

    index = tmp_path / "Articles" / "_index.md"
    assert index.exists()


def test_regenerate_index_groups_by_person_with_count(tmp_path):
    """Index groups articles by person with article count in heading."""
    articles_dir = tmp_path / "Articles"
    _write_metadata(articles_dir, "2024-01-15_gt_wrestler", ["Dave Mccollum"], "Wrestler Wins", "GT", "2024-01-15")
    _write_metadata(articles_dir, "2024-02-10_gt_champ", ["Dave Mccollum"], "Champion Again", "GT", "2024-02-10")
    regenerate_index(str(tmp_path))

    content = (tmp_path / "Articles" / "_index.md").read_text(encoding="utf-8")
    assert "## Dave Mccollum (2 articles)" in content


def test_regenerate_index_reverse_chronological(tmp_path):
    """Articles within a person group are sorted reverse-chronologically."""
    articles_dir = tmp_path / "Articles"
    _write_metadata(articles_dir, "2024-01-15_gt_early", ["Dave Mccollum"], "Early Article", "GT", "2024-01-15")
    _write_metadata(articles_dir, "2024-06-01_gt_later", ["Dave Mccollum"], "Later Article", "GT", "2024-06-01")
    regenerate_index(str(tmp_path))

    content = (tmp_path / "Articles" / "_index.md").read_text(encoding="utf-8")
    idx_early = content.find("Early Article")
    idx_later = content.find("Later Article")
    # Later article should come first
    assert idx_later < idx_early


def test_regenerate_index_unlinked_articles(tmp_path):
    """Articles with no person appear under ## Unlinked Articles."""
    articles_dir = tmp_path / "Articles"
    _write_metadata(articles_dir, "2024-01-15_gt_orphan", [], "Orphan Article", "GT", "2024-01-15")
    regenerate_index(str(tmp_path))

    content = (tmp_path / "Articles" / "_index.md").read_text(encoding="utf-8")
    assert "## Unlinked Articles" in content
    assert "Orphan Article" in content


def test_regenerate_index_empty_articles_dir(tmp_path):
    """regenerate_index handles empty Articles directory gracefully."""
    articles_dir = tmp_path / "Articles"
    articles_dir.mkdir(parents=True)
    regenerate_index(str(tmp_path))

    index = tmp_path / "Articles" / "_index.md"
    assert index.exists()
    content = index.read_text(encoding="utf-8")
    assert "# Article Index" in content


def test_regenerate_index_no_articles_dir(tmp_path):
    """regenerate_index handles missing Articles directory gracefully."""
    regenerate_index(str(tmp_path))
    # Should not raise; writes minimal index


def test_regenerate_index_index_has_title_and_date(tmp_path):
    """Index starts with # Article Index and has a last-updated date."""
    articles_dir = tmp_path / "Articles"
    _write_metadata(articles_dir, "2024-01-15_gt_test", ["Dave Mccollum"], "Test", "GT", "2024-01-15")
    regenerate_index(str(tmp_path))

    content = (tmp_path / "Articles" / "_index.md").read_text(encoding="utf-8")
    assert content.startswith("# Article Index")
    assert "_Last updated:" in content


# ---------------------------------------------------------------------------
# update_graph tests
# ---------------------------------------------------------------------------

def test_update_graph_calls_all_operations(tmp_path):
    """update_graph creates People note, Source note, and index."""
    from mouse_research.config import AppConfig, VaultSettings
    from pydantic_settings import PydanticBaseSettingsSource

    # Use TestConfig subclass that puts init_settings first so constructor
    # kwargs override any existing config.yaml — same pattern as Phase 1 tests.
    class TestConfig(AppConfig):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls,
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ):
            return (init_settings,)

    config = TestConfig(vault=VaultSettings(path=str(tmp_path)))

    record = _make_record(person=["Dave Mccollum"], source="Gettysburg Times")
    # Pre-create metadata.json so index has content
    articles_dir = tmp_path / "Articles"
    _write_metadata(articles_dir, record.slug, record.person, record.article_data.title, record.source_name, "2024-01-15")

    update_graph(record, config)

    assert (tmp_path / "People" / "Dave Mccollum.md").exists()
    assert (tmp_path / "Sources" / "Gettysburg Times.md").exists()
    assert (tmp_path / "Articles" / "_index.md").exists()


def test_update_graph_does_not_raise_on_failure(tmp_path, monkeypatch):
    """update_graph swallows exceptions from sub-operations — non-fatal."""
    from mouse_research.config import AppConfig, VaultSettings
    from pydantic_settings import PydanticBaseSettingsSource
    import mouse_research.graph as graph_module

    class TestConfig(AppConfig):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls,
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ):
            return (init_settings,)

    config = TestConfig(vault=VaultSettings(path=str(tmp_path)))
    record = _make_record(person=["Dave Mccollum"])

    # Make update_people_notes raise
    monkeypatch.setattr(graph_module, "update_people_notes", lambda r, v: (_ for _ in ()).throw(RuntimeError("boom")))

    # Should not raise
    update_graph(record, config)
