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
    assert output_path.stat().st_size > 100


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
