# Interview Prep Feature — Design Spec

**Goal:** Add an Interview Prep page to the Streamlit UI that generates targeted documentary interview questions for any person in the research corpus, with web-powered enrichment/fact-checking, light curation, and export to PDF and Obsidian note. The feature should work both locally and from a cloud-hosted deployment.

**Scope:** v1 — Interview Prep page, `mouse-research sync` command, cloud deployment on Streamlit Community Cloud, PDF + vault export.

---

## Architecture

### Hybrid Local/Cloud Model

The MOUSE Research pipeline operates in two modes:

- **Local mode:** Full app — search, archive, analyze, browse, interview prep. Articles read from the Obsidian vault. LLM analysis uses Gemma 4 via Ollama.
- **Cloud mode:** Read-only subset — browse articles, interview prep. Articles read from a bundled `data/articles.json`. Interview question generation uses Gemini Flash 2.0 via Google AI API.

Cloud detection: if `~/.mouse-research/config.yaml` does not exist or the configured vault path does not exist on disk, the app runs in cloud mode. Cloud mode hides Search and Analysis pages from the sidebar.

Interview prep uses Gemini Flash 2.0 in both modes (not Gemma 4) because it needs:
1. Stronger instruction-following for editorial-quality question generation
2. Built-in Google Search grounding for enrichment and fact-checking
3. Availability without a local Ollama server

### Data Flow

```
Local machine:
  vault/Articles/*/metadata.json + article.md
       │
       ▼
  mouse-research sync --push
       │
       ▼
  data/articles.json → GitHub repo → Streamlit Community Cloud
       │
       ▼
  Interview Prep page (cloud or local)
       │
       ▼
  Gemini Flash 2.0 (+ Google Search grounding)
       │
       ▼
  PDF download / Vault note
```

---

## Data Layer

### `mouse-research sync` CLI Command

New command added to `cli.py`:

```
mouse-research sync [--push]
```

- Scans all `vault/Articles/*/metadata.json` files
- For each article, reads the cleaned text section from `article.md`
- Bundles into a single `data/articles.json` — array of objects, each containing all metadata fields plus a `cleaned_text` field and `slug` as identifier
- Estimated size for 992 articles: ~2-5 MB
- `--push` flag: commits `data/articles.json` and pushes to GitHub

### `ui_utils.py` Changes

`load_articles(vault_path)` gains a fallback path:
- If vault path exists → scan `vault/Articles/*/metadata.json` (current behavior)
- If vault path does not exist → load from `data/articles.json`

New helper:
- `load_article_text(slug, vault_path)` — returns cleaned text for a specific article. Locally reads from `article.md` in vault. Cloud reads from the `cleaned_text` field in `articles.json`.
- `get_people_index(articles)` — returns a dict of `{person_name: [article_dicts]}` built from the `people` field across all articles. Cached.

---

## Interview Prep Page (`pages/4_Interview_Prep.py`)

### System Prompt

Hardcoded constant used for all interview question generation:

```
You are a documentary research assistant for "MOUSE: 50 Years on the Mat,"
a film about the Bermudian Springs wrestling program and its legendary coach
Dave McCollum. The documentary spans roughly 1975-2025 and explores how one
small-town Pennsylvania program shaped generations of wrestlers. When
generating interview questions, prioritize: the wrestling room culture,
relationships with McCollum, moments of transformation, and details that
reveal the program's character. Questions should be designed to elicit vivid,
emotional sound bites suitable for a documentary teaser and feature film.
```

### Page Layout

#### 1. Person Selection

Searchable text input at the top. As the user types, a filtered list appears showing matching people with article count:
- "Kyle Flickinger (11 articles)"
- "Kevin Flickinger (2 articles)"

Implementation: `st.selectbox` with a text filter applied to the people index. The list is sorted by article count (descending) so the most-referenced people appear first when browsing.

On selection, the page loads all articles for that person.

#### 2. Article Timeline

Compact table showing the person's articles in chronological order (oldest first — shows career arc):

| Date | Headline | Schools | Wrestling |
|------|----------|---------|-----------|

Each row has a checkbox (default: checked) to include/exclude from question generation. Expandable detail on click showing summary and cleaned text preview.

#### 3. Theme Selection

Checkboxes for angles to explore. Themes are conditionally shown based on article content:

- **"High school career"** — shown if articles exist from HS years
- **"Relationship with McCollum"** — shown if McCollum appears in any of their articles
- **"College/post-HS career"** — shown if articles exist from later years or mention college
- **"Team moments & championships"** — shown if team event articles found
- **"Teaser sound bite"** — always shown
- **"Family/program legacy"** — shown if other people in the index share the surname

Freeform text box: "Additional context or angles" — for anything the user wants to tell the LLM (e.g., "Kyle is now a coach himself, ask about that").

#### 4. Generation Controls

- **"Enrich with web search"** toggle — off by default. When enabled, Gemini uses Google Search grounding to find external information about the person before generating questions.
- **"Fact-check questions"** toggle — on by default. When enabled, a second LLM pass verifies key claims (names, records, dates, scores) in the generated questions against web sources.
- **"Generate Questions"** button (primary)

#### 5. Generation Pipeline

When the user clicks "Generate Questions":

