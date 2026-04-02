"""Obsidian vault writer for mouse-research pipeline.

Responsible for:
- Creating article folders with slug naming: YYYY-MM-DD_source-slug_title-slug
- Writing article.md notes with YAML frontmatter in Obsidian format
- Writing metadata.json for duplicate detection
- Detecting duplicate URLs against existing vault articles

Note format is LOCKED by user decisions — do not change frontmatter fields,
section names, or wikilink placement without updating 02-CONTEXT.md.
"""
import json
import re
from datetime import date as date_cls
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import frontmatter

from mouse_research.types import ArticleRecord


def make_slug(pub_date: Optional[date_cls], source_name: str, title: str) -> str:
    """Generate folder slug: YYYY-MM-DD_source-slug_title-slug."""
    date_str = pub_date.strftime("%Y-%m-%d") if pub_date else "undated"
    source_slug = re.sub(r"[^a-z0-9]+", "-", source_name.lower()).strip("-")[:30]
    title_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    return f"{date_str}_{source_slug}_{title_slug}"


def create_article_folder(vault_path: str, slug: str) -> Path:
    """Create and return the article folder path under vault/Articles/.

    Creates: <vault_path>/Articles/<slug>/
    Uses exist_ok=True — safe to call if folder already exists.
    """
    folder = Path(vault_path) / "Articles" / slug
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def write_article_note(folder: Path, record: ArticleRecord) -> Path:
    """Write article.md to the article folder.

    Note format (locked by user decisions in 02-CONTEXT.md):
    - YAML frontmatter: person (list), source, date, url, tags (list),
                        captured (date), extraction (method)
    - Title as H1 heading
    - Screenshot embedded: ![[screenshot.png]]
    - ## Article Text section with OCR text (for Newspapers.com) or web extract
    - ## Web Extract section only when BOTH OCR and web text are present
    - ## Notes section (empty) at bottom for Chris's research notes
    - Wikilinks for person and source in note body (not in frontmatter)
    """
    # Determine primary text source
    # For Newspapers.com (OCR result present): OCR is primary
    # For modern web articles: web extraction text is primary
    has_ocr = bool(record.ocr_result.text and not record.ocr_result.queued)
    has_web = bool(record.article_data.text and len(record.article_data.text.strip()) >= 50)

    if has_ocr:
        primary_text = record.ocr_result.text
        primary_section = "## Article Text"
    elif has_web:
        primary_text = record.article_data.text
        primary_section = "## Article Text"
    else:
        primary_text = "_No text extracted._"
        primary_section = "## Article Text"

    # Build wikilinks for person(s) and source — in body, not frontmatter
    person_links = " | ".join(f"[[{p}]]" for p in record.person) if record.person else ""
    source_link = f"[[{record.source_name}]]"

    body_parts = [
        f"# {record.article_data.title or 'Untitled'}",
        "",
        f"**People:** {person_links}" if person_links else "",
        f"**Source:** {source_link}",
        "",
        "![[screenshot.png]]",
        "",
        primary_section,
        "",
        primary_text,
    ]

    # Web Extract secondary section — only when both OCR and web text present
    if has_ocr and has_web:
        body_parts += ["", "## Web Extract", "", record.article_data.text]

    body_parts += ["", "## Notes", ""]

    # Filter None values but preserve internal blank lines
    body = "\n".join(part for part in body_parts if part is not None)

    # Build frontmatter metadata — exact fields from locked user decisions
    post = frontmatter.Post(
        body,
        person=record.person,                    # list: ["Dave McCollum"]
        source=record.source_name,               # string
        date=record.article_data.publish_date,   # date or None
        url=record.url,
        tags=record.tags,                        # list
        captured=record.captured,                # date
        extraction=record.ocr_result.engine if has_ocr else record.article_data.extraction_method,
    )

    # Use frontmatter.dumps() (returns string) NOT frontmatter.dump() (requires binary handle)
    note_path = folder / "article.md"
    note_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return note_path


def write_metadata_json(folder: Path, record: ArticleRecord) -> Path:
    """Write metadata.json for duplicate detection and record-keeping.

    Schema matches what is_duplicate() reads.
    """
    meta = {
        "url": record.url,
        "slug": record.slug,
        "source": record.source_name,
        "date": record.article_data.publish_date.isoformat() if record.article_data.publish_date else None,
        "captured": record.captured.isoformat(),
        "title": record.article_data.title,
        "person": record.person,
        "tags": record.tags,
        "extraction": record.ocr_result.engine if record.ocr_result.text else record.article_data.extraction_method,
        "ocr_queued": record.ocr_result.queued,
    }
    meta_path = folder / "metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta_path


def is_duplicate(vault_path: str, url: str) -> bool:
    """Check if a URL already exists in the vault.

    Scans all metadata.json files under vault/Articles/*/metadata.json.
    Uses normalized URL comparison (strips query params; Newspapers.com ID is in path).
    """
    normalized = _normalize_url(url)
    articles_dir = Path(vault_path) / "Articles"
    if not articles_dir.exists():
        return False
    for meta_file in articles_dir.glob("*/metadata.json"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if _normalize_url(meta.get("url", "")) == normalized:
                return True
        except (json.JSONDecodeError, OSError):
            continue
    return False


def _normalize_url(url: str) -> str:
    """Normalize URL for comparison: strip query params, keep path (Newspapers.com ID is in path)."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
