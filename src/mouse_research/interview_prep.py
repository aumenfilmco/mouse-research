"""Interview preparation module for MOUSE documentary.

Generates interview questions for subjects using Gemini Flash 2.0,
based on newspaper article research and selected themes.
"""
import os
import re
from typing import Any

from mouse_research.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a documentary interview researcher for MOUSE: 50 Years on the Mat, a film about Dave McCollum and the Bermudian Springs Eagles wrestling program in Adams County, Pennsylvania.

Your role is to craft thoughtful, specific interview questions for subjects who appear in the newspaper archive research. Questions should:
- Ground the subject in concrete memories and moments, not generalities
- Surface the emotional truth behind the stats and headlines
- Reveal McCollum's coaching philosophy and its lasting impact
- Connect individual stories to the larger MOUSE documentary narrative
- Include at least one "teaser sound bite" question designed for a compelling trailer moment

The documentary centers on Dave McCollum's decades of coaching at Bermudian Springs High School, the wrestlers he shaped, and what that program meant to a small Pennsylvania community. Keep this focus at the heart of every question set.
"""


def build_question_prompt(
    person_name: str,
    articles: list[dict],
    themes: list[str],
    additional_context: str = "",
) -> str:
    """Build a prompt to generate interview questions for a documentary subject.

    Args:
        person_name: Full name of the interview subject.
        articles: List of article dicts with keys: slug, date, headline, cleaned_text.
        themes: Selected question themes (e.g. "High school career", "Teaser sound bite").
        additional_context: Optional extra background on the subject.

    Returns:
        Prompt string ready for the LLM.
    """
    articles_section = ""
    for article in articles:
        articles_section += (
            f"\n---\nDate: {article.get('date', 'unknown')}\n"
            f"Headline: {article.get('headline', '')}\n"
            f"Text: {article.get('cleaned_text', '')}\n"
        )

    themes_section = "\n".join(f"- {theme}" for theme in themes)

    context_section = ""
    if additional_context:
        context_section = f"\nAdditional context about {person_name}:\n{additional_context}\n"

    return f"""Generate documentary interview questions for {person_name} based on the newspaper articles below.

SELECTED THEMES:
{themes_section}
{context_section}
NEWSPAPER ARTICLES:
{articles_section}

Generate 5-8 questions that cover the selected themes. Make each question specific to details found in the articles. Include at least one "Teaser sound bite" question.

YOU MUST USE THIS EXACT FORMAT with each field on its own line:

STORY_ARC: A 2-3 sentence summary of {person_name}'s narrative arc based on the articles.

QUESTION: First interview question here?
CONTEXT: Why this question matters and what answer we hope to draw out.

QUESTION: Second interview question here?
CONTEXT: Why this question matters and what answer we hope to draw out.

QUESTION: Third interview question here?
CONTEXT: Why this question matters and what answer we hope to draw out.

Do NOT combine questions into paragraphs. Each QUESTION: and CONTEXT: must start on its own line. Do NOT use numbered lists or markdown formatting.
"""


def build_enrichment_prompt(
    person_name: str,
    schools: list[str],
    years: list[str],
) -> str:
    """Build a web search enrichment prompt to find additional background on a subject.

    Args:
        person_name: Full name of the subject.
        schools: Schools associated with the subject.
        years: Relevant years for context.

    Returns:
        Prompt string for web-grounded LLM call.
    """
    schools_str = ", ".join(schools)
    years_str = ", ".join(years)

    return f"""Search for additional information about {person_name} to enrich documentary interview preparation.

Context:
- Schools: {schools_str}
- Relevant years: {years_str}
- Documentary subject: MOUSE: 50 Years on the Mat (Bermudian Springs wrestling, Dave McCollum)

Please find:
1. Career wrestling statistics — check pa-wrestling.com for detailed high school records (wins, losses, state placements by year, weight classes)
2. Post-season results: sectional, district, regional, and PIAA state tournament placements each year
3. College career details if applicable (school, weight class, record)
4. Current occupation or whereabouts (if publicly available)
5. Any notable post-high-school accomplishments related to wrestling or coaching
6. Any other publicly available context useful for a documentary interview

Key sources to check: pa-wrestling.com, PennLive high school wrestling archives, school athletic records.

