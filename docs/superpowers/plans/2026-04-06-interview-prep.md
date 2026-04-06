# Interview Prep Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Interview Prep page to the Streamlit UI that generates targeted documentary interview questions via Gemini Flash 2.0, with web enrichment/fact-checking, PDF export, Obsidian note export, and cloud deployment on Streamlit Community Cloud.

**Architecture:** Hybrid local/cloud model. A new `interview_prep.py` module handles LLM interaction (Gemini Flash). `ui_utils.py` gains dual-source loading (vault or `data/articles.json`). A `sync` CLI command exports article data for cloud deployment. The Interview Prep Streamlit page ties it all together with person search, theme selection, question curation, and export.

**Tech Stack:** Streamlit, google-generativeai (Gemini Flash 2.0), fpdf2, pandas, existing mouse_research modules

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `ui_utils.py` | Modify | Add `is_cloud_mode()`, `load_articles_json()` fallback, `load_article_text()`, `get_people_index()` |
| `src/mouse_research/interview_prep.py` | Create | Gemini Flash client, system prompt, question generation pipeline, fact-checking |
| `src/mouse_research/export_pdf.py` | Create | PDF generation via fpdf2 |
| `src/mouse_research/sync.py` | Create | Export vault metadata + cleaned text to `data/articles.json` |
| `src/mouse_research/cli.py` | Modify | Add `sync` command |
| `pages/4_Interview_Prep.py` | Create | Streamlit Interview Prep page |
| `requirements-cloud.txt` | Create | Cloud-only dependencies |
| `.streamlit/config.toml` | Create | Streamlit theme config |
| `tests/test_interview_prep.py` | Create | Tests for interview_prep module |
| `tests/test_sync.py` | Create | Tests for sync module |
| `tests/test_export_pdf.py` | Create | Tests for PDF export |
| `tests/test_ui_utils.py` | Modify | Add tests for new ui_utils functions |

---

### Task 1: Install new dependencies

**Files:**
- Modify: `pyproject.toml` (or requirements file — check which exists)

- [ ] **Step 1: Check project dependency file**

Run: `ls pyproject.toml setup.py requirements.txt 2>/dev/null`

- [ ] **Step 2: Install fpdf2 and google-generativeai**

Run: `.venv/bin/pip install fpdf2 google-generativeai`

- [ ] **Step 3: Verify imports work**

Run: `.venv/bin/python -c "import fpdf; import google.generativeai; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "chore: add fpdf2 and google-generativeai dependencies"
```

---

### Task 2: Add dual-source loading and people index to ui_utils.py

**Files:**
- Modify: `ui_utils.py`
- Modify: `tests/test_ui_utils.py`

- [ ] **Step 1: Write failing tests for new functions**

Add to `tests/test_ui_utils.py`:

```python
import json
from pathlib import Path
from ui_utils import load_articles, load_article_text, get_people_index, is_cloud_mode


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ui_utils.py -v -k "cloud_mode or from_json or article_text or people_index"`
Expected: FAIL with `ImportError` or `cannot import name`

- [ ] **Step 3: Implement new functions in ui_utils.py**

Replace `ui_utils.py` with:

