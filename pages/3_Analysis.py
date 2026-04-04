# pages/3_Analysis.py
"""Run Gemma 4 analysis on archived articles."""
import subprocess
import sys
import streamlit as st
from ui_utils import get_vault_path, load_articles

st.set_page_config(page_title="Analysis — MOUSE Research", page_icon="🤖")
st.title("🤖 Run Analysis")

vault_path = get_vault_path()
articles = load_articles(vault_path)

total = len(articles)
analyzed = sum(1 for a in articles if a.get("analyzed", False))
remaining = total - analyzed

# Status
col1, col2, col3 = st.columns(3)
col1.metric("Total Articles", total)
col2.metric("Analyzed", analyzed)
col3.metric("Remaining", remaining)

if total > 0:
    st.progress(analyzed / total, text=f"{analyzed}/{total} analyzed ({analyzed*100//total}%)")

st.divider()

if remaining == 0:
    st.success("All articles have been analyzed!")
    if st.button("Re-analyze all (force)"):
        with st.spinner("Re-analyzing all articles..."):
            result = subprocess.run(
                [sys.executable, "-m", "mouse_research.cli", "analyze", "--force", "--verbose"],
                capture_output=True,
                text=True,
                timeout=86400,
                cwd=str(__import__("pathlib").Path(__file__).parent.parent),
            )
        if result.returncode == 0:
            st.success("Re-analysis complete!")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Analysis failed.")
            st.code(result.stderr[-1000:])
else:
    st.subheader("Analyze Articles")

    limit = st.number_input(
        "Number of articles to analyze",
        min_value=1,
        max_value=remaining,
        value=min(50, remaining),
        step=10,
    )

    force = st.checkbox("Re-analyze already analyzed articles", value=False)

    if st.button("🚀 Start Analysis", type="primary"):
        cmd = [sys.executable, "-m", "mouse_research.cli", "analyze", "--limit", str(limit)]
        if force:
            cmd.append("--force")
        cmd.append("--verbose")

        st.markdown(f"**Running:** `{' '.join(cmd)}`")
        st.info(f"Analyzing {limit} articles with Gemma 4 e4b. This will take approximately {limit} minutes.")

        with st.spinner(f"Analyzing {limit} articles..."):
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=86400,
                cwd=str(__import__("pathlib").Path(__file__).parent.parent),
            )

        if result.returncode == 0:
            output_lines = result.stdout.strip().splitlines()
            summary_line = output_lines[-1] if output_lines else "Complete"
            st.success(f"Analysis complete! {summary_line}")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Analysis failed.")
            if result.stderr:
                st.code(result.stderr[-1000:])

st.divider()

# Rebuild graph button
st.subheader("Rebuild Research Graph")
st.caption("Regenerate the article index, People notes, and Source notes after analysis.")

if st.button("🕸️ Rebuild Graph"):
    with st.spinner("Rebuilding graph..."):
        result = subprocess.run(
            [sys.executable, "-m", "mouse_research.cli", "graph"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(__import__("pathlib").Path(__file__).parent.parent),
        )
    if result.returncode == 0:
        st.success("Graph rebuilt!")
    else:
        st.error("Graph rebuild failed.")
        st.code(result.stderr[-500:])
