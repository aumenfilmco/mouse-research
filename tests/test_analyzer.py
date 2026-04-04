from mouse_research.analyzer import build_prompt, parse_response


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
