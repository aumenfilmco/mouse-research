# `mouse-research analyze` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `analyze` CLI command that processes archived newspaper articles through Gemma 4 e4b (via Ollama) to clean OCR text, extract structured metadata (people, schools, wrestling flag, summary), and enrich Obsidian vault notes with wikilinks and frontmatter tags.

**Architecture:** New `analyzer.py` module handles all Gemma 4 interaction — reads `ocr_raw.md` and `metadata.json` from each article folder, sends OCR text to `gemma4:e4b` with a structured prompt, parses the response, then rewrites `article.md` and `metadata.json` with enriched data. CLI command in `cli.py` iterates over unanalyzed articles with a Rich progress bar. Existing `graph.py` is called after analysis to rebuild the index.

**Tech Stack:** Python 3.11+, Ollama Python SDK 0.6.1, Gemma 4 e4b model, Typer CLI, Rich progress, python-frontmatter

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/mouse_research/analyzer.py` | Create | Core analysis logic: prompt construction, Ollama call, response parsing, article rewriting |
| `src/mouse_research/cli.py` | Modify | Add `analyze` command with `--limit` and `--force` options |
| `tests/test_analyzer.py` | Create | Unit tests for prompt building, response parsing, article rewriting |

---

### Task 1: Create analyzer.py — prompt construction and response parsing

**Files:**
- Create: `src/mouse_research/analyzer.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: Write failing test for `build_prompt()`**

```python
# tests/test_analyzer.py
from mouse_research.analyzer import build_prompt

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_analyzer.py::test_build_prompt_includes_ocr_text -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mouse_research.analyzer'`

- [ ] **Step 3: Implement `build_prompt()`**

```python
# src/mouse_research/analyzer.py
"""Article analysis via Gemma 4 e4b.

Processes archived newspaper articles through a local LLM to:
- Clean up OCR text for readability
- Extract structured metadata (people, schools, events)
- Flag relevance (wrestling yes/no)
- Generate one-sentence summaries

Public API:
  build_prompt(ocr_text, date, source)  -- Construct the analysis prompt
  parse_response(response_text)         -- Parse LLM response into AnalysisResult
  analyze_article(article_dir, config)  -- Full single-article analysis pipeline
  analyze_batch(vault_path, config, limit, force)  -- Batch analysis with progress
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mouse_research.logger import get_logger

_ANALYSIS_PROMPT_TEMPLATE = """You are a newspaper text editor. The following text was extracted via OCR from a {date_year} Pennsylvania newspaper article ({source_name}, {date_str}).

The OCR has many errors. Please:
1. Rewrite the text to be readable and accurate. Fix garbled names, numbers, and grammar. Remove duplicated paragraphs.
2. "McCollum" is the correct spelling of the Bermudian Springs wrestling coach (OCR often garbles it as "McCullum", "McCullom", etc.)
3. "Bermudian Springs" is the correct school name (OCR often drops the "s")
4. High school wrestling weight classes are: 103, 112, 119, 125, 130, 135, 140, 145, 152, 160, 171, 189, 215, 275
5. After the corrected text, provide these fields on separate lines:

HEADLINE: the actual article headline (not a byline like "BY DAN CHRIST")
PEOPLE: comma-separated list of all people mentioned (use corrected names)
SCHOOLS: comma-separated list of all schools mentioned
WRESTLING: yes or no (is this article about wrestling?)
SUMMARY: one sentence summary of the article

OCR TEXT:
{ocr_text}"""


def build_prompt(ocr_text: str, date: str, source: str) -> str:
    """Construct the analysis prompt for Gemma 4.

    Args:
        ocr_text: Raw OCR text from ocr_raw.md
        date: ISO date string (YYYY-MM-DD) or "undated"
        source: Publication name (e.g. "The Gettysburg Times")

    Returns:
        Complete prompt string for ollama.generate()
    """
    date_year = date[:4] if date and date != "undated" else "unknown year"
    return _ANALYSIS_PROMPT_TEMPLATE.format(
        date_year=date_year,
        source_name=source or "unknown newspaper",
        date_str=date or "undated",
        ocr_text=ocr_text,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_analyzer.py::test_build_prompt_includes_ocr_text -v`
