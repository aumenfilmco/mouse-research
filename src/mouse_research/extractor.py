"""Article text extraction, source detection, and date detection.

Handles the text path for modern web articles.
- extract_text: newspaper4k primary, trafilatura fallback
- detect_source: maps URL domain to publication name
- detect_date: extracts publish date from multiple sources
"""
import json
import re
from datetime import date, datetime
from typing import Optional
from urllib.parse import urlparse

from newspaper import Article
from newspaper.article import ArticleDownloadState
import trafilatura

from mouse_research.types import ArticleData


# ---------------------------------------------------------------------------
# Domain → publication name mapping
# Add entries as new sources are encountered.
# None means "parse from page HTML" (currently only newspapers.com).
# ---------------------------------------------------------------------------
_DOMAIN_MAP = {
    "newspapers.com": None,                  # Parse from page HTML JSON
    "lancasteronline.com": "LancasterOnline",
    "ydr.com": "York Daily Record",
    "eveningsun.com": "The Evening Sun",
    "gettysburgtimes.com": "Gettysburg Times",
    "pennlive.com": "PennLive / The Patriot-News",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text(url: str, html: str) -> ArticleData:
    """Extract article text from pre-fetched HTML.

    Primary: newspaper4k. Fallback: trafilatura when text < 50 chars.

    Note: For Newspapers.com viewer pages, newspaper4k title returns the
    newspaper name (from <title> tag) — not the article headline. Title
    should be sourced from OCR output in those cases (archiver.py handles
    this).
    """
    article = None

    # Primary: newspaper4k
    try:
        article = Article(url)
        article.html = html
        article.download_state = ArticleDownloadState.SUCCESS
        article.parse()
        text = article.text or ""
        if len(text.strip()) >= 50:
            return ArticleData(
                title=article.title or "",
                authors=article.authors or [],
                publish_date=article.publish_date.date()
                if hasattr(article.publish_date, "date")
                else article.publish_date,
                text=text,
                extraction_method="newspaper4k",
            )
    except Exception:
        pass

    # Fallback: trafilatura
    try:
        doc = trafilatura.bare_extraction(
            html,
            include_comments=False,
            include_tables=False,
            with_metadata=True,
        )
        if doc and doc.text and len(doc.text.strip()) >= 50:
            return ArticleData(
                title=doc.title or "",
                authors=[doc.author] if doc.author else [],
                publish_date=_parse_date(doc.date),
                text=doc.text,
                extraction_method="trafilatura",
            )
    except Exception:
        pass

    # Neither produced usable text — return empty with whatever newspaper4k found
    return ArticleData(
        title=(article.title or "") if article is not None else "",
        extraction_method="none",
    )


def detect_source(url: str, html: str) -> str:
    """Detect publication name from URL domain.

    For newspapers.com: parses the embedded JSON blob in the page HTML for
    the publication name (looks for 'publicationName' or 'title' in
    window.__PRELOADED_STATE__ or <script type="application/json"> tags).
    Falls back to "Newspapers.com" if parsing fails.
    """
    domain = urlparse(url).netloc.lstrip("www.")

    for known_domain, name in _DOMAIN_MAP.items():
        if known_domain in domain:
            if name is not None:
                return name
            # newspapers.com: extract from page HTML JSON
            return _extract_newspapers_com_source(html)

    # Unknown domain: titlecase the domain minus TLD
    return domain.split(".")[0].replace("-", " ").title()


def detect_date(url: str, article_data: ArticleData, html: str) -> Optional[date]:
    """Detect article publication date.

    Priority:
    1. article_data.publish_date (from newspaper4k or trafilatura)
    2. URL date patterns: /YYYY/MM/DD/, /YYYY-MM-DD, ?date=YYYY-MM-DD
    3. HTML meta tags (og:article:published_time, datePublished)
    4. Returns None — archiver.py can attempt date extraction from OCR text
    """
    # 1. From extraction
    if article_data.publish_date:
        return article_data.publish_date

    # 2. URL date patterns
    url_patterns = [
        r"/(\d{4})/(\d{2})/(\d{2})/",        # /YYYY/MM/DD/
        r"/(\d{4})-(\d{2})-(\d{2})[/_]",      # /YYYY-MM-DD
        r"[?&]date=(\d{4})-(\d{2})-(\d{2})",  # ?date=YYYY-MM-DD
    ]
    for pattern in url_patterns:
        m = re.search(pattern, url)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue

    # 3. HTML meta tags
    meta_patterns = [
        r'(?:datePublished|article:published_time)["\s:]+(\d{4}-\d{2}-\d{2})',
        r'<meta[^>]+(?:published_time|datePublished)[^>]+content="(\d{4}-\d{2}-\d{2})',
    ]
    for pattern in meta_patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            try:
                parts = m.group(1).split("-")
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                continue

    return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: str | None) -> Optional[date]:
    """Parse a date string into a date object, trying multiple formats."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%B %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _extract_newspapers_com_source(html: str) -> str:
    """Extract publication name from Newspapers.com viewer page HTML.

    The page embeds a JSON blob containing publication metadata.
    Try multiple known patterns before falling back.
    """
    patterns = [
        r'"publicationName"\s*:\s*"([^"]+)"',
        r'"publication"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"',
        r'"title"\s*:\s*"([^"]+Gettysburg|[^"]+Evening Sun|[^"]+York Daily[^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return "Newspapers.com"