```python
"""Shared utilities for the Streamlit UI.

Provides cached data loading from the Obsidian vault or bundled JSON.
"""
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

# Streamlit import — may not be available in test/CLI context
try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False


_DATA_DIR = Path(__file__).parent / "data"


def is_cloud_mode(vault_path: str | None) -> bool:
    """True when running without a local vault (cloud deployment)."""
    if vault_path is None:
        return True
    return not Path(vault_path).exists()


def get_vault_path() -> str | None:
    """Get vault path from mouse-research config. Returns None if config missing."""
    try:
        from mouse_research.config import get_config, CONFIG_PATH
        if not CONFIG_PATH.exists():
            return None
        return get_config().vault.path
    except Exception:
        return None


def _load_articles_from_vault(vault_path: str) -> list[dict]:
    """Scan vault/Articles/*/metadata.json."""
    articles_dir = Path(vault_path) / "Articles"
    if not articles_dir.exists():
        return []

    articles: list[dict] = []
    for meta_file in articles_dir.glob("*/metadata.json"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["_dir"] = str(meta_file.parent)
            articles.append(meta)
        except (json.JSONDecodeError, OSError):
            continue

    articles.sort(key=lambda r: r.get("date") or "0000-00-00", reverse=True)
    return articles


def _load_articles_from_json(data_dir: str | None = None) -> list[dict]:
    """Load articles from bundled data/articles.json."""
    d = Path(data_dir) if data_dir else _DATA_DIR
    json_path = d / "articles.json"
    if not json_path.exists():
        return []
    articles = json.loads(json_path.read_text(encoding="utf-8"))
    articles.sort(key=lambda r: r.get("date") or "0000-00-00", reverse=True)
    return articles


def load_articles(vault_path: str | None = None, data_dir: str | None = None) -> list[dict]:
    """Load all article metadata.

    In local mode (vault_path exists): scans vault metadata.json files.
    In cloud mode: loads from data/articles.json.

    Returns a list of dicts sorted by date descending.
    """
    if vault_path and not is_cloud_mode(vault_path):
        return _load_articles_from_vault(vault_path)
    return _load_articles_from_json(data_dir)


def load_article_text(slug: str, vault_path: str | None = None, data_dir: str | None = None) -> str:
    """Load cleaned text for a specific article.

    Local mode: parses the ## Cleaned Text section from article.md.
    Cloud mode: reads the cleaned_text field from articles.json.
    """
    if vault_path and not is_cloud_mode(vault_path):
        articles_dir = Path(vault_path) / "Articles"
        # Find the article directory by slug
        for d in articles_dir.iterdir():
            if not d.is_dir():
                continue
            meta_path = d / "metadata.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    if meta.get("slug") == slug:
                        article_md = d / "article.md"
                        if article_md.exists():
                            content = article_md.read_text(encoding="utf-8")
                            marker = "## Cleaned Text"
                            idx = content.find(marker)
                            if idx != -1:
                                text_start = idx + len(marker)
                                end_marker = "***"
                                end_idx = content.find(end_marker, text_start)
                                if end_idx != -1:
                                    return content[text_start:end_idx].strip()
                                return content[text_start:].strip()
                        return ""
                except (json.JSONDecodeError, OSError):
                    continue
        return ""

    # Cloud mode — read from articles.json
    d = Path(data_dir) if data_dir else _DATA_DIR
    json_path = d / "articles.json"
    if not json_path.exists():
        return ""
    articles = json.loads(json_path.read_text(encoding="utf-8"))
    for a in articles:
        if a.get("slug") == slug:
            return a.get("cleaned_text", "")
    return ""


def get_people_index(articles: list[dict]) -> dict[str, list[dict]]:
    """Build a person name -> list of articles mapping."""
    index: dict[str, list[dict]] = defaultdict(list)
    for a in articles:
        for person in a.get("people") or []:
            index[person].append(a)
    return dict(index)


def articles_to_dataframe(articles: list[dict]) -> pd.DataFrame:
    """Convert article metadata list to a pandas DataFrame for display."""
    rows = []
    for a in articles:
        rows.append({
            "Date": a.get("date", "undated"),
            "Headline": a.get("headline") or a.get("title") or a.get("slug", ""),
            "Schools": ", ".join(a.get("schools") or []),
            "Wrestling": "✅" if a.get("is_wrestling", True) else "⚠️",
            "People": ", ".join(a.get("people") or []),
            "Summary": a.get("summary", ""),
            "Source": a.get("source", ""),
            "_slug": a.get("slug", ""),
            "_is_wrestling": a.get("is_wrestling", True),
            "_analyzed": a.get("analyzed", False),
        })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Update existing Streamlit pages for new load_articles signature**

The existing `app.py` and `pages/*.py` call `load_articles(vault_path)` with a positional vault_path. This still works — the signature is `load_articles(vault_path=None, data_dir=None)` so passing a vault path positionally is unchanged.

Verify by running: `.venv/bin/python -c "from ui_utils import load_articles; print('import OK')"`

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_ui_utils.py -v`
Expected: All tests PASS (both old and new)

- [ ] **Step 6: Commit**

```bash
git add ui_utils.py tests/test_ui_utils.py
git commit -m "feat: add dual-source article loading and people index to ui_utils"
```

---

### Task 3: Create sync module and CLI command

**Files:**
- Create: `src/mouse_research/sync.py`
- Create: `tests/test_sync.py`
- Modify: `src/mouse_research/cli.py`

- [ ] **Step 1: Write failing tests for sync**

Create `tests/test_sync.py`:

```python
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
    # Check cleaned text was extracted
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sync.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement sync.py**

Create `src/mouse_research/sync.py`:

```python
"""Export vault article data to a portable JSON file for cloud deployment."""
import json
from pathlib import Path

from mouse_research.logger import get_logger

logger = get_logger(__name__)


def _extract_cleaned_text(article_md_path: Path) -> str:
    """Extract the ## Cleaned Text section from an article.md file."""
    if not article_md_path.exists():
        return ""
    content = article_md_path.read_text(encoding="utf-8")
    marker = "## Cleaned Text"
    idx = content.find(marker)
    if idx == -1:
        return ""
    text_start = idx + len(marker)
    end_marker = "***"
    end_idx = content.find(end_marker, text_start)
    if end_idx != -1:
        return content[text_start:end_idx].strip()
    return content[text_start:].strip()


def export_articles_json(vault_path: str, output_path: str) -> int:
    """Export all article metadata + cleaned text to a single JSON file.

    Args:
        vault_path: Path to the Obsidian vault root.
        output_path: Path to write the output JSON file.

    Returns:
        Number of articles exported.
    """
    articles_dir = Path(vault_path) / "Articles"
    articles: list[dict] = []

    if articles_dir.exists():
        for meta_file in sorted(articles_dir.glob("*/metadata.json")):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                article_md = meta_file.parent / "article.md"
                meta["cleaned_text"] = _extract_cleaned_text(article_md)
                # Remove internal fields that don't belong in export
                meta.pop("_dir", None)
                articles.append(meta)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Skipping %s: %s", meta_file, e)
                continue

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(articles, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Exported %d articles to %s", len(articles), output_path)
    return len(articles)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_sync.py -v`
Expected: 3 PASS

- [ ] **Step 5: Add `sync` command to cli.py**

Add after the `ui` command in `src/mouse_research/cli.py`:

```python
@app.command()
def sync(
    push: bool = typer.Option(False, "--push", help="Commit and push to GitHub after export"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    """Export article data to data/articles.json for cloud deployment."""
    import subprocess
    from mouse_research.config import get_config
    from mouse_research.logger import setup_logging
    from mouse_research.sync import export_articles_json

    setup_logging(verbose=verbose)
    config = get_config()

    output_path = Path(__file__).parent.parent.parent / "data" / "articles.json"
    count = export_articles_json(config.vault.path, str(output_path))
    console.print(f"[green]Exported {count} articles[/green] to {output_path}")

    if push:
        repo_root = Path(__file__).parent.parent.parent
        subprocess.run(["git", "add", "data/articles.json"], cwd=repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"data: sync {count} articles for cloud deployment"],
            cwd=repo_root,
            check=True,
        )
        subprocess.run(["git", "push"], cwd=repo_root, check=True)
        console.print("[green]Pushed to GitHub.[/green]")
```

- [ ] **Step 6: Verify CLI command registers**

Run: `.venv/bin/mouse-research sync --help`
Expected: Shows "Export article data to data/articles.json for cloud deployment."

- [ ] **Step 7: Commit**

```bash
git add src/mouse_research/sync.py tests/test_sync.py src/mouse_research/cli.py
git commit -m "feat: add sync command to export articles for cloud deployment"
```

---

### Task 4: Create interview_prep module (Gemini Flash integration)

**Files:**
- Create: `src/mouse_research/interview_prep.py`
- Create: `tests/test_interview_prep.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_interview_prep.py`:

```python
import json
from unittest.mock import MagicMock, patch
from mouse_research.interview_prep import (
    build_question_prompt,
    build_enrichment_prompt,
    build_factcheck_prompt,
    parse_questions_response,
    SYSTEM_PROMPT,
)


def test_system_prompt_mentions_mouse():
    """System prompt contains documentary context."""
    assert "MOUSE" in SYSTEM_PROMPT
    assert "McCollum" in SYSTEM_PROMPT
    assert "Bermudian Springs" in SYSTEM_PROMPT


def test_build_question_prompt_includes_articles():
    """Question prompt includes article text and selected themes."""
    articles = [
        {"slug": "a1", "date": "2005-02-27", "headline": "Eagles Win", "cleaned_text": "The Eagles won the district title."},
        {"slug": "a2", "date": "2007-02-28", "headline": "NCAA Success", "cleaned_text": "Flickinger went to nationals."},
    ]
    themes = ["High school career", "Teaser sound bite"]
    prompt = build_question_prompt(
        person_name="Kyle Flickinger",
        articles=articles,
        themes=themes,
        additional_context="He is now a coach.",
    )
    assert "Kyle Flickinger" in prompt
    assert "Eagles Won" in prompt or "Eagles won" in prompt
    assert "High school career" in prompt
    assert "Teaser sound bite" in prompt
    assert "He is now a coach" in prompt


def test_build_question_prompt_without_optional_fields():
    """Question prompt works without additional context."""
    articles = [{"slug": "a1", "date": "2005-02-27", "headline": "Test", "cleaned_text": "Text."}]
    prompt = build_question_prompt("Test Person", articles, ["Teaser sound bite"])
    assert "Test Person" in prompt
    assert "Teaser sound bite" in prompt


def test_build_enrichment_prompt():
    """Enrichment prompt includes person name and key details."""
    prompt = build_enrichment_prompt("Kyle Flickinger", ["Bermudian Springs"], ["2003", "2005", "2007"])
    assert "Kyle Flickinger" in prompt
    assert "Bermudian Springs" in prompt


def test_build_factcheck_prompt():
    """Fact-check prompt includes the questions to verify."""
    questions = [
        {"question": "You had a 26-7 record?", "context": "From 2007 article"},
    ]
    prompt = build_factcheck_prompt("Kyle Flickinger", questions)
    assert "26-7" in prompt
    assert "Kyle Flickinger" in prompt


def test_parse_questions_response():
    """Parse structured question output from LLM."""
    response = """STORY_ARC: Kyle Flickinger wrestled at Bermudian Springs under Dave McCollum before going on to NCAA Division II success at York College.

QUESTION: What was the wrestling room at Bermudian like under McCollum?
CONTEXT: The practice room is the heart of the documentary — let him paint the picture.

QUESTION: Your college coach said he didn't think you'd start. Did you know?
CONTEXT: From 2007 article — Coach Kessler admitted doubting him freshman year.

QUESTION: When did you realize that what McCollum built wasn't normal?
CONTEXT: Teaser sound bite — the moment of perspective usually comes in college."""

    result = parse_questions_response(response)
    assert result["story_arc"] == "Kyle Flickinger wrestled at Bermudian Springs under Dave McCollum before going on to NCAA Division II success at York College."
    assert len(result["questions"]) == 3
    assert result["questions"][0]["question"] == "What was the wrestling room at Bermudian like under McCollum?"
    assert "practice room" in result["questions"][0]["context"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_interview_prep.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement interview_prep.py**

Create `src/mouse_research/interview_prep.py`:

```python
"""Interview question generation via Gemini Flash 2.0.

Generates targeted documentary interview questions for a person
based on their archived articles, with optional web enrichment
and fact-checking via Google Search grounding.

Public API:
    build_question_prompt(person_name, articles, themes, additional_context)
    build_enrichment_prompt(person_name, schools, years)
    build_factcheck_prompt(person_name, questions)
    parse_questions_response(response_text)
    generate_questions(person_name, articles, themes, ...)
"""
import os
import re
from dataclasses import dataclass, field

from mouse_research.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a documentary research assistant for "MOUSE: 50 Years on the Mat," \
a film about the Bermudian Springs wrestling program and its legendary coach \
Dave McCollum. The documentary spans roughly 1975-2025 and explores how one \
small-town Pennsylvania program shaped generations of wrestlers. When \
generating interview questions, prioritize: the wrestling room culture, \
relationships with McCollum, moments of transformation, and details that \
reveal the program's character. Questions should be designed to elicit vivid, \
emotional sound bites suitable for a documentary teaser and feature film."""

_QUESTION_PROMPT_TEMPLATE = """Generate interview questions for {person_name} based on the following newspaper articles about them.

ARTICLES (chronological):
{articles_text}

THEMES TO EXPLORE:
{themes_text}

{additional_context_block}

INSTRUCTIONS:
- Generate 6-10 targeted interview questions
- Each question should reference specific details from the articles
- Design questions to elicit vivid, emotional responses suitable for documentary footage
- Include at least one question designed for a teaser/trailer sound bite
- For each question, include a brief context note explaining why it matters and what article/fact it draws from

FORMAT YOUR RESPONSE EXACTLY AS:
STORY_ARC: 2-3 sentence overview of this person's trajectory based on the articles.

QUESTION: [the question]
CONTEXT: [why this question matters / what it's drawn from]

QUESTION: [the question]
CONTEXT: [why this question matters / what it's drawn from]

(repeat for each question)"""


def build_question_prompt(
    person_name: str,
    articles: list[dict],
    themes: list[str],
    additional_context: str = "",
) -> str:
    """Build the prompt for generating interview questions."""
    articles_text = ""
    for a in sorted(articles, key=lambda x: x.get("date", "0000")):
        date = a.get("date", "undated")
        headline = a.get("headline", "untitled")
        text = a.get("cleaned_text", "")
        articles_text += f"\n--- {date}: {headline} ---\n{text}\n"

    themes_text = "\n".join(f"- {t}" for t in themes)

    additional_context_block = ""
    if additional_context:
        additional_context_block = f"ADDITIONAL CONTEXT FROM FILMMAKER:\n{additional_context}"

    return _QUESTION_PROMPT_TEMPLATE.format(
        person_name=person_name,
        articles_text=articles_text,
        themes_text=themes_text,
        additional_context_block=additional_context_block,
    )


def build_enrichment_prompt(person_name: str, schools: list[str], years: list[str]) -> str:
    """Build prompt for web search enrichment."""
    schools_str = ", ".join(schools) if schools else "Pennsylvania"
    years_str = ", ".join(years) if years else "unknown years"
    return (
        f"Find information about {person_name} in connection with wrestling, "
        f"particularly at {schools_str} ({years_str}). "
        f"Look for career records, achievements, coaching roles, or current activities. "
        f"Return only verified facts with sources."
    )


def build_factcheck_prompt(person_name: str, questions: list[dict]) -> str:
    """Build prompt for fact-checking generated questions."""
    questions_text = ""
    for i, q in enumerate(questions, 1):
        questions_text += f"\nQ{i}: {q['question']}\nContext: {q['context']}\n"

    return (
        f"Fact-check the following interview questions about {person_name} "
        f"and Bermudian Springs wrestling. For each question, verify any specific "
        f"claims (records, dates, scores, names, titles). Report ONLY discrepancies "
        f"or corrections. If a fact checks out, skip it.\n"
        f"{questions_text}\n"
        f"FORMAT: Q[number]: [correction or 'verified']\n"
        f"Only include entries where you found a discrepancy."
    )


def parse_questions_response(response_text: str) -> dict:
    """Parse the LLM response into structured questions.

    Returns:
        {"story_arc": str, "questions": [{"question": str, "context": str}, ...]}
    """
    result: dict = {"story_arc": "", "questions": []}

    # Extract story arc
    arc_match = re.search(r"STORY_ARC:\s*(.+?)(?=\n\nQUESTION:|\Z)", response_text, re.DOTALL)
    if arc_match:
        result["story_arc"] = arc_match.group(1).strip()

    # Extract questions
    question_blocks = re.findall(
        r"QUESTION:\s*(.+?)\nCONTEXT:\s*(.+?)(?=\n\nQUESTION:|\Z)",
        response_text,
        re.DOTALL,
    )
    for q_text, c_text in question_blocks:
        result["questions"].append({
            "question": q_text.strip(),
            "context": c_text.strip(),
        })

    return result


def _get_gemini_api_key() -> str:
    """Get Gemini API key from Streamlit secrets or environment."""
    try:
        import streamlit as st
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError(
            "GEMINI_API_KEY not found. Set it as an environment variable "
            "or in .streamlit/secrets.toml"
        )
    return key


def generate_questions(
    person_name: str,
    articles: list[dict],
    themes: list[str],
    additional_context: str = "",
    enrich: bool = False,
    fact_check: bool = True,
) -> dict:
    """Full question generation pipeline.

    Returns:
        {
            "story_arc": str,
            "questions": [{"question": str, "context": str, "fact_check_warning": str | None}],
            "enrichment": str | None,
        }
    """
    import google.generativeai as genai

    api_key = _get_gemini_api_key()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    enrichment_text = None

    # Step 1: Web enrichment (optional)
    if enrich:
        schools = list({s for a in articles for s in (a.get("schools") or [])})
        years = sorted({a.get("date", "")[:4] for a in articles if a.get("date")})
        enrich_prompt = build_enrichment_prompt(person_name, schools, years)
        logger.info("Running web enrichment for %s", person_name)
        enrich_response = model.generate_content(
            enrich_prompt,
            tools="google_search_retrieval",
        )
        enrichment_text = enrich_response.text
        if additional_context:
            additional_context += f"\n\nWEB RESEARCH:\n{enrichment_text}"
        else:
            additional_context = f"WEB RESEARCH:\n{enrichment_text}"

    # Step 2: Generate questions
    prompt = build_question_prompt(person_name, articles, themes, additional_context)
    logger.info("Generating questions for %s (%d articles, %d themes)", person_name, len(articles), len(themes))
    response = model.generate_content(
        [{"role": "user", "parts": [prompt]}],
        generation_config={"temperature": 0.7},
        system_instruction=SYSTEM_PROMPT,
    )
    result = parse_questions_response(response.text)
    result["enrichment"] = enrichment_text

    # Step 3: Fact-check (optional)
    if fact_check and result["questions"]:
        fc_prompt = build_factcheck_prompt(person_name, result["questions"])
        logger.info("Fact-checking %d questions", len(result["questions"]))
        fc_response = model.generate_content(
            fc_prompt,
            tools="google_search_retrieval",
        )
        # Parse fact-check results
        for line in fc_response.text.strip().splitlines():
            match = re.match(r"Q(\d+):\s*(.+)", line)
            if match:
                q_num = int(match.group(1)) - 1
                correction = match.group(2).strip()
                if correction.lower() != "verified" and q_num < len(result["questions"]):
                    result["questions"][q_num]["fact_check_warning"] = correction

    # Ensure all questions have fact_check_warning key
    for q in result["questions"]:
        q.setdefault("fact_check_warning", None)

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_interview_prep.py -v`
Expected: 6 PASS (all tests are for prompt building and parsing — no API calls)

- [ ] **Step 5: Commit**

```bash
git add src/mouse_research/interview_prep.py tests/test_interview_prep.py
git commit -m "feat: add interview_prep module with Gemini Flash question generation"
```

---

### Task 5: Create PDF export module

**Files:**
- Create: `src/mouse_research/export_pdf.py`
- Create: `tests/test_export_pdf.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_export_pdf.py`:

```python
from pathlib import Path
from mouse_research.export_pdf import generate_interview_pdf


def test_generate_interview_pdf_creates_file(tmp_path):
    """PDF file is created with correct content."""
    output_path = tmp_path / "test_output.pdf"
    questions = [
        {"question": "What was the room like?", "context": "Heart of the doc.", "fact_check_warning": None},
        {"question": "When did you know it wasn't normal?", "context": "Teaser bite.", "fact_check_warning": "OCR said 26-8, web says 26-7"},
    ]
    source_articles = [
        {"date": "2005-02-27", "headline": "Eagles Win District Title"},
        {"date": "2007-02-28", "headline": "NCAA Success"},
    ]

    generate_interview_pdf(
        person_name="Kyle Flickinger",
        story_arc="Kyle wrestled at Bermudian Springs before NCAA success at York.",
        questions=questions,
        source_articles=source_articles,
        output_path=str(output_path),
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 100  # Not empty


def test_generate_interview_pdf_returns_bytes():
    """PDF can be generated as bytes (for Streamlit download)."""
    questions = [
        {"question": "Test question?", "context": "Test context.", "fact_check_warning": None},
    ]
    source_articles = [{"date": "2005-01-01", "headline": "Test Article"}]

    pdf_bytes = generate_interview_pdf(
        person_name="Test Person",
        story_arc="Test arc.",
        questions=questions,
        source_articles=source_articles,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100
    assert pdf_bytes[:5] == b"%PDF-"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_export_pdf.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement export_pdf.py**

Create `src/mouse_research/export_pdf.py`:

```python
"""PDF export for interview prep sheets using fpdf2."""
from datetime import date
from pathlib import Path

from fpdf import FPDF


class _InterviewPDF(FPDF):
    """Custom PDF with MOUSE branding."""

    def __init__(self, person_name: str):
        super().__init__()
        self.person_name = person_name

    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "MOUSE -- Interview Prep", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, self.person_name, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, date.today().strftime("%B %d, %Y"), new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"MOUSE Research Pipeline - Page {self.page_no()}", align="C")


def generate_interview_pdf(
    person_name: str,
    story_arc: str,
    questions: list[dict],
    source_articles: list[dict],
    output_path: str | None = None,
) -> bytes | None:
    """Generate an interview prep PDF.

    Args:
        person_name: Name of the interviewee.
        story_arc: 2-3 sentence summary of their trajectory.
        questions: List of {"question": str, "context": str, "fact_check_warning": str | None}.
        source_articles: List of {"date": str, "headline": str}.
        output_path: If provided, writes PDF to this path and returns None.
                     If None, returns PDF as bytes.

    Returns:
        PDF bytes if output_path is None, otherwise None.
    """
    pdf = _InterviewPDF(person_name)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Story Arc
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "STORY ARC", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, story_arc)
    pdf.ln(6)

    # Questions
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "QUESTIONS", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for i, q in enumerate(questions, 1):
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(0, 5, f"{i}. {q['question']}")
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 4.5, f"   {q['context']}")
        if q.get("fact_check_warning"):
            pdf.set_text_color(200, 120, 0)
            pdf.set_font("Helvetica", "I", 8)
            pdf.multi_cell(0, 4, f"   * {q['fact_check_warning']}")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

    # Fact-check footnotes section
    warnings = [(i + 1, q["fact_check_warning"]) for i, q in enumerate(questions) if q.get("fact_check_warning")]
    if warnings:
        pdf.ln(4)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, "FACT-CHECK NOTES", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for q_num, warning in warnings:
            pdf.multi_cell(0, 4.5, f"Q{q_num}: {warning}")
            pdf.ln(1)

    # Source articles
    pdf.ln(4)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "SOURCE ARTICLES", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for a in sorted(source_articles, key=lambda x: x.get("date", "")):
        pdf.cell(0, 4.5, f"  {a.get('date', 'undated')} -- {a.get('headline', 'untitled')}", new_x="LMARGIN", new_y="NEXT")

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pdf.output(output_path)
        return None
    return pdf.output()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_export_pdf.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add src/mouse_research/export_pdf.py tests/test_export_pdf.py
