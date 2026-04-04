# MOUSE Research Streamlit UI — Design Spec

**Goal:** Add a web-based GUI so the user can browse articles, run searches, and kick off analysis without remembering CLI commands.

**Scope:** v1 — Dashboard, Browse Articles, New Search, Run Analysis. No graph visualization or synthesis (v2).

---

## Architecture

Single Streamlit multi-page app. Main entry point `app.py` at project root, individual pages in `pages/` folder. Streamlit auto-generates a sidebar with page links from the `pages/` directory structure.

All pages read article data directly from the Obsidian vault's `metadata.json` files — no separate database. The vault path comes from `~/.mouse-research/config.yaml` (same config the CLI uses).

Long-running operations (search, analysis) are launched as subprocesses via `subprocess.Popen` so the Streamlit UI stays responsive. Progress is displayed by polling log files or process status.

### Data Access

A shared utility module (`ui_utils.py`) provides:
- `load_articles()` — scans `vault/Articles/*/metadata.json`, returns a list of dicts. Decorated with `@st.cache_data(ttl=30)` so it refreshes every 30 seconds without re-scanning on every interaction.
- `get_config()` — reuses existing `mouse_research.config.get_config()` to get vault path and Ollama URL.

### Dependencies

- `streamlit` — only new pip dependency
- All other dependencies (Typer, Rich, Ollama SDK, etc.) already installed

### Launch

Two options:
1. Direct: `streamlit run app.py`
2. CLI command: `mouse-research ui` (runs streamlit as subprocess)

---

## Pages

### 1. Dashboard (`app.py`)

The main page. Shows at-a-glance stats for the research corpus.

**Content:**
- **Stat cards row:** Total articles | Wrestling | Non-wrestling | Analyzed
- **Date coverage:** "1977 — 2025" (earliest and latest article dates)
- **Top 10 People:** Bar chart or table showing people with the most article appearances (from `people` field in metadata)
- **Top 10 Schools:** Same format, from `schools` field
- **Recent articles:** Last 10 articles by capture date

**Data source:** `load_articles()` → aggregate counts and top-N from metadata fields.

### 2. Browse Articles (`pages/1_Articles.py`)

The primary research screen. Filterable, sortable table of all articles with expandable detail rows.

**Filters (top of page):**
- Text search box — filters headline and summary fields
- Wrestling filter — selectbox: All / Wrestling only / Non-wrestling only
- School filter — multiselect dropdown populated from all unique schools in metadata
- Year range — slider from min to max year in corpus

**Table columns:**
- Date (sortable)
- Headline (from `headline` field, falls back to `title`)
- Schools (comma-separated)
- Wrestling flag (✅ or ⚠️)

**Expandable detail (click row):**
- Summary
- People list (comma-separated)
- Schools list
- Cleaned text preview (first 500 chars)
- Link to open in Obsidian (obsidian:// URI) if feasible, otherwise vault file path

**Non-wrestling articles** shown with reduced opacity and ⚠️ icon.

**Implementation:** Use `st.dataframe` with column configuration for the table. Use `st.expander` for detail rows, or render a detail section below the table when a row is selected.

### 3. New Search (`pages/2_Search.py`)

Form to launch a Newspapers.com search without touching the CLI.

**Form fields:**
- Keyword (text input, required) — e.g. `"Dave McCollum" Bermudian wrestling`
- Years (text input, optional) — e.g. `1977-2025`
- Location (selectbox) — Pennsylvania, New York, Maryland, etc. (from `LOCATION_CODES` in searcher.py)
- Person (text input, optional) — name to tag articles with
- Auto-archive (checkbox, default True)

**Submit button:** Launches `mouse-research search` as a subprocess with the form values as CLI args. The command runs with `--auto-archive` if checked.

**Progress/status:**
- While running: show spinner with "Searching Newspapers.com..."
- On completion: show result count from stdout, offer to refresh article list

**Implementation:** `subprocess.Popen` with stdout/stderr capture. Use `st.status` or `st.spinner` for progress.

### 4. Run Analysis (`pages/3_Analysis.py`)

Dashboard for running Gemma 4 analysis on articles.

**Status display:**
- Analyzed count / total count (with progress bar)
- "X articles remaining"

**Controls:**
- Number input: "Analyze next N articles" (default 50)
- "Start Analysis" button
- "Re-analyze" checkbox (maps to `--force`)

**While running:**
- Show spinner with article count progress
- Launched as subprocess: `mouse-research analyze --limit N`

**On completion:** Show summary (X analyzed, Y skipped, Z failed), refresh stats.

---

## File Structure

```
researchpapers/
├── app.py                      # Streamlit entry point + Dashboard page
├── pages/
│   ├── 1_Articles.py           # Browse Articles
│   ├── 2_Search.py             # New Search
│   └── 3_Analysis.py           # Run Analysis
├── ui_utils.py                 # Shared data loading utilities
└── src/mouse_research/
    └── cli.py                  # Add `ui` command
```

## CLI Integration

Add `mouse-research ui` command to `cli.py`:

```python
@app.command()
def ui():
    """Launch the Streamlit web interface."""
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])
```

## Constraints

- No additional database — reads directly from vault metadata.json files
- No authentication — local-only tool
- Streamlit's rerun-on-interaction model means `load_articles()` must be cached to avoid re-scanning 992 files on every click
- Subprocess-launched operations (search, analyze) must not block the Streamlit event loop