Expected: PASS

- [ ] **Step 5: Write failing test for `parse_response()`**

```python
# tests/test_analyzer.py (append)
from mouse_research.analyzer import parse_response

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
    assert result.is_wrestling is True  # default to True (conservative)
    assert result.summary == ""
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_analyzer.py -v`
Expected: 1 PASS, 2 FAIL (`ImportError` for `parse_response`)

- [ ] **Step 7: Implement `AnalysisResult` and `parse_response()`**

Add to `src/mouse_research/analyzer.py`:

```python
@dataclass
class AnalysisResult:
    """Parsed output from Gemma 4 analysis."""
    cleaned_text: str = ""
    headline: str = ""
    people: list[str] = field(default_factory=list)
    schools: list[str] = field(default_factory=list)
    is_wrestling: bool = True
    summary: str = ""


def parse_response(response_text: str) -> AnalysisResult:
    """Parse Gemma 4's response into structured fields.

    Expects free-form cleaned text followed by labeled lines:
    HEADLINE: ..., PEOPLE: ..., SCHOOLS: ..., WRESTLING: ..., SUMMARY: ...

    Lines not matching a label are treated as cleaned text.
    Missing labels get safe defaults (is_wrestling defaults True to avoid
    accidentally discarding wrestling articles).
    """
    lines = response_text.strip().splitlines()
    cleaned_lines: list[str] = []
    headline = ""
    people: list[str] = []
    schools: list[str] = []
    is_wrestling = True
    summary = ""

    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("HEADLINE:"):
            headline = stripped.split(":", 1)[1].strip()
        elif stripped.upper().startswith("PEOPLE:"):
            raw = stripped.split(":", 1)[1].strip()
            people = [p.strip() for p in raw.split(",") if p.strip()]
        elif stripped.upper().startswith("SCHOOLS:"):
            raw = stripped.split(":", 1)[1].strip()
            schools = [s.strip() for s in raw.split(",") if s.strip()]
        elif stripped.upper().startswith("WRESTLING:"):
            val = stripped.split(":", 1)[1].strip().lower()
            is_wrestling = val != "no"
        elif stripped.upper().startswith("SUMMARY:"):
            summary = stripped.split(":", 1)[1].strip()
        else:
            cleaned_lines.append(line)

    # Strip trailing blank lines from cleaned text
    cleaned_text = "\n".join(cleaned_lines).strip()

    return AnalysisResult(
        cleaned_text=cleaned_text,
        headline=headline,
        people=people,
        schools=schools,
        is_wrestling=is_wrestling,
        summary=summary,
    )
```

- [ ] **Step 8: Run all tests to verify they pass**

Run: `.venv/bin/pytest tests/test_analyzer.py -v`
Expected: 3 PASS

- [ ] **Step 9: Commit**

```bash
git add src/mouse_research/analyzer.py tests/test_analyzer.py
git commit -m "feat: add analyzer.py with prompt construction and response parsing"
```

---

### Task 2: Implement `analyze_article()` — single article analysis pipeline

**Files:**
- Modify: `src/mouse_research/analyzer.py`
- Create or modify: `tests/test_analyzer.py`

- [ ] **Step 1: Write failing test for `analyze_article()`**

```python
# tests/test_analyzer.py (append)
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from mouse_research.analyzer import analyze_article

def test_analyze_article_writes_enriched_note(tmp_path):
    """Test that analyze_article reads OCR, calls Ollama, and rewrites article.md."""
    # Set up a mock article directory
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

    # Mock Ollama response
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

    # Check metadata was updated
    meta = json.loads((article_dir / "metadata.json").read_text())
    assert meta["analyzed"] is True
    assert "Bermudian Springs" in meta["schools"]
    assert meta["is_wrestling"] is True
    assert "Bermudian Springs Wrestling Preview" in meta["headline"]

    # Check article.md was rewritten
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
    assert result is False  # skipped
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_analyzer.py::test_analyze_article_writes_enriched_note -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `analyze_article()`**

Add to `src/mouse_research/analyzer.py`:

```python
import ollama as _ollama_module