git commit -m "feat: add PDF export for interview prep sheets"
```

---

### Task 6: Create Interview Prep Streamlit page

**Files:**
- Create: `pages/4_Interview_Prep.py`

- [ ] **Step 1: Create the Interview Prep page**

Create `pages/4_Interview_Prep.py`:

```python
"""Interview Prep — generate targeted documentary interview questions."""
import json
from datetime import date
from pathlib import Path

import streamlit as st

from ui_utils import (
    get_vault_path,
    load_articles,
    load_article_text,
    get_people_index,
    is_cloud_mode,
)

st.set_page_config(page_title="Interview Prep — MOUSE Research", page_icon="🎬", layout="wide")
st.title("🎬 Interview Prep")

vault_path = get_vault_path()
cloud = is_cloud_mode(vault_path)
articles = load_articles(vault_path)

if not articles:
    st.warning("No articles found. Run a search and analysis first.")
    st.stop()

people_index = get_people_index(articles)

# --- Person Selection ---
st.subheader("Select Person")

people_options = sorted(people_index.keys(), key=lambda p: len(people_index[p]), reverse=True)
people_labels = [f"{p} ({len(people_index[p])} articles)" for p in people_options]

search_text = st.text_input("🔍 Search for a person", placeholder="Type a name...")
if search_text:
    filtered_options = [p for p in people_options if search_text.lower() in p.lower()]
    filtered_labels = [f"{p} ({len(people_index[p])} articles)" for p in filtered_options]
