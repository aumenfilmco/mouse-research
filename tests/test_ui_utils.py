import json
from pathlib import Path
from ui_utils import load_articles


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
