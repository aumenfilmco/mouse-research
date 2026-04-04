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