else:
    filtered_options = people_options
    filtered_labels = people_labels

if not filtered_options:
    st.info("No people match your search.")
    st.stop()

selected_idx = st.selectbox(
    "Person",
    range(len(filtered_options)),
    format_func=lambda i: filtered_labels[i],
)
person_name = filtered_options[selected_idx]
person_articles = people_index[person_name]

# --- Article Timeline ---
st.subheader("Article Timeline")
st.caption(f"{len(person_articles)} articles mentioning {person_name}")

# Sort chronologically (oldest first to show career arc)
person_articles_sorted = sorted(person_articles, key=lambda a: a.get("date") or "0000-00-00")

# Article selection checkboxes
if "selected_articles" not in st.session_state:
    st.session_state.selected_articles = {}

selected_articles = []
for a in person_articles_sorted:
    slug = a.get("slug", "")
    date_str = a.get("date", "undated")
    headline = a.get("headline") or a.get("title") or slug
    schools = ", ".join(a.get("schools") or [])
    wrestling = "✅" if a.get("is_wrestling", True) else "⚠️"

    col1, col2 = st.columns([0.05, 0.95])
    with col1:
        checked = st.checkbox("", value=True, key=f"article_{slug}", label_visibility="collapsed")
    with col2:
        with st.expander(f"{wrestling} **{date_str}** — {headline} ({schools})"):
            summary = a.get("summary", "")
            if summary:
                st.write(summary)

    if checked:
        selected_articles.append(a)

