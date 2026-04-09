# pages/1_Articles.py
"""Browse and filter archived articles."""
import streamlit as st
import pandas as pd
from ui_utils import get_vault_path, load_articles, articles_to_dataframe, load_article_text

st.set_page_config(page_title="Articles — MOUSE Research", page_icon="📰", layout="wide")
st.title("📰 Browse Articles")

vault_path = get_vault_path()
articles = load_articles(vault_path)

if not articles:
    st.warning("No articles found.")
    st.stop()

# --- Filters ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    search_text = st.text_input("🔍 Search", placeholder="keyword...")

with col2:
    wrestling_filter = st.selectbox("Wrestling", ["All", "Wrestling only", "Non-wrestling only"])

with col3:
    all_schools = sorted(set(s for a in articles for s in (a.get("schools") or [])))
    school_filter = st.multiselect("Schools", all_schools)

with col4:
    dates = [a.get("date", "")[:4] for a in articles if a.get("date")]
    if dates:
        min_year, max_year = int(min(dates)), int(max(dates))
        year_range = st.slider("Years", min_year, max_year, (min_year, max_year))
    else:
        year_range = (1900, 2100)

# --- Apply filters ---
filtered = articles

if search_text:
    q = search_text.lower()
    filtered = [
        a for a in filtered
        if q in (a.get("headline") or "").lower()
        or q in (a.get("summary") or "").lower()
        or q in (a.get("title") or "").lower()
    ]

if wrestling_filter == "Wrestling only":
    filtered = [a for a in filtered if a.get("is_wrestling", True)]
elif wrestling_filter == "Non-wrestling only":
    filtered = [a for a in filtered if not a.get("is_wrestling", True)]

if school_filter:
    filtered = [
        a for a in filtered
        if any(s in (a.get("schools") or []) for s in school_filter)
    ]

filtered = [
    a for a in filtered
    if a.get("date") and year_range[0] <= int(a["date"][:4]) <= year_range[1]
]

st.caption(f"Showing {len(filtered)} of {len(articles)} articles")

# --- Table ---
if not filtered:
    st.info("No articles match your filters.")
    st.stop()

df = articles_to_dataframe(filtered)

# Display table with single-row selection — click a row to view details below.
display_cols = ["Date", "Headline", "Schools", "Wrestling"]
selection = st.dataframe(
    df[display_cols],
    use_container_width=True,
    hide_index=True,
    height=400,
    on_select="rerun",
    selection_mode="single-row",
    key="articles_table",
)

selected_rows = selection.selection.rows if selection and selection.selection else []

# --- Detail view ---
st.subheader("Article Details")

if not selected_rows:
    st.caption("Click a row above to view details.")
else:
    row_idx = selected_rows[0]
    row = df.iloc[row_idx]
    article = filtered[row_idx]

    wrestling_badge = "✅ Wrestling" if row["_is_wrestling"] else "⚠️ Not wrestling"
    analyzed_badge = "🤖 Analyzed" if row["_analyzed"] else "📝 Not analyzed"

    st.markdown(f"### {row['Headline']}")
    st.caption(f"{row['Date']} · {row['Source']} · {wrestling_badge} · {analyzed_badge}")

    if row["People"]:
        st.markdown(f"**People:** {row['People']}")
    if row["Schools"]:
        st.markdown(f"**Schools:** {row['Schools']}")

    if row["Summary"]:
        st.markdown("**Summary**")
        st.write(row["Summary"])

    # Load cleaned text — works in both local (vault) and cloud (articles.json) modes.
    cleaned = load_article_text(article.get("slug", ""), vault_path)
    if cleaned:
        with st.expander("Cleaned Text"):
            st.write(cleaned)