Summarize findings in 2–3 paragraphs. Cite sources where possible.
"""


def build_factcheck_prompt(
    person_name: str,
    questions: list[dict],
) -> str:
    """Build a fact-check prompt to verify claims embedded in interview questions.

    Args:
        person_name: Full name of the subject.
        questions: List of question dicts with keys: question, context.

    Returns:
        Prompt string for fact-checking LLM call.
    """
    questions_section = ""
    for i, q in enumerate(questions, 1):
        questions_section += (
            f"\nQ{i}: {q.get('question', '')}\n"
            f"Context: {q.get('context', '')}\n"
        )

    return f"""Fact-check the following interview questions prepared for {person_name} in the MOUSE documentary about Bermudian Springs wrestling and Dave McCollum.

QUESTIONS TO VERIFY:
{questions_section}

For each question, identify:
1. Any specific claims (records, dates, names, stats) that need verification
2. Whether the claim appears accurate based on available sources
3. Suggested correction if the claim appears wrong
4. Confidence level: HIGH / MEDIUM / LOW

If a question contains no verifiable claims, note "No specific claims to verify."
"""


def parse_questions_response(response_text: str) -> dict:
    """Parse structured question output from LLM response.

    Handles two formats:
    1. Strict: STORY_ARC: / QUESTION: / CONTEXT: tags
    2. Markdown fallback: numbered lists with bold questions and italic/plain context

    Args:
        response_text: Raw LLM response string.

    Returns:
        Dict with keys:
            - story_arc (str): The narrative arc summary.
            - questions (list[dict]): Each dict has "question" and "context" keys.
    """
    logger.debug("Raw LLM response:\n%s", response_text[:2000])
    result: dict[str, Any] = {"story_arc": "", "questions": []}

    # --- Try QUESTION:/CONTEXT: format (with or without preceding newline) ---
    arc_match = re.search(r"STORY_ARC:\s*(.+?)(?=\s*QUESTION:|\Z)", response_text, re.DOTALL)
    if arc_match:
        result["story_arc"] = arc_match.group(1).strip().strip("*")

    # Split on QUESTION: (allow it to appear mid-line or after newline)
    question_blocks = re.split(r"QUESTION:\s*", response_text)
    for block in question_blocks[1:]:
        context_split = re.split(r"CONTEXT:\s*", block, maxsplit=1)
        question_text = context_split[0].strip()
        context_text = context_split[1].strip() if len(context_split) > 1 else ""
        # Clean up: remove anything after the next tag
        question_text = re.split(r"(?:QUESTION|STORY_ARC|CONTEXT):", question_text)[0].strip()
        context_text = re.split(r"(?:QUESTION|STORY_ARC):", context_text)[0].strip()
        # Strip markdown artifacts
        question_text = question_text.strip("*").strip()
        context_text = context_text.strip("*").strip()
        if question_text:
            result["questions"].append({"question": question_text, "context": context_text})

    if result["questions"]:
        return result

    # --- Fallback: parse markdown-style output ---
    logger.info("Strict format not found, trying markdown fallback parser")

    # Try to extract story arc from first paragraph or **Story Arc** section
    if not result["story_arc"]:
        arc_match = re.search(
            r"(?:\*\*\s*Story\s*Arc\s*\*\*|##\s*Story\s*Arc|STORY.ARC)[:\s]*(.+?)(?=\n\s*(?:\d+\.|##|\*\*\s*Question)|\Z)",
            response_text, re.DOTALL | re.IGNORECASE,
        )
        if arc_match:
            result["story_arc"] = re.sub(r"\*+", "", arc_match.group(1)).strip()

    # If still no story arc, use the first paragraph
    if not result["story_arc"]:
        paragraphs = response_text.strip().split("\n\n")
        if paragraphs:
            candidate = re.sub(r"\*+", "", paragraphs[0]).strip()
            # Only use if it looks like prose, not a question
            if len(candidate) > 40 and "?" not in candidate[:50]:
                result["story_arc"] = candidate

    # Extract numbered questions: "1. **question**" or "1. question"
    # Pattern: number + dot + optional bold markers + question text
    q_pattern = re.compile(
        r"^\s*(\d+)\.\s*\**\s*(.+?)\s*\**\s*$",
        re.MULTILINE,
    )
    lines = response_text.split("\n")
    i = 0
    while i < len(lines):
        m = q_pattern.match(lines[i])
        if m:
            question_text = re.sub(r"\*+", "", m.group(2)).strip().rstrip("*")
            # Look for context in subsequent lines (indented, italic, or starting with >)
            context_lines = []
            j = i + 1
            while j < len(lines):
                line = lines[j].strip()
                if not line:
                    j += 1
                    continue
                # Stop if we hit the next numbered question
                if re.match(r"^\s*\d+\.\s", lines[j]):
                    break
                # Context lines: italic, indented, quoted, or starting with "Context:" etc.
                cleaned = re.sub(r"^\s*[>*_]+\s*", "", line)
                cleaned = re.sub(r"[*_]+$", "", cleaned).strip()
                if cleaned.lower().startswith("context:"):
                    cleaned = cleaned[8:].strip()
                context_lines.append(cleaned)
                j += 1

            context_text = " ".join(context_lines).strip()
            if question_text:
                result["questions"].append({"question": question_text, "context": context_text})
            i = j
        else:
            i += 1

    return result


def _get_api_key() -> str:
    """Retrieve Gemini API key from Streamlit secrets or environment variable."""
    try:
        import streamlit as st
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return key
    except Exception:
        pass

    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key

    raise ValueError(
        "GEMINI_API_KEY not found. Set it in Streamlit secrets or the GEMINI_API_KEY environment variable."
    )


def generate_questions(
    person_name: str,
    articles: list[dict],
    themes: list[str],
    additional_context: str = "",
    enrich: bool = False,
    fact_check: bool = True,
) -> dict:
    """Generate documentary interview questions using Gemini Flash 2.0.

    Full pipeline:
    1. Optionally enrich context with web search grounding.
    2. Generate questions from article research and themes.
    3. Optionally fact-check the generated questions.

    Args:
        person_name: Full name of the interview subject.
        articles: List of article dicts with slug, date, headline, cleaned_text.
        themes: Selected question themes.
        additional_context: Optional extra background on the subject.
        enrich: If True, run a web-grounded enrichment call first.
        fact_check: If True, run a fact-check pass on generated questions.

    Returns:
        Dict with:
            - story_arc (str)
            - questions (list[dict] with "question" and "context")
            - enrichment (str | None): Enrichment summary if enrich=True.
            - factcheck (str | None): Fact-check output if fact_check=True.
    """
    from google import genai
    from google.genai import types

    api_key = _get_api_key()
    client = genai.Client(api_key=api_key)

    enrichment_text: str | None = None
    if enrich:
        logger.info("Running web enrichment for %s", person_name)
        # Collect schools and years from articles
        schools: list[str] = ["Bermudian Springs"]
        years: list[str] = sorted({
            a["date"][:4] for a in articles if a.get("date") and len(a["date"]) >= 4
        })
        enrichment_prompt = build_enrichment_prompt(person_name, schools, years)
        enrich_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=enrichment_prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        enrichment_text = enrich_response.text
        logger.debug("Enrichment result: %s", enrichment_text[:200] if enrichment_text else "")
        if enrichment_text and not additional_context:
            additional_context = enrichment_text
        elif enrichment_text:
            additional_context = f"{additional_context}\n\nWeb research:\n{enrichment_text}"

    logger.info("Generating questions for %s (%d articles, %d themes)", person_name, len(articles), len(themes))
    question_prompt = build_question_prompt(person_name, articles, themes, additional_context)
    q_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=question_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.7,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    raw_text = q_response.text
    logger.info("Raw question response (%d chars): %s", len(raw_text), raw_text[:500])
    parsed = parse_questions_response(raw_text)

    factcheck_text: str | None = None
    if fact_check and parsed["questions"]:
        logger.info("Running fact-check for %s (%d questions)", person_name, len(parsed["questions"]))
        fc_prompt = build_factcheck_prompt(person_name, parsed["questions"])
        fc_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=fc_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        factcheck_text = fc_response.text

    return {
        "story_arc": parsed["story_arc"],
        "questions": parsed["questions"],
        "enrichment": enrichment_text,
        "factcheck": factcheck_text,
    }