st.caption(f"{len(selected_articles)} of {len(person_articles_sorted)} articles selected")

# --- Theme Selection ---
st.subheader("Themes & Angles")

# Detect available themes
all_people_in_articles = {p for a in person_articles for p in (a.get("people") or [])}
all_schools = {s for a in person_articles for s in (a.get("schools") or [])}
years = sorted({a.get("date", "")[:4] for a in person_articles if a.get("date")})
has_mcollum = any("McCollum" in p or "Mccollum" in p for p in all_people_in_articles)
surname = person_name.split()[-1] if " " in person_name else person_name
has_family = any(
    surname in p and p != person_name
    for p in people_index.keys()
)

themes = []
themes.append(st.checkbox("High school career", value=True))
theme_labels = ["High school career"]

if has_mcollum:
    themes.append(st.checkbox("Relationship with McCollum", value=True))
    theme_labels.append("Relationship with McCollum")

if len(years) > 1 and int(years[-1]) - int(years[0]) > 4:
    themes.append(st.checkbox("College/post-HS career", value=True))
    theme_labels.append("College/post-HS career")

themes.append(st.checkbox("Team moments & championships", value=True))
theme_labels.append("Team moments & championships")

themes.append(st.checkbox("Teaser sound bite", value=True))
theme_labels.append("Teaser sound bite")

