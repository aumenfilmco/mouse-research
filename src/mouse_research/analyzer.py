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
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import ollama as _ollama_module

# Module-level reference so tests can mock it
ollama = _ollama_module

from mouse_research.logger import get_logger

_ANALYSIS_MODEL = "gemma4:e4b"

_ANALYSIS_PROMPT_TEMPLATE = """You are a newspaper text editor. The following text was extracted via OCR from a {date_year} Pennsylvania newspaper article ({source_name}, {date_str}).

The OCR has many errors. Please:
1. Rewrite the text to be readable and accurate. Fix garbled names, numbers, and grammar. Remove duplicated paragraphs.
2. "McCollum" is the correct spelling of the Bermudian Springs wrestling coach (OCR often garbles it as "McCullum", "McCullom", etc.)
3. "Bermudian Springs" is the correct school name (OCR often drops the "s")
4. High school wrestling weight classes are: 103, 112, 119, 125, 130, 135, 140, 145, 152, 160, 171, 189, 215, 275
5. After the corrected text, provide these fields on separate lines. Be concise and definitive — do not hedge or add parenthetical qualifiers:

HEADLINE: the best headline you can extract or construct (short, no commentary)
PEOPLE: comma-separated list of all people mentioned (use corrected names)
SCHOOLS: comma-separated list of all schools mentioned
WRESTLING: yes or no (is this article primarily about wrestling?)
SUMMARY: one sentence summary of the article

OCR TEXT:
{ocr_text}"""


def build_prompt(ocr_text: str, date: str, source: str) -> str:
    """Construct the analysis prompt for Gemma 4."""
    date_year = date[:4] if date and date != "undated" else "unknown year"
    return _ANALYSIS_PROMPT_TEMPLATE.format(
        date_year=date_year,
        source_name=source or "unknown newspaper",
        date_str=date or "undated",
        ocr_text=ocr_text,
    )


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
    """Parse Gemma 4's response into structured fields."""
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

    cleaned_text = "\n".join(cleaned_lines).strip()

    return AnalysisResult(
        cleaned_text=cleaned_text,
        headline=headline,
        people=people,
        schools=schools,
        is_wrestling=is_wrestling,
        summary=summary,
    )


def analyze_article(
    article_dir: Path,
    ollama_url: str = "http://localhost:11434",
    force: bool = False,
) -> bool:
    """Analyze a single article: read OCR, call Gemma 4, rewrite note.

    Returns True if article was analyzed, False if skipped.
    """
    logger = get_logger(__name__)
    meta_path = article_dir / "metadata.json"
    ocr_path = article_dir / "ocr_raw.md"

    if not meta_path.exists():
        logger.warning("No metadata.json in %s — skipping", article_dir.name)
        return False

    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    if meta.get("analyzed") and not force:
        return False

    if not ocr_path.exists():
        logger.warning("No ocr_raw.md in %s — skipping", article_dir.name)
        return False

    ocr_text = ocr_path.read_text(encoding="utf-8").strip()
    if not ocr_text:
        logger.warning("Empty ocr_raw.md in %s — skipping", article_dir.name)
        return False

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

    result = parse_response(response.response)

    meta["analyzed"] = True
    meta["headline"] = result.headline
    meta["people"] = result.people
    meta["schools"] = result.schools
    meta["is_wrestling"] = result.is_wrestling
    meta["summary"] = result.summary
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    _rewrite_article_note(article_dir, meta, result, ocr_text)

    logger.info(
        "Analyzed %s: wrestling=%s, people=%d, schools=%d",
        article_dir.name, result.is_wrestling, len(result.people), len(result.schools),
    )
    return True


def _rewrite_article_note(
    article_dir: Path,
    meta: dict,
    result: AnalysisResult,
    original_ocr: str,
) -> None:
    """Rewrite article.md with enriched content."""
    import frontmatter

    title = result.headline or meta.get("title", "Untitled")

    all_people = list(dict.fromkeys(meta.get("person", []) + result.people))
    people_links = ", ".join(f"[[{p}]]" for p in all_people) if all_people else ""
    school_links = ", ".join(f"[[{s}]]" for s in result.schools) if result.schools else ""
    source_link = f"[[{meta.get('source', 'Unknown')}]]"

    existing_notes = ""
    article_path = article_dir / "article.md"
    if article_path.exists():
        existing_text = article_path.read_text(encoding="utf-8")
        notes_marker = "## Notes"
        idx = existing_text.find(notes_marker)
        if idx != -1:
            after_marker = existing_text[idx + len(notes_marker):]
            existing_notes = after_marker.strip()

    body_parts = [f"# {title}", ""]
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