1. **Gather context:** Collect cleaned text from all checked articles. Build a chronological summary of the person's arc.
2. **Web enrichment (if enabled):** Gemini Flash call with Google Search grounding enabled. Prompt: find additional information about this person + Bermudian Springs wrestling. Results appended to context.
3. **Generate questions:** Gemini Flash call with system prompt + article context + selected themes + user's freeform notes. Response format: numbered questions, each with a context note explaining why the question matters and what article/fact it draws from. Also includes a 2-3 sentence "story arc summary" of the person.
4. **Fact-check (if enabled):** Second Gemini Flash call with Google Search grounding. Prompt: verify the key factual claims in these questions against web sources. Returns a list of any discrepancies with corrections.

#### 6. Results Display

Generated questions shown as an ordered list. Each question has:
- Question text (bold)
- Context note (italic, smaller text) — why this question matters, what it's drawn from
- Fact-check warning icon (orange triangle) if a claim was flagged, with the correction noted

Curation controls:
- Delete button (X) per question
- Up/down arrow buttons per question to reorder
- "Add question" text input + button at the bottom

All state managed via `st.session_state` so curation persists across Streamlit reruns.

#### 7. Export

Two buttons:

- **"Download PDF"** — generates and serves a PDF file for download
- **"Save to Vault"** (local mode only) — writes markdown to `vault/Interview Prep/{Person Name} - {YYYY-MM-DD}.md`

---

## PDF Export

**Library:** `fpdf2` — lightweight, no system dependencies.

**Layout:**

```
┌─────────────────────────────────────┐
│  MOUSE — Interview Prep             │
│  Kyle Flickinger                    │
│  April 6, 2026                      │
├─────────────────────────────────────┤
│  STORY ARC                          │
│  2-3 sentence overview of the       │
│  person's trajectory from the       │
│  articles.                          │
├─────────────────────────────────────┤
│  QUESTIONS                          │
│                                     │
│  1. "What was the wrestling room    │
│     at Bermudian like under         │
│     McCollum?"                      │
│     → Let him paint the picture.    │
│       The practice room is the      │
│       heart of the doc.             │
│                                     │
│  2. ...                             │
├─────────────────────────────────────┤
│  FACT-CHECK NOTES                   │
│  * Q3: OCR shows 26-7 record —     │
│    web sources confirm 26-7.        │
├─────────────────────────────────────┤
│  SOURCE ARTICLES                    │
│  • 2003-11-26 — Bermudian Springs   │
│    Wrestling Program Shows Depth    │
│  • 2005-02-27 — Bermudian Springs   │
│    Wins District II Title           │
│  • ...                              │
└─────────────────────────────────────┘
```

### Obsidian Note Format

```markdown
---
type: interview-prep
person: Kyle Flickinger
date: 2026-04-06
articles: 11
---

# Interview Prep — Kyle Flickinger

## Story Arc
{2-3 sentence summary}

## Questions
1. **{question}**
   *{context note}*

2. ...

## Fact-Check Notes
- Q3: OCR shows 26-7 record — web sources confirm 26-7.

## Source Articles
- [[2003-11-26_newspapers-com_10f11-matches|Bermudian Springs Wrestling Program Shows Depth and Talent]]
- [[2005-02-27_newspapers-com_dave-h|Bermudian Springs Wins District II Wrestling Title]]
- ...
```

---

## Cloud Deployment — Streamlit Community Cloud

### Files

| File | Purpose |
|------|---------|
| `requirements-cloud.txt` | Cloud-only dependencies: `streamlit`, `pandas`, `fpdf2`, `google-generativeai` |
| `.streamlit/config.toml` | Streamlit theme/config (committed) |
| `.streamlit/secrets.toml` | Gemini API key (configured in Streamlit Cloud dashboard, NOT committed) |
| `data/articles.json` | Exported article data (committed, updated by `sync`) |

### Secrets Access

In code: `st.secrets["GEMINI_API_KEY"]` for cloud mode. Locally: falls back to environment variable `GEMINI_API_KEY` or config file.

### Pages Visibility

Cloud mode hides pages that need local infrastructure. Implementation: each local-only page checks `is_local_mode()` at the top and calls `st.error("This feature requires local mode.")` + `st.stop()` if running in cloud.

### Deployment Steps (One-Time)

1. Push repo to GitHub (private)
2. Go to share.streamlit.io, connect repo
3. Set `GEMINI_API_KEY` in Streamlit Cloud secrets
4. App deploys automatically

### Ongoing Sync

After running analysis locally:
```bash
mouse-research sync --push
```
Streamlit Cloud auto-redeploys on push. New articles live in ~60 seconds.

---

## Dependencies

| Package | Purpose | Local | Cloud |
|---------|---------|-------|-------|
| `streamlit` | Web UI | Yes | Yes |
| `pandas` | DataFrames | Yes | Yes |
| `fpdf2` | PDF generation | Yes | Yes |
| `google-generativeai` | Gemini Flash API | Yes | Yes |
| `ollama` | Gemma 4 for analysis/OCR | Yes | No |
| `playwright` | Browser automation | Yes | No |

### New Dependencies
- `fpdf2` — PDF generation (~100 KB, no system deps)
- `google-generativeai` — Google AI Python SDK

---

## Constraints

- Interview prep always uses Gemini Flash 2.0, never Gemma 4 (needs Google Search grounding + cloud availability)
- `data/articles.json` must be kept in sync manually via `mouse-research sync`
- Cloud mode is read-only — no search, archive, or analysis
- PDF is text-only (no article screenshots embedded)
- Gemini API key required for interview prep in both local and cloud modes
- Free Gemini tier: 15 RPM, 1M tokens/day — more than sufficient for interview prep usage
