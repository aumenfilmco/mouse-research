import json
from pathlib import Path
from mouse_research.sync import export_articles_json


def _make_article(tmp_path, slug, headline, cleaned_text, people=None, schools=None):
    """Helper to create a test article directory with metadata.json and article.md."""
    art_dir = tmp_path / "Articles" / slug
    art_dir.mkdir(parents=True)
    meta = {
        "slug": slug,
        "date": slug[:10],
        "headline": headline,
        "people": people or [],
        "schools": schools or [],
        "is_wrestling": True,
        "summary": f"Summary of {headline}.",
        "analyzed": True,
        "source": "Newspapers.com",
    }
    (art_dir / "metadata.json").write_text(json.dumps(meta))
    (art_dir / "article.md").write_text(
        f"---\nheadline: {headline}\n---\n# {headline}\n\n## Cleaned Text\n\n{cleaned_text}\n\n***\n\n## Original OCR\n\ngarbled text"
    )
    return art_dir


def test_export_articles_json(tmp_path):
    """export_articles_json writes all articles to a single JSON file."""
    _make_article(tmp_path, "2005-02-27_test-one", "Eagles Win", "The Eagles won.", ["Kyle"], ["Bermudian Springs"])
    _make_article(tmp_path, "2003-11-26_test-two", "Season Preview", "Preview of season.", ["Dave"], ["Bermudian Springs"])

    output_path = tmp_path / "output" / "articles.json"
    export_articles_json(str(tmp_path), str(output_path))

    assert output_path.exists()
    data = json.loads(output_path.read_text())
    assert len(data) == 2
    slugs = {a["slug"] for a in data}
    assert "2005-02-27_test-one" in slugs
    assert "2003-11-26_test-two" in slugs
    for a in data:
        assert "cleaned_text" in a
        assert len(a["cleaned_text"]) > 0


def test_export_articles_json_skips_unanalyzed(tmp_path):
    """Articles without article.md still export, just with empty cleaned_text."""
    art_dir = tmp_path / "Articles" / "2005-01-01_no-article-md"
    art_dir.mkdir(parents=True)
    (art_dir / "metadata.json").write_text(json.dumps({
        "slug": "2005-01-01_no-article-md",
        "date": "2005-01-01",
        "headline": "No Article",
        "people": [],
        "schools": [],
        "is_wrestling": True,
        "analyzed": False,
    }))

    output_path = tmp_path / "output" / "articles.json"
    export_articles_json(str(tmp_path), str(output_path))

    data = json.loads(output_path.read_text())
    assert len(data) == 1
    assert data[0]["cleaned_text"] == ""


def test_export_articles_json_empty_vault(tmp_path):
    """Empty vault produces empty JSON array."""
    output_path = tmp_path / "output" / "articles.json"
    export_articles_json(str(tmp_path), str(output_path))

    data = json.loads(output_path.read_text())
    assert data == []
