# Streamlit UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Streamlit multi-page web UI so the user can browse articles, run searches, and kick off analysis without remembering CLI commands.

**Architecture:** Streamlit multi-page app with `app.py` (Dashboard) at project root and `pages/` folder for sub-pages. Shared `ui_utils.py` provides cached article loading. Long-running CLI operations run as subprocesses. All data read from Obsidian vault `metadata.json` files.

**Tech Stack:** Streamlit, pandas (comes with Streamlit), existing mouse_research modules

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `ui_utils.py` | Create | Shared data loading: `load_articles()`, `get_vault_path()` |
| `app.py` | Create | Streamlit entry point + Dashboard page |
| `pages/1_Articles.py` | Create | Browse/filter/search articles table with expandable details |
| `pages/2_Search.py` | Create | Form to launch Newspapers.com searches |
| `pages/3_Analysis.py` | Create | Run Gemma 4 analysis on unanalyzed articles |
| `src/mouse_research/cli.py` | Modify | Add `ui` command |
| `tests/test_ui_utils.py` | Create | Tests for data loading utilities |

---

### Task 1: Install Streamlit and create ui_utils.py

**Files:**
- Create: `ui_utils.py`
- Create: `tests/test_ui_utils.py`

- [ ] **Step 1: Install Streamlit**

Run: `.venv/bin/pip install streamlit`

- [ ] **Step 2: Write failing test for `load_articles()`**

```python
# tests/test_ui_utils.py
import json
from pathlib import Path
from ui_utils import load_articles


def test_load_articles_reads_metadata(tmp_path):
    """load_articles scans metadata.json files and returns list of dicts."""
    art_dir = tmp_path / "Articles"
    a1 = art_dir / "1991-12-05_test_article-one"
    a1.mkdir(parents=True)
    (a1 / "metadata.json").write_text(json.dumps({
        "slug": "1991-12-05_test_article-one",
        "date": "1991-12-05",
        "headline": "Eagles Win",
        "title": "eagles",
        "source": "Newspapers.com",
        "people": ["Dave McCollum"],
        "schools": ["Bermudian Springs"],
        "is_wrestling": True,
        "summary": "Eagles win a match.",
        "analyzed": True,
        "person": ["Dave McCollum"],
        "tags": ["newspaper"],
    }))

    a2 = art_dir / "1992-01-10_test_article-two"
    a2.mkdir(parents=True)
    (a2 / "metadata.json").write_text(json.dumps({
        "slug": "1992-01-10_test_article-two",
        "date": "1992-01-10",
        "headline": "Football Recap",
        "title": "football",
        "source": "Newspapers.com",
        "people": [],
        "schools": ["West Chester"],
        "is_wrestling": False,
        "summary": "Football game.",
        "analyzed": True,
        "person": [],
        "tags": ["newspaper"],
    }))

    articles = load_articles(str(tmp_path))
    assert len(articles) == 2
    assert articles[0]["headline"] == "Eagles Win" or articles[1]["headline"] == "Eagles Win"


def test_load_articles_skips_bad_json(tmp_path):
    """Malformed metadata.json files are skipped."""
    art_dir = tmp_path / "Articles"
    a1 = art_dir / "bad-article"
    a1.mkdir(parents=True)
    (a1 / "metadata.json").write_text("not json")

    articles = load_articles(str(tmp_path))
    assert len(articles) == 0


def test_load_articles_empty_dir(tmp_path):
    """Returns empty list when no Articles directory exists."""
    articles = load_articles(str(tmp_path))
    assert articles == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ui_utils.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement ui_utils.py**

```python
# ui_utils.py
"""Shared utilities for the Streamlit UI.

Provides cached data loading from the Obsidian vault.
"""
import json
from pathlib import Path

import streamlit as st
import pandas as pd


def get_vault_path() -> str:
    """Get vault path from mouse-research config."""
    from mouse_research.config import get_config
    return get_config().vault.path