# Use a module-level reference so tests can mock it
ollama = _ollama_module

_ANALYSIS_MODEL = "gemma4:e4b"


def analyze_article(
    article_dir: Path,
    ollama_url: str = "http://localhost:11434",
    force: bool = False,
) -> bool:
    """Analyze a single article: read OCR, call Gemma 4, rewrite note.

    Args:
        article_dir: Path to article folder (contains ocr_raw.md, metadata.json, article.md)
        ollama_url: Ollama server URL
        force: If True, re-analyze even if already analyzed

    Returns:
        True if article was analyzed, False if skipped
    """
    logger = get_logger(__name__)
    meta_path = article_dir / "metadata.json"
    ocr_path = article_dir / "ocr_raw.md"

    # Load metadata
    if not meta_path.exists():
        logger.warning("No metadata.json in %s — skipping", article_dir.name)
        return False

    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # Skip already analyzed unless forced
    if meta.get("analyzed") and not force:
        return False

    # Load OCR text
    if not ocr_path.exists():
        logger.warning("No ocr_raw.md in %s — skipping", article_dir.name)
        return False

    ocr_text = ocr_path.read_text(encoding="utf-8").strip()
    if not ocr_text:
        logger.warning("Empty ocr_raw.md in %s — skipping", article_dir.name)
        return False

    # Build prompt and call Gemma 4
    prompt = build_prompt(
        ocr_text=ocr_text,
        date=meta.get("date", "undated"),
        source=meta.get("source", ""),
    )

    try:
        response = ollama.generate(
            model=_ANALYSIS_MODEL,
            prompt=prompt,
            options={"num_predict": 8000, "temperature": 0.1},
        )
    except Exception as e:
        logger.error("Ollama failed for %s: %s", article_dir.name, e)
        return False

    # Parse response
    result = parse_response(response.response)

    # Update metadata
    meta["analyzed"] = True
    meta["headline"] = result.headline
    meta["people"] = result.people
    meta["schools"] = result.schools
    meta["is_wrestling"] = result.is_wrestling
    meta["summary"] = result.summary
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Rewrite article.md
    _rewrite_article_note(article_dir, meta, result, ocr_text)

    logger.info(
        "Analyzed %s: wrestling=%s, people=%d, schools=%d",
        article_dir.name,
        result.is_wrestling,
        len(result.people),
        len(result.schools),
    )
    return True


