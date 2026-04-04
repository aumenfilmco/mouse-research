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
