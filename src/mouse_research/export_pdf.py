"""PDF export for interview prep sheets using fpdf2."""
from datetime import date
from pathlib import Path

from fpdf import FPDF


def _sanitize(text: str) -> str:
    """Replace smart quotes and other Unicode chars that Helvetica can't render."""
    return (
        text
        .replace("\u2018", "'").replace("\u2019", "'")   # smart single quotes
        .replace("\u201c", '"').replace("\u201d", '"')   # smart double quotes
        .replace("\u2013", "-").replace("\u2014", "--")   # en/em dashes
        .replace("\u2026", "...").replace("\u00a0", " ")  # ellipsis, nbsp
        .replace("\u2022", "*")                           # bullet
    )


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
    """
    pdf = _InterviewPDF(person_name)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Story Arc
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "STORY ARC", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _sanitize(story_arc))
    pdf.ln(6)

    # Questions
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "QUESTIONS", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for i, q in enumerate(questions, 1):
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(0, 5, _sanitize(f"{i}. {q['question']}"))
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(pdf.l_margin + 6)
        pdf.multi_cell(0, 4.5, _sanitize(q['context']))
        if q.get("fact_check_warning"):
            pdf.set_text_color(200, 120, 0)
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_x(pdf.l_margin + 6)
            pdf.multi_cell(0, 4, _sanitize(f"* {q['fact_check_warning']}"))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

    # Fact-check footnotes
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
            pdf.multi_cell(0, 4.5, _sanitize(f"Q{q_num}: {warning}"))
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
        pdf.cell(0, 4.5, _sanitize(f"  {a.get('date', 'undated')} -- {a.get('headline', 'untitled')}"), new_x="LMARGIN", new_y="NEXT")

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pdf.output(output_path)
        return None
    return bytes(pdf.output())
