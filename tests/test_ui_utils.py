import json
from pathlib import Path
from ui_utils import load_articles, load_article_text, get_people_index, is_cloud_mode


def test_load_articles_reads_metadata(tmp_path):
    art_dir = tmp_path / "Articles"
    a1 = art_dir / "1991-12-05_test_article-one"
    a1.mkdir(parents=True)
    (a1 / "metadata.json").write_text(json.dumps({
        "slug": "1991-12-05_test_article-one",
        "date": "1991-12-05",
        "headline": "Eagles Win",
        "title": "eagles",
        "source": "Newspapers.com",
        "people": ["Dave McCollum"],
        "schools": ["Bermudian Springs"],
        "is_wrestling": True,
        "summary": "Eagles win a match.",
        "analyzed": True,
        "person": ["Dave McCollum"],
        "tags": ["newspaper"],
    }))
    a2 = art_dir / "1992-01-10_test_article-two"
    a2.mkdir(parents=True)
    (a2 / "metadata.json").write_text(json.dumps({
        "slug": "1992-01-10_test_article-two",
        "date": "1992-01-10",
        "headline": "Football Recap",
        "title": "football",
        "source": "Newspapers.com",
        "people": [],
        "schools": ["West Chester"],
        "is_wrestling": False,
        "summary": "Football game.",
        "analyzed": True,
        "person": [],
        "tags": ["newspaper"],
    }))
    articles = load_articles(str(tmp_path))
    assert len(articles) == 2
    assert articles[0]["headline"] == "Eagles Win" or articles[1]["headline"] == "Eagles Win"


def test_load_articles_skips_bad_json(tmp_path):
    art_dir = tmp_path / "Articles"
    a1 = art_dir / "bad-article"
    a1.mkdir(parents=True)
    (a1 / "metadata.json").write_text("not json")
    articles = load_articles(str(tmp_path))
    assert len(articles) == 0


def test_load_articles_empty_dir(tmp_path):
    articles = load_articles(str(tmp_path))
    assert articles == []


def test_is_cloud_mode_true_when_no_vault(tmp_path):
    """Cloud mode when vault path doesn't exist."""
    assert is_cloud_mode(str(tmp_path / "nonexistent")) is True


def test_is_cloud_mode_false_when_vault_exists(tmp_path):
    """Local mode when vault path exists."""
    assert is_cloud_mode(str(tmp_path)) is False


def test_load_articles_from_json(tmp_path):
    """load_articles falls back to data/articles.json when vault missing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    articles_data = [
        {"slug": "2005-02-27_test", "date": "2005-02-27", "headline": "Eagles Win",
         "people": ["Kyle Flickinger"], "schools": ["Bermudian Springs"],
         "is_wrestling": True, "summary": "Test.", "analyzed": True,
         "cleaned_text": "The Eagles won the match."},
    ]
    (data_dir / "articles.json").write_text(json.dumps(articles_data))

    articles = load_articles(vault_path=None, data_dir=str(data_dir))
    assert len(articles) == 1
    assert articles[0]["headline"] == "Eagles Win"


def test_load_article_text_from_vault(tmp_path):
    """load_article_text reads cleaned text from article.md in vault."""
    art_dir = tmp_path / "Articles" / "2005-02-27_test"
    art_dir.mkdir(parents=True)
    (art_dir / "metadata.json").write_text(json.dumps({"slug": "2005-02-27_test"}))
    (art_dir / "article.md").write_text(
        "---\nheadline: Test\n---\n# Test\n\n## Cleaned Text\n\nThe Eagles won the match.\n\n***\n\n## Original OCR\n\ngarbled"
    )

    text = load_article_text("2005-02-27_test", vault_path=str(tmp_path))
    assert "Eagles won the match" in text


def test_load_article_text_from_json(tmp_path):
    """load_article_text reads cleaned_text field from articles.json."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    articles_data = [
        {"slug": "2005-02-27_test", "cleaned_text": "The Eagles won."},
    ]
    (data_dir / "articles.json").write_text(json.dumps(articles_data))

    text = load_article_text("2005-02-27_test", vault_path=None, data_dir=str(data_dir))
    assert text == "The Eagles won."


def test_get_people_index():
    """get_people_index builds person -> articles mapping."""
    articles = [
        {"slug": "a1", "people": ["Kyle Flickinger", "Dave McCollum"]},
        {"slug": "a2", "people": ["Kyle Flickinger"]},
        {"slug": "a3", "people": ["Jon Hade"]},
    ]
    index = get_people_index(articles)
    assert len(index["Kyle Flickinger"]) == 2
    assert len(index["Dave McCollum"]) == 1
    assert len(index["Jon Hade"]) == 1
