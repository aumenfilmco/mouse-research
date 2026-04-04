# pages/2_Search.py
"""Launch a new Newspapers.com search."""
import subprocess
import sys
import streamlit as st

st.set_page_config(page_title="Search — MOUSE Research", page_icon="🔍")
st.title("🔍 New Search")

st.markdown("Search Newspapers.com and archive results directly into the vault.")

# Form
with st.form("search_form"):
    keyword = st.text_input(
        "Keyword *",
        placeholder='"Dave McCollum" Bermudian wrestling',
        help="Use quotes for exact phrases",
    )
    col1, col2 = st.columns(2)
    with col1:
        years = st.text_input("Years", placeholder="1977-2025", help="Single year or range: 1980 or 1975-1985")
    with col2:
        location = st.selectbox(
            "Location",
            ["", "Pennsylvania", "New York", "Maryland", "New Jersey", "Delaware", "Virginia", "West Virginia", "Ohio"],
        )
    col3, col4 = st.columns(2)
    with col3:
        person = st.text_input("Person tag", placeholder="Dave McCollum", help="Tag articles with this person name")
    with col4:
        auto_archive = st.checkbox("Auto-archive all results", value=True)

    submitted = st.form_submit_button("🔍 Search", type="primary")

if submitted:
    if not keyword:
        st.error("Keyword is required.")
        st.stop()

    cmd = [sys.executable, "-m", "mouse_research.cli", "search", keyword]
    if years:
        cmd += ["--years", years]
    if location:
        cmd += ["--location", location]
    if person:
        cmd += ["--person", person]
    if auto_archive:
        cmd.append("--auto-archive")

    st.markdown(f"**Running:** `{' '.join(cmd)}`")

    with st.spinner("Searching Newspapers.com... this may take a few minutes."):
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(__import__("pathlib").Path(__file__).parent.parent),
        )

    if result.returncode == 0:
        st.success("Search complete!")
        st.text(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
        st.cache_data.clear()
    else:
        st.error(f"Search failed (exit code {result.returncode})")
        if result.stderr:
            st.code(result.stderr[-1000:])
