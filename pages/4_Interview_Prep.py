"""Interview Prep page for MOUSE Research Pipeline."""
import streamlit as st
from datetime import date
from pathlib import Path

from ui_utils import (
    get_vault_path,
    load_articles,
    load_article_text,
    get_people_index,
    is_cloud_mode,
)

st.set_page_config(
    page_title="Interview Prep — MOUSE Research",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 Interview Prep")

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
vault_path = get_vault_path()
cloud = is_cloud_mode(vault_path)
articles = load_articles(vault_path)

if not articles:
    st.warning("No articles found. Run a search and analysis pass first.")
    st.stop()

people_index = get_people_index(articles)

if not people_index:
    st.warning("No people found in articles. Run analysis first to extract names.")
    st.stop()

# ---------------------------------------------------------------------------
# Section 1: Person Selection
# ---------------------------------------------------------------------------
st.subheader("1. Select a Person")

search_query = st.text_input("Search for a person", placeholder="e.g. Flickinger")

# Sort people by article count descending
sorted_people = sorted(people_index.items(), key=lambda kv: len(kv[1]), reverse=True)

if search_query:
    q = search_query.lower()
    sorted_people = [(name, arts) for name, arts in sorted_people if q in name.lower()]

if not sorted_people:
    st.info("No people match your search.")
    st.stop()

person_options = [f"{name} ({len(arts)} articles)" for name, arts in sorted_people]
selected_option = st.selectbox("Person", person_options, label_visibility="collapsed")

# Extract selected person name
selected_idx = person_options.index(selected_option)
selected_name, person_articles = sorted_people[selected_idx]

# ---------------------------------------------------------------------------
# Section 2: Article Timeline
# ---------------------------------------------------------------------------
st.subheader("2. Article Timeline")

# Sort chronologically (oldest first — career arc)
person_articles_sorted = sorted(
    person_articles,
    key=lambda a: a.get("date") or "0000-00-00",
)

if "article_checks" not in st.session_state:
    st.session_state.article_checks = {}

# Reset checkboxes when person changes
person_key = f"person_{selected_name}"
if st.session_state.get("_current_person") != person_key:
    st.session_state._current_person = person_key
    st.session_state.article_checks = {
        a.get("slug", str(i)): True for i, a in enumerate(person_articles_sorted)
    }

selected_article_slugs = []
for i, article in enumerate(person_articles_sorted):
    slug = article.get("slug", str(i))
    col_check, col_detail = st.columns([0.05, 0.95])
    with col_check:
        checked = st.checkbox(
            label=f"article_{slug}",
            value=st.session_state.article_checks.get(slug, True),
            key=f"art_check_{slug}",
            label_visibility="collapsed",
        )
        st.session_state.article_checks[slug] = checked
    with col_detail:
        headline = article.get("headline") or article.get("title") or slug
        date_str = article.get("date", "undated")
        schools = ", ".join(article.get("schools") or [])
        summary = article.get("summary", "")
        with st.expander(f"{date_str} — {headline}", expanded=False):
            if schools:
                st.caption(f"Schools: {schools}")
            if summary:
                st.write(summary)
    if checked:
        selected_article_slugs.append(slug)

total = len(person_articles_sorted)
n_selected = len(selected_article_slugs)
st.caption(f"{n_selected} of {total} articles selected")

# ---------------------------------------------------------------------------
# Section 3: Theme Selection
# ---------------------------------------------------------------------------
st.subheader("3. Themes & Context")

# Compute derived flags for conditional themes
all_people_in_articles: list[str] = []
for a in person_articles_sorted:
    all_people_in_articles.extend(a.get("people") or [])

has_mccollum = any("McCollum" in p for p in all_people_in_articles)

dates_list = sorted(
    [a.get("date", "")[:4] for a in person_articles_sorted if a.get("date") and len(a.get("date", "")) >= 4]
)
year_span = (int(dates_list[-1]) - int(dates_list[0])) if len(dates_list) >= 2 else 0

# Check for family/program legacy: other people sharing the surname
selected_surname = selected_name.split()[-1] if selected_name else ""
shares_surname = any(
    p != selected_name and p.split()[-1] == selected_surname
    for p in all_people_in_articles
) if selected_surname else False

# Theme checkboxes
themes_selected = []

hs_career = st.checkbox("High school career", value=True, key="theme_hs")
if hs_career:
    themes_selected.append("High school career")

if has_mccollum:
    rel_mc = st.checkbox("Relationship with McCollum", value=True, key="theme_mc")
    if rel_mc:
        themes_selected.append("Relationship with McCollum")

if year_span > 4:
    col_career = st.checkbox("College/post-HS career", value=True, key="theme_college")
    if col_career:
        themes_selected.append("College/post-HS career")

team_moments = st.checkbox("Team moments & championships", value=True, key="theme_team")
if team_moments:
    themes_selected.append("Team moments & championships")

teaser = st.checkbox("Teaser sound bite", value=True, key="theme_teaser")
if teaser:
    themes_selected.append("Teaser sound bite")

if shares_surname:
    family = st.checkbox("Family/program legacy", value=True, key="theme_family")
    if family:
        themes_selected.append("Family/program legacy")

additional_context = st.text_area(
    "Additional context (optional)",
    placeholder="e.g. He is now a coach at Bermudian Springs.",
    height=80,
)

# ---------------------------------------------------------------------------
# Section 4: Generation Controls
# ---------------------------------------------------------------------------
st.subheader("4. Generate Questions")

col_enrich, col_factcheck = st.columns(2)
with col_enrich:
    enrich = st.toggle("Enrich with web search", value=False)
with col_factcheck:
    fact_check = st.toggle("Fact-check questions", value=True)

generate_clicked = st.button("Generate Questions", type="primary", disabled=(n_selected == 0 or not themes_selected))

if n_selected == 0:
    st.caption("Select at least one article to generate questions.")
elif not themes_selected:
    st.caption("Select at least one theme.")

# ---------------------------------------------------------------------------
# Section 5: Generation
# ---------------------------------------------------------------------------
if generate_clicked:
    # Load cleaned text for each selected article
    selected_articles_with_text = []
    slug_to_article = {a.get("slug", str(i)): a for i, a in enumerate(person_articles_sorted)}

    for slug in selected_article_slugs:
        article = dict(slug_to_article.get(slug, {}))
        text = load_article_text(slug, vault_path)
        article["cleaned_text"] = text
        selected_articles_with_text.append(article)

    with st.spinner(f"Generating questions for {selected_name}…"):
        try:
            from mouse_research.interview_prep import generate_questions
            result = generate_questions(
                person_name=selected_name,
                articles=selected_articles_with_text,
                themes=themes_selected,
                additional_context=additional_context,
                enrich=enrich,
                fact_check=fact_check,
            )
            # Attach fact_check_warning=None to each question if missing
            for q in result.get("questions", []):
                q.setdefault("fact_check_warning", None)

            st.session_state.interview_result = result
            st.session_state.interview_person = selected_name
            st.session_state.interview_articles = selected_articles_with_text
            st.session_state._questions_gen_id = st.session_state.get("_questions_gen_id", 0) + 1
            st.session_state.interview_source_articles = [
                {"date": a.get("date", ""), "headline": a.get("headline") or a.get("title") or a.get("slug", ""), "slug": a.get("slug", "")}
                for a in selected_articles_with_text
            ]
        except ValueError as e:
            st.error(f"API key error: {e}")
            st.stop()
        except Exception as e:
            st.error(f"Generation failed: {e}")
            st.stop()

# ---------------------------------------------------------------------------
# Section 6: Results Display
# ---------------------------------------------------------------------------
if "interview_result" in st.session_state and st.session_state.get("interview_person") == selected_name:
    result = st.session_state.interview_result
    questions: list[dict] = result.get("questions", [])

    st.divider()
    st.subheader("Story Arc")
    st.write(result.get("story_arc", ""))

    if result.get("enrichment"):
        with st.expander("Web Enrichment"):
            st.write(result["enrichment"])

    st.subheader("Questions")

    # Initialize curation state from latest generation result
    # Use a generation counter to detect new results vs. cached ones
    current_gen = st.session_state.get("_questions_gen_id", 0)
    if (
        "interview_questions" not in st.session_state
        or st.session_state.get("_questions_person") != selected_name
        or st.session_state.get("_questions_gen_applied") != current_gen
    ):
        st.session_state.interview_questions = list(questions)
        st.session_state._questions_person = selected_name
        st.session_state._questions_gen_applied = current_gen

    curated: list[dict] = st.session_state.interview_questions

    for idx, q in enumerate(curated):
        col_q, col_up, col_down, col_del = st.columns([0.82, 0.05, 0.05, 0.08])
        with col_q:
            st.markdown(f"**{idx + 1}. {q['question']}**")
            if q.get("context"):
                st.caption(q["context"])
            if q.get("fact_check_warning"):
                st.warning(q["fact_check_warning"])
        with col_up:
            if idx > 0 and st.button("↑", key=f"up_{idx}", help="Move up"):
                curated[idx - 1], curated[idx] = curated[idx], curated[idx - 1]
                st.session_state.interview_questions = curated
                st.rerun()
        with col_down:
            if idx < len(curated) - 1 and st.button("↓", key=f"down_{idx}", help="Move down"):
                curated[idx], curated[idx + 1] = curated[idx + 1], curated[idx]
                st.session_state.interview_questions = curated
                st.rerun()
        with col_del:
            if st.button("✕", key=f"del_{idx}", help="Delete question"):
                curated.pop(idx)
                st.session_state.interview_questions = curated
                st.rerun()

    # Add custom question
    st.markdown("---")
    new_q_text = st.text_input("Add a question", placeholder="Type a custom question…", key="new_question_input")
    if st.button("Add Question") and new_q_text.strip():
        curated.append({"question": new_q_text.strip(), "context": "", "fact_check_warning": None})
        st.session_state.interview_questions = curated
        st.rerun()

    # Fact-check raw output
    if result.get("factcheck"):
        with st.expander("Raw Fact-Check Output"):
            st.text(result["factcheck"])

    # ---------------------------------------------------------------------------
    # Section 7: Export
    # ---------------------------------------------------------------------------
    st.divider()
    st.subheader("Export")

    source_articles = st.session_state.get("interview_source_articles", [])
    story_arc = result.get("story_arc", "")
    export_questions = st.session_state.interview_questions

    from mouse_research.export_pdf import generate_interview_pdf

    pdf_bytes = generate_interview_pdf(
        person_name=selected_name,
        story_arc=story_arc,
        questions=export_questions,
        source_articles=source_articles,
    )

    col_pdf, col_vault = st.columns(2)

    with col_pdf:
        safe_name = selected_name.replace(" ", "_")
        today_str = date.today().strftime("%Y-%m-%d")
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name=f"Interview_Prep_{safe_name}_{today_str}.pdf",
            mime="application/pdf",
        )

    with col_vault:
        if cloud:
            st.button("Save to Vault", disabled=True, help="Not available in cloud mode")
        else:
            if st.button("Save to Vault"):
                # Build markdown content
                questions_md = ""
                for i, q in enumerate(export_questions, 1):
                    questions_md += f"\n{i}. **{q['question']}**\n"
                    if q.get("context"):
                        questions_md += f"   *{q['context']}*\n"

                factcheck_notes = [
                    (i, q["fact_check_warning"])
                    for i, q in enumerate(export_questions, 1)
                    if q.get("fact_check_warning")
                ]
                factcheck_md = ""
                if factcheck_notes:
                    factcheck_md = "\n## Fact-Check Notes\n"
                    for q_num, warning in factcheck_notes:
                        factcheck_md += f"- Q{q_num}: {warning}\n"

                source_articles_md = "\n## Source Articles\n"
                for a in source_articles:
                    slug = a.get("slug", "")
                    headline = a.get("headline", "untitled")
                    if slug:
                        source_articles_md += f"- [[{slug}|{headline}]]\n"
                    else:
                        source_articles_md += f"- {headline}\n"

                note_content = f"""---
type: interview-prep
person: {selected_name}
date: {date.today().isoformat()}
articles: {len(source_articles)}
---

# Interview Prep — {selected_name}

## Story Arc
{story_arc}

## Questions
{questions_md}
{factcheck_md}
{source_articles_md}"""

                save_dir = Path(vault_path) / "Interview Prep"
                save_dir.mkdir(parents=True, exist_ok=True)
                filename = f"{selected_name} - {date.today().isoformat()}.md"
                save_path = save_dir / filename
                save_path.write_text(note_content, encoding="utf-8")
                st.success(f"Saved to vault: Interview Prep/{filename}")
