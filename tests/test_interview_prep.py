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
