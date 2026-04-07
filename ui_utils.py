"""Shared utilities for the Streamlit UI.

Provides cached data loading from the Obsidian vault or a pre-exported
data/articles.json file (cloud / demo mode).
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Make src/ importable so `from mouse_research.X import Y` works in both
# local development and Streamlit Cloud (where the package isn't pip-installed).
_SRC_DIR = Path(__file__).parent / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import pandas as pd

# ---------------------------------------------------------------------------
# Optional Streamlit import — not available in test / CLI contexts
# ---------------------------------------------------------------------------
try:
    import streamlit as st
    _STREAMLIT_AVAILABLE = True
except ImportError:
    st = None  # type: ignore[assignment]
    _STREAMLIT_AVAILABLE = False

# Default data directory (relative to this file)
_DATA_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------

def is_cloud_mode(vault_path: str | None) -> bool:
    """Return True when vault_path is None or does not exist on disk."""
    if vault_path is None:
        return True
    return not Path(vault_path).exists()


def get_vault_path() -> str | None:
    """Get vault path from mouse-research config, or None if unavailable."""
    try:
        from mouse_research.config import get_config
        return get_config().vault.path
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Internal loaders
# ---------------------------------------------------------------------------

def _load_articles_from_vault(vault_path: str) -> list[dict]:
    """Scan vault/Articles/*/metadata.json and return sorted article list."""
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


def _load_articles_from_json(data_dir: str | None = None) -> list[dict]:
    """Load articles from data/articles.json (cloud / demo mode)."""
    path = Path(data_dir) / "articles.json" if data_dir else _DATA_DIR / "articles.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _load_articles_impl(vault_path: str | None = None, data_dir: str | None = None) -> list[dict]:
    """Core implementation — dispatches to vault or JSON loader."""
    if vault_path is not None and not is_cloud_mode(vault_path):
        return _load_articles_from_vault(vault_path)
    return _load_articles_from_json(data_dir)


# Apply @st.cache_data only when Streamlit is available
if _STREAMLIT_AVAILABLE:
    @st.cache_data(ttl=30)
    def load_articles(vault_path: str | None = None, data_dir: str | None = None) -> list[dict]:
        """Load all article metadata.

        Reads from vault/Articles/*/metadata.json when vault_path exists,
        otherwise falls back to data/articles.json (cloud mode).
        Cached for 30 seconds when running inside Streamlit.
        """
        return _load_articles_impl(vault_path, data_dir)
else:
    def load_articles(vault_path: str | None = None, data_dir: str | None = None) -> list[dict]:  # type: ignore[misc]
        """Load all article metadata (no-cache version for tests/CLI)."""
        return _load_articles_impl(vault_path, data_dir)


def load_article_text(slug: str, vault_path: str | None = None, data_dir: str | None = None) -> str:
    """Return the cleaned article text for *slug*.

    Local mode: reads the '## Cleaned Text' section from article.md in the
    vault.  Cloud mode: returns the 'cleaned_text' field from articles.json.
    Returns an empty string when the text cannot be found.
    """
    if vault_path is not None and not is_cloud_mode(vault_path):
        article_md = Path(vault_path) / "Articles" / slug / "article.md"
        if article_md.exists():
            content = article_md.read_text(encoding="utf-8")
            # Extract text between '## Cleaned Text' and the next '***' or '##'
            match = re.search(
                r"##\s+Cleaned Text\s*\n(.*?)(?=\n\*\*\*|\n##\s|\Z)",
                content,
                re.DOTALL,
            )
            if match:
                return match.group(1).strip()
        return ""

    # Cloud / JSON mode
    articles = _load_articles_from_json(data_dir)
    for article in articles:
        if article.get("slug") == slug:
            return article.get("cleaned_text", "")
    return ""


def get_people_index(articles: list[dict]) -> dict[str, list[dict]]:
    """Build a mapping of person name -> list of article dicts."""
    index: dict[str, list[dict]] = defaultdict(list)
    for article in articles:
        for person in article.get("people") or []:
            index[person].append(article)
    return dict(index)


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