if has_family:
    themes.append(st.checkbox("Family/program legacy", value=False))
    theme_labels.append("Family/program legacy")

selected_themes = [label for label, checked in zip(theme_labels, themes) if checked]

additional_context = st.text_area(
    "Additional context or angles",
    placeholder="e.g., 'Kyle is now a coach himself, ask about that'",
    height=80,
)

# --- Generation Controls ---
st.subheader("Generate")
col1, col2 = st.columns(2)
with col1:
    enrich = st.toggle("Enrich with web search", value=False)
with col2:
    fact_check = st.toggle("Fact-check questions", value=True)

generate_clicked = st.button("🎬 Generate Questions", type="primary", use_container_width=True)

# --- Generation ---
if generate_clicked:
    if not selected_articles:
        st.error("Select at least one article.")
        st.stop()
    if not selected_themes:
        st.error("Select at least one theme.")
        st.stop()

    # Load cleaned text for selected articles
    for a in selected_articles:
        slug = a.get("slug", "")
        if "cleaned_text" not in a:
            a["cleaned_text"] = load_article_text(slug, vault_path)

    with st.spinner(f"Generating interview questions for {person_name}..."):
        try:
            from mouse_research.interview_prep import generate_questions

            result = generate_questions(
                person_name=person_name,
                articles=selected_articles,
                themes=selected_themes,
                additional_context=additional_context,
                enrich=enrich,
                fact_check=fact_check,
            )
            st.session_state.prep_result = result
            st.session_state.prep_person = person_name
            st.session_state.prep_articles = selected_articles
        except ValueError as e:
            st.error(str(e))
            st.stop()
        except Exception as e:
            st.error(f"Generation failed: {e}")
            st.stop()

