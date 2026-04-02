"""Searcher module — Node.js scraper integration, dedup filtering, and selection parsing.

This module is the sole interface between the Python pipeline and the Node.js
scraper-wrapper.js. It handles:
- Invoking the Node.js scraper subprocess
- Parsing JSON-line output into SearchResult dataclasses
- Filtering vault duplicates via is_duplicate()
- Mapping human-readable location names to Newspapers.com region codes
- Parsing user selection strings like "1,3,5-12,all"
"""
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mouse_research.config import AppConfig
from mouse_research.obsidian import is_duplicate

SCRAPER_WRAPPER = Path.home() / ".mouse-research" / "scraper-wrapper.js"

LOCATION_CODES: dict[str, str] = {
    "pennsylvania": "us-pa",
    "new york": "us-ny",
    "maryland": "us-md",
    "new jersey": "us-nj",
    "delaware": "us-de",
    "virginia": "us-va",
    "west virginia": "us-wv",
    "ohio": "us-oh",
}


@dataclass
class SearchResult:
    """A single search result from the Newspapers.com scraper."""
    number: int           # 1-based display index (assigned after dedup filtering)
    title: str            # Newspaper name
    date: str             # ISO date "YYYY-MM-DD"
    location: str         # Publication location
    url: str              # Full Newspapers.com URL
    keyword_matches: int  # Match count


class ScraperError(Exception):
    """Raised when the Node.js scraper subprocess fails."""


def resolve_location(location: str) -> str:
    """Map a human-readable location name to a Newspapers.com region code.

    Examples:
        resolve_location("Pennsylvania") -> "us-pa"
        resolve_location("us-pa")        -> "us-pa"  (passthrough)
        resolve_location("New York")     -> "us-ny"

    Unknown locations are returned unchanged (passthrough).
    """
    normalized = location.strip().lower()
    return LOCATION_CODES.get(normalized, location.strip())


def _parse_scraper_output(stdout: str) -> list[dict]:
    """Parse newline-delimited JSON lines from scraper stdout.

    Malformed lines are silently skipped.
    Returns a list of dicts — one per article.
    """
    results = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results


def call_scraper(
    keyword: str,
    years: str | None = None,
    location: str | None = None,
    max_pages: int | None = None,
) -> list[dict]:
    """Invoke the Node.js scraper-wrapper.js subprocess and return parsed results.

    Args:
        keyword:   Search keyword/phrase.
        years:     Date range string like "1975-1985" or single year "1980".
                   Must match r'\\d{4}(-\\d{4})?'; raises ValueError if invalid.
        location:  Human-readable location name or region code (e.g. "Pennsylvania",
                   "us-pa"). Resolved via resolve_location() before passing to scraper.
        max_pages: Maximum pages to fetch. Passed as --max-pages to the scraper.

    Returns:
        List of dicts parsed from scraper JSON-line stdout.

    Raises:
        ValueError:    If years format is invalid.
        ScraperError:  If the scraper subprocess exits with a non-zero return code.
                       If Cloudflare is detected in stderr, the error message includes
                       a hint to re-run `mouse-research login newspapers.com`.
    """
    node = shutil.which("node") or "node"
    cmd: list[str] = [node, str(SCRAPER_WRAPPER), "--keyword", keyword]

    if years is not None:
        if not re.fullmatch(r"\d{4}(-\d{4})?", years):
            raise ValueError(
                f"Invalid years format: {years!r}. Expected 'YYYY' or 'YYYY-YYYY'."
            )
        cmd += ["--years", years]

    if location is not None:
        resolved = resolve_location(location)
        cmd += ["--location", resolved]

    if max_pages is not None:
        cmd += ["--max-pages", str(max_pages)]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        stderr = result.stderr or ""
        if "Cloudflare" in stderr:
            raise ScraperError(
                "Session may have expired -- run `mouse-research login newspapers.com`\n"
                f"Scraper stderr: {stderr}"
            )
        raise ScraperError(f"Scraper failed (exit {result.returncode}): {stderr}")

    return _parse_scraper_output(result.stdout)


def search_and_filter(
    keyword: str,
    years: str | None,
    location: str | None,
    config: AppConfig,
    max_pages: int | None = None,
) -> tuple[list[SearchResult], int]:
    """Run a search and filter out URLs already present in the Obsidian vault.

    Args:
        keyword:   Search keyword/phrase.
        years:     Date range string (passed through to call_scraper).
        location:  Location name or code (passed through to call_scraper).
        config:    AppConfig instance — vault.path is used for dedup detection.
        max_pages: Optional page limit passed to the scraper.

    Returns:
        A tuple of (results, excluded_count) where:
        - results is a list of SearchResult with 1-based numbering.
        - excluded_count is the number of results filtered out as duplicates.
    """
    raw_results = call_scraper(keyword, years, location, max_pages)

    results: list[SearchResult] = []
    excluded_count = 0

    for raw in raw_results:
        url = raw.get("url", "")
        if is_duplicate(config.vault.path, url):
            excluded_count += 1
            continue
        results.append(
            SearchResult(
                number=len(results) + 1,
                title=raw.get("title", ""),
                date=raw.get("date", ""),
                location=raw.get("location", ""),
                url=url,
                keyword_matches=raw.get("keywordMatches", 0),
            )
        )

    return results, excluded_count


def parse_selection(selection: str, max_count: int) -> list[int]:
    """Parse a user selection string into a sorted list of 0-based indices.

    Supported formats:
        "all"      -> [0, 1, ..., max_count-1]
        "1,3,5"    -> [0, 2, 4]
        "1,3,5-8"  -> [0, 2, 4, 5, 6, 7]

    Args:
        selection:  User-supplied selection string.
        max_count:  Total number of available items (upper bound for validation).

    Returns:
        Sorted list of unique 0-based indices.

    Raises:
        ValueError: If any part of the selection string is invalid (non-numeric,
                    out of bounds, or malformed range).
    """
    selection = selection.strip().lower()

    if selection == "all":
        return list(range(max_count))

    indices: list[int] = []

    for part in selection.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            halves = part.split("-", maxsplit=1)
            try:
                start_1based = int(halves[0])
                end_1based = int(halves[1])
            except ValueError:
                raise ValueError(
                    f"Invalid range {part!r}: both ends must be integers."
                )
            start = start_1based - 1
            end = end_1based - 1
            if start < 0 or end >= max_count or start > end:
                raise ValueError(
                    f"Range {part!r} is out of bounds for {max_count} items "
                    f"(valid: 1–{max_count})."
                )
            indices.extend(range(start, end + 1))
        else:
            try:
                one_based = int(part)
            except ValueError:
                raise ValueError(
                    f"Invalid selection {part!r}: expected an integer."
                )
            idx = one_based - 1
            if idx < 0 or idx >= max_count:
                raise ValueError(
                    f"Selection {part!r} is out of bounds for {max_count} items "
                    f"(valid: 1–{max_count})."
                )
            indices.append(idx)

    return sorted(set(indices))
