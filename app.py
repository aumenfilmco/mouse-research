# app.py
"""MOUSE Research Pipeline — Streamlit Dashboard."""
import streamlit as st
import pandas as pd
from collections import Counter
from ui_utils import get_vault_path, load_articles

st.set_page_config(
    page_title="MOUSE Research",
    page_icon="🐭",
    layout="wide",
)

st.title("🐭 MOUSE Research Dashboard")

vault_path = get_vault_path()
articles = load_articles(vault_path)

if not articles:
    st.warning("No articles found in vault. Run a search first.")
    st.stop()

# Stat cards
total = len(articles)
wrestling = sum(1 for a in articles if a.get("is_wrestling", True))
non_wrestling = total - wrestling
analyzed = sum(1 for a in articles if a.get("analyzed", False))

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Articles", total)
col2.metric("Wrestling", wrestling)
col3.metric("Non-Wrestling", non_wrestling)
col4.metric("Analyzed", analyzed)

# Date range
dates = sorted(a.get("date", "") for a in articles if a.get("date"))
if dates:
    st.caption(f"Coverage: **{dates[0]}** to **{dates[-1]}**")

# Top people and schools side by side
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Top 10 People")
    people_counts: Counter = Counter()
    for a in articles:
        for p in a.get("people") or []:
            people_counts[p] += 1
    if people_counts:
        top_people = people_counts.most_common(10)
        df_people = pd.DataFrame(top_people, columns=["Person", "Articles"])
        st.bar_chart(df_people.set_index("Person"))
    else:
        st.info("No people data yet. Run analysis first.")

with col_right:
    st.subheader("Top 10 Schools")
    school_counts: Counter = Counter()
    for a in articles:
        for s in a.get("schools") or []:
            school_counts[s] += 1
    if school_counts:
        top_schools = school_counts.most_common(10)
        df_schools = pd.DataFrame(top_schools, columns=["School", "Articles"])
        st.bar_chart(df_schools.set_index("School"))
    else:
        st.info("No school data yet. Run analysis first.")

# Recent articles
st.subheader("Recent Articles")
recent = articles[:10]
for a in recent:
    date = a.get("date", "undated")
    headline = a.get("headline") or a.get("title") or a.get("slug", "")
    wrestling_icon = "✅" if a.get("is_wrestling", True) else "⚠️"
    st.text(f"{wrestling_icon} {date} — {headline}")
