import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from mouse_research.analyzer import build_prompt, parse_response, analyze_article


def test_build_prompt_includes_ocr_text():
    prompt = build_prompt(
        ocr_text="McCullum said Bermudian Spring wrestling",
        date="1991-12-05",
        source="The Gettysburg Times",
    )
    assert "McCullum said Bermudian Spring wrestling" in prompt
    assert "1991" in prompt
    assert "Gettysburg Times" in prompt
    assert "PEOPLE:" in prompt
    assert "SCHOOLS:" in prompt
    assert "WRESTLING:" in prompt
    assert "SUMMARY:" in prompt


def test_parse_response_extracts_fields():
    response = """BY DAN CHRIST
Times Correspondent

Although Bermudian Springs is not a returning regional champion, the team is well balanced.

"The strength of our team is balance," McCollum said.

HEADLINE: Bermudian Springs Wrestling Preview
PEOPLE: Dan Christ, Dave McCollum, Brandon Dawell, Mike Markey
SCHOOLS: Bermudian Springs
WRESTLING: yes
SUMMARY: Preview of the 1991 Bermudian Springs Eagles wrestling season highlighting team balance and key wrestlers."""

    result = parse_response(response)
    assert result.headline == "Bermudian Springs Wrestling Preview"
    assert "Dave McCollum" in result.people
    assert "Dan Christ" in result.people
    assert "Bermudian Springs" in result.schools
    assert result.is_wrestling is True
    assert "1991" in result.summary or "preview" in result.summary.lower()
    assert "McCollum" in result.cleaned_text
    assert "HEADLINE:" not in result.cleaned_text


def test_parse_response_handles_no_metadata():
    response = "Some cleaned text with no metadata lines."
    result = parse_response(response)
    assert result.cleaned_text == "Some cleaned text with no metadata lines."
    assert result.headline == ""
    assert result.people == []
    assert result.schools == []
    assert result.is_wrestling is True
    assert result.summary == ""


def test_analyze_article_writes_enriched_note(tmp_path):
    """Test that analyze_article reads OCR, calls Ollama, and rewrites article.md."""
    article_dir = tmp_path / "1991-12-05_newspapers-com_test-article"
    article_dir.mkdir()

    (article_dir / "ocr_raw.md").write_text("McCullum said Bermudian Spring wrestling")
    (article_dir / "metadata.json").write_text(json.dumps({
        "url": "https://www.newspapers.com/image/123",
        "slug": "1991-12-05_newspapers-com_test-article",
        "source": "Newspapers.com",
        "date": "1991-12-05",
        "captured": "2026-04-02",
        "title": "McCullum",
        "person": ["Dave McCollum"],
        "tags": ["newspaper", "archive"],
        "extraction": "glm-ocr",
        "ocr_queued": False,
    }))
    (article_dir / "article.md").write_text("---\ndate: 1991-12-05\n---\n# Old Title\nold content")

    mock_response = MagicMock()
    mock_response.response = """McCollum said Bermudian Springs wrestling is well balanced.

HEADLINE: Bermudian Springs Wrestling Preview
PEOPLE: Dave McCollum
SCHOOLS: Bermudian Springs
WRESTLING: yes
SUMMARY: Preview of the wrestling season."""
    mock_response.eval_count = 50

    with patch("mouse_research.analyzer.ollama") as mock_ollama:
        mock_ollama.generate.return_value = mock_response
        result = analyze_article(article_dir, ollama_url="http://localhost:11434")

    assert result is True

    meta = json.loads((article_dir / "metadata.json").read_text())
    assert meta["analyzed"] is True
    assert "Bermudian Springs" in meta["schools"]
    assert meta["is_wrestling"] is True
    assert "Bermudian Springs Wrestling Preview" in meta["headline"]

    article_text = (article_dir / "article.md").read_text()
    assert "[[Dave McCollum]]" in article_text
    assert "[[Bermudian Springs]]" in article_text
    assert "## Cleaned Text" in article_text
    assert "## Original OCR" in article_text
    assert "McCollum said Bermudian Springs" in article_text


def test_analyze_article_skips_already_analyzed(tmp_path):
    """Articles with analyzed: true in metadata are skipped."""
    article_dir = tmp_path / "test-article"
    article_dir.mkdir()
    (article_dir / "metadata.json").write_text(json.dumps({"analyzed": True}))

    result = analyze_article(article_dir, ollama_url="http://localhost:11434")
    assert result is False


from typer.testing import CliRunner
from mouse_research.cli import app

runner = CliRunner()

def test_analyze_command_exists():
    result = runner.invoke(app, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "Process archived articles through Gemma 4" in result.output