def _rewrite_article_note(
    article_dir: Path,
    meta: dict,
    result: AnalysisResult,
    original_ocr: str,
) -> None:
    """Rewrite article.md with enriched content.

    New structure:
    - YAML frontmatter with analysis fields added
    - H1 title from cleaned headline (or original title)
    - People wikilinks, School wikilinks, Source wikilink
    - Summary section
    - Cleaned Text section (from Gemma 4)
    - Original OCR section (preserved for reference)
    - Notes section (preserved if present)
    """
    import frontmatter

    title = result.headline or meta.get("title", "Untitled")

    # Build wikilinks
    all_people = list(dict.fromkeys(meta.get("person", []) + result.people))
    people_links = ", ".join(f"[[{p}]]" for p in all_people) if all_people else ""
    school_links = ", ".join(f"[[{s}]]" for s in result.schools) if result.schools else ""
    source_link = f"[[{meta.get('source', 'Unknown')}]]"

    # Preserve existing notes section if present
    existing_notes = ""
    article_path = article_dir / "article.md"
    if article_path.exists():
        existing_text = article_path.read_text(encoding="utf-8")
        notes_marker = "## Notes"
        idx = existing_text.find(notes_marker)
        if idx != -1:
            after_marker = existing_text[idx + len(notes_marker):]
            existing_notes = after_marker.strip()

    # Build body
    body_parts = [
        f"# {title}",
        "",
    ]
    if people_links:
        body_parts.append(f"**People:** {people_links}")
    if school_links:
        body_parts.append(f"**Schools:** {school_links}")
    body_parts.append(f"**Source:** {source_link}")
    if not result.is_wrestling:
        body_parts.append("**Flag:** Not wrestling-related")
    body_parts.append("")
    body_parts.append("![[screenshot.png]]")

    if result.summary:
        body_parts += ["", "## Summary", "", result.summary]

    body_parts += ["", "## Cleaned Text", "", result.cleaned_text]
    body_parts += ["", "## Original OCR", "", original_ocr]
    body_parts += ["", "## Notes", ""]
    if existing_notes:
        body_parts.append(existing_notes)

    body = "\n".join(body_parts)

    # Build frontmatter — preserve existing fields, add new ones
    post = frontmatter.Post(
        body,
        person=all_people,
        source=meta.get("source", ""),
        date=meta.get("date"),
        url=meta.get("url", ""),
        tags=meta.get("tags", []),
        captured=meta.get("captured"),
        extraction=meta.get("extraction", ""),
        analyzed=True,
        headline=result.headline,
        people=result.people,
        schools=result.schools,
        is_wrestling=result.is_wrestling,
        summary=result.summary,
    )

    article_path.write_text(frontmatter.dumps(post), encoding="utf-8")
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `.venv/bin/pytest tests/test_analyzer.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/mouse_research/analyzer.py tests/test_analyzer.py
git commit -m "feat: implement analyze_article() with Ollama integration and note rewriting"
```

---

### Task 3: Add `analyze` CLI command

**Files:**
- Modify: `src/mouse_research/cli.py`

- [ ] **Step 1: Write failing test for CLI command existence**

```python
# tests/test_analyzer.py (append)
from typer.testing import CliRunner
from mouse_research.cli import app

runner = CliRunner()

def test_analyze_command_exists():
    result = runner.invoke(app, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "Process archived articles through Gemma 4" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_analyzer.py::test_analyze_command_exists -v`
Expected: FAIL — no such command "analyze"

- [ ] **Step 3: Add `analyze` command to cli.py**

Add to `src/mouse_research/cli.py`, after the `graph` command:

```python
@app.command()
def analyze(
    limit: Optional[int] = typer.Option(None, "--limit", help="Process only N articles (default: all unanalyzed)"),
    force: bool = typer.Option(False, "--force", help="Re-analyze already-analyzed articles"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    """Process archived articles through Gemma 4 for OCR cleanup and metadata extraction."""
    from mouse_research.config import get_config
    from mouse_research.logger import setup_logging
    from mouse_research.analyzer import analyze_article
    from rich.progress import Progress, SpinnerColumn, BarColumn, TaskProgressColumn, TextColumn

    setup_logging(verbose=verbose)
    config = get_config()

    articles_dir = Path(config.vault.path) / "Articles"
    if not articles_dir.exists():
        console.print("[red]No Articles directory found in vault.[/red]")
        raise typer.Exit(code=1)

    # Gather article directories (exclude _index.md and other non-directories)
    article_dirs = sorted(
        [d for d in articles_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )

    if limit:
        # When using --limit, filter to unanalyzed first (unless --force)
        if not force:
            import json as _json
            unanalyzed = []
            for d in article_dirs:
                meta_path = d / "metadata.json"
                if meta_path.exists():
                    meta = _json.loads(meta_path.read_text(encoding="utf-8"))
                    if not meta.get("analyzed"):
                        unanalyzed.append(d)
                else:
                    unanalyzed.append(d)
            article_dirs = unanalyzed[:limit]
        else:
            article_dirs = article_dirs[:limit]

    if not article_dirs:
        console.print("[yellow]No articles to analyze.[/yellow]")
        return

    console.print(f"Analyzing [bold]{len(article_dirs)}[/bold] articles with Gemma 4...")

    analyzed = 0
    skipped = 0
    failed = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[cyan]{task.fields[status]}"),
    ) as progress:
        task = progress.add_task("Analyzing", total=len(article_dirs), status="starting...")

        for article_dir in article_dirs:
            progress.update(task, status=article_dir.name[:40])
            try:
                result = analyze_article(
                    article_dir,
                    ollama_url=config.ocr.ollama_url,
                    force=force,
                )
                if result:
                    analyzed += 1
                else:
                    skipped += 1
            except Exception as e:
                console.print(f"[red]Error analyzing {article_dir.name}: {e}[/red]")
                failed += 1
            progress.advance(task)

    console.print(
        f"\nDone: [green]{analyzed} analyzed[/green], "
        f"[yellow]{skipped} skipped[/yellow], "
        f"[red]{failed} failed[/red]"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_analyzer.py::test_analyze_command_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mouse_research/cli.py
git commit -m "feat: add analyze CLI command with --limit and --force options"
```