@st.cache_data(ttl=30)
def load_articles(vault_path: str) -> list[dict]:
    """Load all article metadata from vault/Articles/*/metadata.json.

    Returns a list of dicts sorted by date descending.
    Malformed or missing files are silently skipped.
    Cached for 30 seconds to avoid re-scanning on every Streamlit rerun.
    """
    articles_dir = Path(vault_path) / "Articles"
    if not articles_dir.exists():
        return []

    articles: list[dict] = []
    for meta_file in articles_dir.glob("*/metadata.json"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["_dir"] = str(meta_file.parent)
            articles.append(meta)
        except (json.JSONDecodeError, OSError):
            continue

    articles.sort(key=lambda r: r.get("date") or "0000-00-00", reverse=True)
    return articles


def articles_to_dataframe(articles: list[dict]) -> pd.DataFrame:
    """Convert article metadata list to a pandas DataFrame for display."""
    rows = []
    for a in articles:
        rows.append({
            "Date": a.get("date", "undated"),
            "Headline": a.get("headline") or a.get("title") or a.get("slug", ""),
            "Schools": ", ".join(a.get("schools") or []),
            "Wrestling": "✅" if a.get("is_wrestling", True) else "⚠️",
            "People": ", ".join(a.get("people") or []),
            "Summary": a.get("summary", ""),
            "Source": a.get("source", ""),
            "_slug": a.get("slug", ""),
            "_is_wrestling": a.get("is_wrestling", True),
            "_analyzed": a.get("analyzed", False),
        })
    return pd.DataFrame(rows)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_ui_utils.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add ui_utils.py tests/test_ui_utils.py
git commit -m "feat: add ui_utils.py with cached article loading for Streamlit UI"
```

---

### Task 2: Create Dashboard page (app.py)

**Files:**
- Create: `app.py`
- Create: `pages/` directory

- [ ] **Step 1: Create pages directory**

Run: `mkdir -p pages`

- [ ] **Step 2: Create app.py**

```python
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
```

- [ ] **Step 3: Verify it runs**

Run: `.venv/bin/streamlit run app.py --server.headless true` (Ctrl+C after it starts)
Expected: "You can now view your Streamlit app in your browser" message

- [ ] **Step 4: Commit**

```bash
git add app.py pages/
git commit -m "feat: add Streamlit Dashboard page with stats, top people/schools, recent articles"
```

---

### Task 3: Create Browse Articles page

**Files:**
- Create: `pages/1_Articles.py`

- [ ] **Step 1: Create the Articles page**

```python
# pages/1_Articles.py
"""Browse and filter archived articles."""
import streamlit as st
import pandas as pd
from ui_utils import get_vault_path, load_articles, articles_to_dataframe

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

# Display table (hide internal columns)
display_cols = ["Date", "Headline", "Schools", "Wrestling"]
st.dataframe(
    df[display_cols],
    use_container_width=True,
    hide_index=True,
    height=400,
)

# --- Detail view ---
st.subheader("Article Details")
st.caption("Select a row number to view details")

row_idx = st.number_input("Row #", min_value=0, max_value=len(df) - 1, value=0, step=1)

if row_idx < len(df):
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

    # Load cleaned text from article directory
    article_dir = article.get("_dir", "")
    if article_dir:
        from pathlib import Path
        ocr_path = Path(article_dir) / "ocr_raw.md"
        if ocr_path.exists():
            with st.expander("Cleaned Text / OCR"):
                article_md = Path(article_dir) / "article.md"
                if article_md.exists():
                    content = article_md.read_text(encoding="utf-8")
                    # Extract cleaned text section
                    marker = "## Cleaned Text"
                    idx = content.find(marker)
                    if idx != -1:
                        end_marker = "## Original OCR"
                        end_idx = content.find(end_marker, idx)
                        cleaned = content[idx + len(marker):end_idx].strip() if end_idx != -1 else content[idx + len(marker):].strip()
                        st.write(cleaned[:2000])
                    else:
                        st.write("No cleaned text available.")
```

- [ ] **Step 2: Verify it loads**

Run: `.venv/bin/streamlit run app.py --server.headless true` (check Articles page loads in browser)

- [ ] **Step 3: Commit**

```bash
git add pages/1_Articles.py
git commit -m "feat: add Browse Articles page with filters and expandable details"
```

---

### Task 4: Create Search page

**Files:**
- Create: `pages/2_Search.py`

- [ ] **Step 1: Create the Search page**

```python
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
```

- [ ] **Step 2: Verify it loads**

Run: open browser to Streamlit app, check "New Search" page renders without errors.

- [ ] **Step 3: Commit**

```bash
git add pages/2_Search.py
git commit -m "feat: add Search page with form to launch Newspapers.com searches"
```

---

### Task 5: Create Analysis page

**Files:**
- Create: `pages/3_Analysis.py`

- [ ] **Step 1: Create the Analysis page**

```python
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
            # Extract last few lines for summary
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
```

- [ ] **Step 2: Verify it loads**

Run: open browser to Streamlit app, check "Run Analysis" page shows correct counts.

- [ ] **Step 3: Commit**

```bash
git add pages/3_Analysis.py
git commit -m "feat: add Analysis page with batch analysis controls and graph rebuild"
```

---

### Task 6: Add `ui` CLI command and final verification

**Files:**
- Modify: `src/mouse_research/cli.py`

- [ ] **Step 1: Add `ui` command to cli.py**

Add after the `analyze` command in `src/mouse_research/cli.py`:

```python
@app.command()
def ui():
    """Launch the Streamlit web interface."""
    import subprocess
    import sys
    from pathlib import Path

    app_path = Path(__file__).parent.parent.parent / "app.py"
    if not app_path.exists():
        console.print(f"[red]app.py not found at {app_path}[/red]")
        raise typer.Exit(code=1)

    console.print(f"Starting MOUSE Research UI at [bold]http://localhost:8501[/bold]")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])
```

- [ ] **Step 2: Verify CLI command works**

Run: `.venv/bin/mouse-research ui --help`
Expected: Shows "Launch the Streamlit web interface."

- [ ] **Step 3: Full smoke test**

Run: `.venv/bin/mouse-research ui`
Verify in browser:
1. Dashboard shows correct stats (992 articles, 928 wrestling, etc.)
2. Articles page filters work (search, wrestling filter, school filter, year slider)
3. Articles page shows details when row selected
4. Search page form renders
5. Analysis page shows correct analyzed/remaining counts

- [ ] **Step 4: Commit**

```bash
git add src/mouse_research/cli.py
git commit -m "feat: add ui CLI command to launch Streamlit interface"
```