# --- Results Display ---
if "prep_result" in st.session_state and st.session_state.get("prep_person") == person_name:
    result = st.session_state.prep_result

    st.divider()
    st.subheader("Story Arc")
    st.write(result["story_arc"])

    st.subheader("Questions")

    # Initialize question order in session state
    if "prep_questions" not in st.session_state or generate_clicked:
        st.session_state.prep_questions = list(result["questions"])

    questions = st.session_state.prep_questions

    to_delete = None
    swap = None

    for i, q in enumerate(questions):
        col_ctrl, col_q = st.columns([0.08, 0.92])
        with col_ctrl:
            if i > 0 and st.button("↑", key=f"up_{i}"):
                swap = (i, i - 1)
            if i < len(questions) - 1 and st.button("↓", key=f"down_{i}"):
                swap = (i, i + 1)
            if st.button("✕", key=f"del_{i}"):
                to_delete = i

        with col_q:
            st.markdown(f"**{i + 1}. {q['question']}**")
            st.caption(q["context"])
            if q.get("fact_check_warning"):
                st.warning(f"⚠️ {q['fact_check_warning']}")

    # Handle reorder/delete
    if to_delete is not None:
        st.session_state.prep_questions.pop(to_delete)
        st.rerun()
    if swap:
        qs = st.session_state.prep_questions
        qs[swap[0]], qs[swap[1]] = qs[swap[1]], qs[swap[0]]
        st.rerun()

    # Add custom question
    with st.expander("Add a question"):
        new_q = st.text_input("Question", key="new_q_input")
        new_c = st.text_input("Context note", key="new_c_input", value="Custom question")
        if st.button("Add") and new_q:
            st.session_state.prep_questions.append({
                "question": new_q,
                "context": new_c,
                "fact_check_warning": None,
            })
            st.rerun()

    # --- Export ---
    st.divider()
    st.subheader("Export")

    col_pdf, col_vault = st.columns(2)

    with col_pdf:
        from mouse_research.export_pdf import generate_interview_pdf

        source_articles = [{"date": a.get("date", ""), "headline": a.get("headline", "")} for a in selected_articles]
        pdf_bytes = generate_interview_pdf(
            person_name=person_name,
            story_arc=result["story_arc"],
            questions=st.session_state.prep_questions,
            source_articles=source_articles,
        )
        st.download_button(
            "📄 Download PDF",
            data=pdf_bytes,
            file_name=f"Interview Prep - {person_name} - {date.today()}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    with col_vault:
        if not cloud:
            if st.button("💾 Save to Vault", use_container_width=True):
                prep_dir = Path(vault_path) / "Interview Prep"
                prep_dir.mkdir(exist_ok=True)
                filename = f"{person_name} - {date.today()}.md"
                filepath = prep_dir / filename

                # Build Obsidian note
                lines = [
                    "---",
                    "type: interview-prep",
                    f"person: {person_name}",
                    f"date: {date.today()}",
                    f"articles: {len(selected_articles)}",
                    "---",
                    "",
                    f"# Interview Prep — {person_name}",
                    "",
                    "## Story Arc",
                    result["story_arc"],
                    "",
                    "## Questions",
                ]
                for j, q in enumerate(st.session_state.prep_questions, 1):
                    lines.append(f"{j}. **{q['question']}**")
                    lines.append(f"   *{q['context']}*")
                    if q.get("fact_check_warning"):
                        lines.append(f"   ⚠️ {q['fact_check_warning']}")
                    lines.append("")

                warnings = [(j + 1, q["fact_check_warning"]) for j, q in enumerate(st.session_state.prep_questions) if q.get("fact_check_warning")]
                if warnings:
                    lines.append("## Fact-Check Notes")
                    for q_num, warning in warnings:
                        lines.append(f"- Q{q_num}: {warning}")
                    lines.append("")

                lines.append("## Source Articles")
                for a in sorted(selected_articles, key=lambda x: x.get("date", "")):
                    slug = a.get("slug", "")
                    headline = a.get("headline", "untitled")
                    lines.append(f"- [[{slug}|{headline}]]")

                filepath.write_text("\n".join(lines), encoding="utf-8")
                st.success(f"Saved to {filepath}")
        else:
            st.info("Save to Vault is only available in local mode.")
```

- [ ] **Step 2: Verify it loads without errors**

Run: `.venv/bin/streamlit run app.py --server.headless true` (Ctrl+C after it starts)
Expected: "You can now view your Streamlit app in your browser" — no import errors.

- [ ] **Step 3: Commit**

```bash
git add pages/4_Interview_Prep.py
git commit -m "feat: add Interview Prep page with person search, theme selection, and export"
```

---

### Task 7: Create cloud deployment files

**Files:**
- Create: `requirements-cloud.txt`
- Create: `.streamlit/config.toml`
- Create: `data/.gitkeep`

- [ ] **Step 1: Create requirements-cloud.txt**

```
streamlit
pandas
fpdf2
google-generativeai
```

- [ ] **Step 2: Create .streamlit/config.toml**

```toml
[theme]
primaryColor = "#4A90D9"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"

[server]
headless = true
```

- [ ] **Step 3: Create data directory with .gitkeep**

Run: `mkdir -p data && touch data/.gitkeep`

- [ ] **Step 4: Add data/articles.json to .gitignore exceptions**

Check if `.gitignore` exists and ensure `data/articles.json` is NOT ignored:

Run: `grep -n "data" .gitignore 2>/dev/null || echo "no gitignore or no data entry"`

If data/ is ignored, add `!data/articles.json` exception.

- [ ] **Step 5: Commit**

```bash
git add requirements-cloud.txt .streamlit/config.toml data/.gitkeep
git commit -m "chore: add cloud deployment files for Streamlit Community Cloud"
```

---

### Task 8: Run initial sync and smoke test

- [ ] **Step 1: Run sync to generate articles.json**

Run: `.venv/bin/mouse-research sync -v`
Expected: "Exported 992 articles to data/articles.json" (or similar count)

- [ ] **Step 2: Verify articles.json content**

Run: `.venv/bin/python -c "import json; d=json.load(open('data/articles.json')); print(f'{len(d)} articles, {sum(1 for a in d if a.get(\"cleaned_text\"))} with text')"`
Expected: Shows article count and cleaned text count

- [ ] **Step 3: Set Gemini API key**

Run: `export GEMINI_API_KEY="your-key-here"` (get from aistudio.google.com)

- [ ] **Step 4: Full smoke test**

Run: `.venv/bin/streamlit run app.py`
Verify in browser:
1. Interview Prep page appears in sidebar
2. Person search finds "Kyle Flickinger"
3. Article timeline shows his 11+ articles chronologically
4. Themes auto-detect (McCollum checkbox appears, Family checkbox appears)
5. Generate produces questions (requires Gemini API key)
6. Curation controls work (delete, reorder, add)
7. PDF download produces a readable file
8. Save to Vault creates the note

- [ ] **Step 5: Commit articles.json**

```bash
git add data/articles.json
git commit -m "data: initial sync of article data for cloud deployment"
```