---

### Task 4: Integration test — run on 20 real articles

This is a manual verification step, not an automated test.

- [ ] **Step 1: Verify Gemma 4 e4b is loaded**

Run: `curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin)['models']]"`
Expected: `gemma4:e4b` in the list

- [ ] **Step 2: Run analyze on 20 articles as a test**

Run: `caffeinate -dims & .venv/bin/mouse-research analyze --limit 20 --verbose`
Expected: Progress bar, ~60s per article, 20 analyzed

- [ ] **Step 3: Inspect results in Obsidian vault**

Check a few articles:
```bash
# Check an enriched metadata file
cat "/Users/aumen-server/Documents/Obsidian Vault/01-Aumen-Film-Co/Projects/MOUSE/Research/Articles/$(ls '/Users/aumen-server/Documents/Obsidian Vault/01-Aumen-Film-Co/Projects/MOUSE/Research/Articles/' | head -2 | tail -1)/metadata.json" | python3 -m json.tool

# Check an enriched article.md
head -40 "/Users/aumen-server/Documents/Obsidian Vault/01-Aumen-Film-Co/Projects/MOUSE/Research/Articles/$(ls '/Users/aumen-server/Documents/Obsidian Vault/01-Aumen-Film-Co/Projects/MOUSE/Research/Articles/' | head -2 | tail -1)/article.md"
```

Expected: metadata.json has `analyzed: true`, `headline`, `people`, `schools`, `is_wrestling`, `summary`. article.md has wikilinks, cleaned text, original OCR preserved.

- [ ] **Step 4: Review and adjust prompt if needed**

If the 20-article test reveals issues with the prompt (e.g. model consistently misidentifies fields, garbles output, or misses people), adjust `_ANALYSIS_PROMPT_TEMPLATE` in `analyzer.py` and re-run with `--force --limit 5`.

- [ ] **Step 5: Commit any prompt adjustments**

```bash
git add src/mouse_research/analyzer.py
git commit -m "fix: tune analysis prompt based on 20-article test run"
```

---

### Task 5: Rebuild graph after analysis

- [ ] **Step 1: Run graph rebuild to pick up new people/schools**

Run: `.venv/bin/mouse-research graph`
Expected: Index rebuilt with enriched metadata from analyzed articles

- [ ] **Step 2: Verify the index reflects analysis data**

```bash
head -30 "/Users/aumen-server/Documents/Obsidian Vault/01-Aumen-Film-Co/Projects/MOUSE/Research/Articles/_index.md"
```

Expected: Articles grouped by person, with enriched titles from `headline` field

- [ ] **Step 3: Commit if any graph changes needed**

If the graph rebuild reveals issues with how analyzed metadata integrates, fix in `graph.py` and commit.
