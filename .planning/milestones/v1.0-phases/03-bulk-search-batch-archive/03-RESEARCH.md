# Phase 3: Bulk Search + Batch Archive - Research

**Researched:** 2026-04-02
**Domain:** Typer CLI extension, Node.js subprocess integration, Rich progress/tables, JSONL retry logic
**Confidence:** HIGH

## Summary

Phase 3 adds `search` and `retry-failures` commands to the existing Typer app. The core
pipeline (archiver, logger, obsidian dedup) is already built and stable. The primary new
surface is calling the newspapers-com-scraper Node.js library via subprocess and orchestrating
the results into the existing archive pipeline with Rich progress display.

The scraper is a **Node.js library** (EventEmitter API), not a CLI tool. A thin wrapper
script `~/.mouse-research/scraper-wrapper.js` **already exists** in the project and is the
correct integration point. It emits one JSON line per article to stdout and progress/error
events to stderr. Python reads stdout line-by-line, parses JSON, and accumulates results.

The location filter in the scraper uses Newspapers.com API codes: 2-char country (`us`) or
`us-XX` IETF-style region codes (e.g., `us-pa` for Pennsylvania). Plain state names like
"Pennsylvania" are not accepted. The `--location` CLI flag must translate human-readable
state names to these codes, or accept codes directly.

**Primary recommendation:** Write a new `searcher.py` module to own subprocess call + result
parsing, then add `search` and `retry-failures` commands to `cli.py` following the existing
lazy-import + Rich Console pattern.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Search Result Display:** Rich Table with columns: #, Newspaper, Date, Location, URL snippet, Match count — consistent with existing Rich Console pattern in cli.py
- **Pagination:** Show all results without pagination — scraper returns manageable counts, keeps interactive selection simple
- **Vault dedup display:** Exclude vault duplicates from results entirely with a count footer: "N results excluded (already in vault)"
- **Zero results:** print "No results found for {query}" with suggestion to broaden search (remove --years/--location)
- **Scraper invocation:** Call via `subprocess.run(['node', scraper_path, ...])` with JSON stdout capture — matches installer.py pattern
- **Scraper failure:** print stderr, log to failures.jsonl, exit with error — consistent with Phase 2 error pattern
- **Rate-limit/block detection:** warn user "Session may have expired — run `mouse-research login newspapers.com`" — aligns with Phase 1 cookie management
- **Scraper args:** Pass search params as CLI args: `node scraper.js --keyword "..." --years "1975-1985" --location "us-pa"` — parse scraper's actual CLI interface
- **Interactive selection prompt:** Rich Prompt with `Enter selection (e.g. 1,3,5-12,all):`
- **Progress bar:** Rich Progress bar with live task count: `Archiving: [####....] 3/12 — current-article-title`
- **Ctrl+C handling:** Print summary of archived-so-far and remaining URLs, don't corrupt failures.jsonl
- **retry-failures:** Read failures.jsonl, show count, reprocess all with same progress display, clear successful entries from log

### Claude's Discretion

- Area 1 (Search Result Display) confirmed by user as Claude's judgment call — recommendations held based on codebase patterns and success criteria alignment
- Exact scraper CLI argument parsing (depends on newspapers-com-scraper's actual interface — will discover during research)
- Internal module structure for search functionality (new searcher.py module vs extending cli.py)
- Selection input parsing implementation details (regex for "1,3,5-12,all" syntax)

### Deferred Ideas (OUT OF SCOPE)

- People notes auto-linking on archive (Phase 4: Research Graph)
- Source notes auto-linking on archive (Phase 4)
- Master article index generation (Phase 4)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BULK-01 | `mouse-research search "<query>"` calls newspapers-com-scraper as Node.js subprocess and returns structured search results | scraper-wrapper.js exists; subprocess.run with stdout capture; JSON line protocol confirmed |
| BULK-02 | Search results deduplicated against existing articles in Obsidian vault (match on URL) | `is_duplicate(config.vault.path, url)` from obsidian.py already handles this; filter before display |
| BULK-03 | Search results filterable by year range (`--years`), location (`--location`), and target newspapers | `--years` maps to `dateRange` param; `--location` must map to Newspapers.com region codes (`us-pa` for Pennsylvania) |
| BULK-04 | Interactive review mode displays numbered results; user selects which to archive (e.g., `1,3,5-12,all`) | Rich Prompt + custom range parser; confirmed syntax from success criteria |
| BULK-05 | `--auto-archive` flag feeds all search results directly into the archiving pipeline | Skip interactive prompt; call `_batch_archive()` directly on full result list |
| BULK-06 | Batch archiving with 5-second rate limiting between fetches, progress bar, and failure continuation | `config.rate_limit_seconds` from config.py; Rich Progress with transient=False for summary visibility |
| BULK-07 | Batch summary at completion showing archived/failed counts | Mirrors `_archive_file()` summary pattern already in cli.py |
| BULK-08 | `mouse-research retry-failures` reprocesses URLs from failures.jsonl | `FAILURE_LOG` path from logger.py; read JSONL, re-run archive pipeline, remove successes from log |
</phase_requirements>

## Standard Stack

### Core (all already installed — no new dependencies required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | 0.24.1 | Add `search` and `retry-failures` commands | Already project CLI framework |
| rich | 14.3.3 | Table display, Progress bar, Prompt | Already project output library |
| subprocess (stdlib) | — | Call `node scraper-wrapper.js` | Matches installer.py pattern; already used |
| json (stdlib) | — | Parse scraper JSON lines | No extra dependency needed |
| re (stdlib) | — | Parse selection ranges like `1,3,5-12,all` | No extra dependency needed |

**No new Python dependencies needed for this phase.** All required libraries are already in
`pyproject.toml` and installed in `.venv/`.

### Node.js Scraper (already installed)

| Component | Location | Version | Interface |
|-----------|----------|---------|-----------|
| newspapers-com-scraper | `~/.mouse-research/node_modules/` | 1.1.0 | Node.js library (EventEmitter) |
| scraper-wrapper.js | `~/.mouse-research/scraper-wrapper.js` | existing | CLI: `node scraper-wrapper.js --keyword ... --years ... --location ...` |

**scraper-wrapper.js already handles:**
- `--keyword`, `--years`, `--location`, `--max-pages` argument parsing
- Emits one JSON article line per result to stdout
- Emits progress/complete/error events as JSON to stderr
- Monkey-patches Chrome path to macOS location (`/Applications/Google Chrome.app/...`)
- Sets `logger: { level: 'silent' }` so scraper internals don't pollute stdout

**Installation:**
```bash
# No new installs needed — all dependencies present
# Verify:
node --version  # v24.14.1 confirmed
ls ~/.mouse-research/scraper-wrapper.js  # confirmed present
```

## Architecture Patterns

### Recommended Project Structure Addition

```
src/mouse_research/
├── searcher.py      # NEW: subprocess call, JSON parsing, result dataclass
├── cli.py           # EXTEND: add search() and retry_failures() commands
└── (all existing modules unchanged)
```

### Pattern 1: scraper-wrapper.js invocation from Python

**What:** Run the wrapper with `subprocess.run`, capture stdout (JSON lines), check returncode.

**The wrapper's output protocol:**
- stdout: one JSON line per article: `{"title": "...", "pageNumber": 4, "date": "1982-03-15", "location": "York, PA", "keywordMatches": 3, "url": "https://www.newspapers.com/image/12345678/"}`
- stderr: progress/complete/error JSON (can be ignored or logged at DEBUG level)
- exitcode 0 = success, 1 = error (with error JSON on stderr)

**Example:**
```python
# Source: scraper-wrapper.js interface (verified by reading source)
import subprocess
import json
import shutil
from pathlib import Path

MOUSE_DIR = Path.home() / ".mouse-research"
SCRAPER_WRAPPER = MOUSE_DIR / "scraper-wrapper.js"

def call_scraper(keyword: str, years: str | None, location: str | None) -> list[dict]:
    """Call scraper-wrapper.js and return list of article dicts."""
    node_path = shutil.which("node")
    cmd = [node_path, str(SCRAPER_WRAPPER), "--keyword", keyword]
    if years:
        cmd += ["--years", years]
    if location:
        cmd += ["--location", location]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        # Parse error from stderr if possible
        raise ScraperError(result.stderr)

    articles = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                articles.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # Skip malformed lines
    return articles
```

### Pattern 2: Location code mapping

**What:** The scraper's `buildSearchParams()` accepts only 2-char country codes (`us`) or
`us-XX` IETF region codes. "Pennsylvania" as a plain string is silently ignored (falls through
both `if` branches in the scraper source).

**Resolution:** The `--location` flag in the CLI should accept either the region code directly
OR a common state name that gets mapped to its code. Pennsylvania = `us-pa`.

```python
# Verified by reading NewspaperScraper.js buildSearchParams() lines 188-193
LOCATION_CODES = {
    "pennsylvania": "us-pa",
    "new york": "us-ny",
    "maryland": "us-md",
    # extend as needed — these cover MOUSE research geography
}

def resolve_location(location: str) -> str:
    """Resolve human-readable state name or pass-through region code."""
    normalized = location.lower().strip()
    return LOCATION_CODES.get(normalized, normalized)
```

### Pattern 3: Selection range parsing

**What:** Parse `1,3,5-12,all` into a list of 0-based indices into the results list.

```python
# Source: custom — no library needed
def parse_selection(selection: str, max_count: int) -> list[int]:
    """Parse selection string into list of 0-based indices.
    
    Accepts: '1,3,5-12,all' (1-based user input)
    Returns: list of 0-based indices
    Raises: ValueError on invalid input
    """
    selection = selection.strip().lower()
    if selection == "all":
        return list(range(max_count))

    indices = []
    for part in selection.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start_i = int(start) - 1  # Convert to 0-based
            end_i = int(end) - 1
            if start_i < 0 or end_i >= max_count or start_i > end_i:
                raise ValueError(f"Range {part} out of bounds (1-{max_count})")
            indices.extend(range(start_i, end_i + 1))
        else:
            idx = int(part) - 1  # Convert to 0-based
            if idx < 0 or idx >= max_count:
                raise ValueError(f"Index {part} out of bounds (1-{max_count})")
            indices.append(idx)
    return sorted(set(indices))
```

### Pattern 4: Rich Progress for batch archive

**What:** Wrap the batch archive loop in a Rich Progress context. Mirrors `_archive_file()`
but uses the visual progress bar required by BULK-06.

```python
# Source: Rich docs (confirmed library version 14.3.3 installed)
from rich.progress import Progress, SpinnerColumn, BarColumn, TaskProgressColumn, TextColumn

def _batch_archive_with_progress(urls_and_titles, config, persons, tags, console):
    """Archive a list of (url, title) pairs with Rich progress display."""
    import time
    from mouse_research.archiver import archive_url

    archived = failed = 0
    with Progress(
        SpinnerColumn(),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[dim]{task.description}"),
        console=console,
        transient=False,  # Keep bar visible after completion for summary
    ) as progress:
        task = progress.add_task("Archiving", total=len(urls_and_titles))

        for i, (url, title) in enumerate(urls_and_titles):
            if i > 0:
                time.sleep(config.rate_limit_seconds)

            short_title = title[:50] + "..." if len(title) > 50 else title
            progress.update(task, description=short_title)

            result = archive_url(url, config, person=persons, tags=tags)

            if result.error:
                failed += 1
            else:
                archived += 1

            progress.advance(task)

    return archived, failed
```

### Pattern 5: Graceful Ctrl+C handling

**What:** Wrap the batch loop in a `try/except KeyboardInterrupt`. Print a partial summary
and exit cleanly without corrupting failures.jsonl.

```python
try:
    archived, failed = _batch_archive_with_progress(selected, config, persons, tags, console)
except KeyboardInterrupt:
    console.print("\n[yellow]Interrupted.[/yellow] Partial results:")
    console.print(f"  Archived: {archived}  Failed: {failed}  Remaining: {len(selected) - archived - failed}")
    raise typer.Exit(code=130)  # Standard SIGINT exit code
```

### Pattern 6: retry-failures command

**What:** Read `failures.jsonl`, filter to unique URLs, re-run archive pipeline, remove
successfully-reprocessed entries from the log.

```python
# Source: logger.py FAILURE_LOG pattern (verified)
from mouse_research.logger import FAILURE_LOG, log_failure

def retry_failures_impl(config, console):
    if not FAILURE_LOG.exists():
        console.print("[yellow]No failures log found.[/yellow]")
        return

    records = []
    for line in FAILURE_LOG.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    if not records:
        console.print("[green]No failures to retry.[/green]")
        return

    console.print(f"Retrying [bold]{len(records)}[/bold] failed URLs...")
    still_failed = []
    archived = 0

    # Re-run archive; keep failed records for rewrite
    for record in records:
        result = archive_url(record["url"], config)
        if result.error:
            still_failed.append(record)
        else:
            archived += 1

    # Rewrite failures.jsonl with only unresolved failures
    FAILURE_LOG.write_text(
        "\n".join(json.dumps(r) for r in still_failed) + ("\n" if still_failed else ""),
        encoding="utf-8"
    )
    console.print(f"[bold]Done:[/bold] {archived} archived, {len(still_failed)} still failed")
```

### Pattern 7: SearchResult dataclass

**What:** Typed wrapper around raw scraper dict, for clean passing between searcher.py and cli.py.

```python
# searcher.py
from dataclasses import dataclass

@dataclass
class SearchResult:
    """One result from newspapers-com-scraper, post-dedup-filter."""
    number: int          # 1-based display index
    title: str           # Newspaper name (e.g. "York Daily Record")
    date: str            # ISO date string "YYYY-MM-DD"
    location: str        # Publication location (e.g. "York, PA")
    url: str             # Full Newspapers.com article URL
    keyword_matches: int # Number of keyword hits on page
```

### Anti-Patterns to Avoid

- **Passing "Pennsylvania" as `--location` directly:** Scraper silently ignores it — no error, no filtering. Always resolve to `us-pa` first.
- **Calling `subprocess.run` without `timeout`:** Scraper can hang on Cloudflare challenges indefinitely. Use `timeout=300` (5 minutes).
- **Using `result.stderr` only to detect failure:** Always check `result.returncode != 0` first; stderr also contains progress JSON on success.
- **Collecting ALL stderr output as an error string:** stderr carries progress events (`{"type":"progress",...}`) even on success runs. Filter stderr for `{"type":"error",...}` or rely on returncode.
- **Appending to failures.jsonl without reading first in retry:** `retry-failures` must rewrite the file (not append) after processing so resolved entries are removed.
- **Rich Progress with `transient=True` in batch mode:** The progress bar would disappear on completion, hiding the summary. Use `transient=False`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Progress display | Custom print loop with manual percentage | `rich.progress.Progress` | Handles terminal width, render rate, transient/persistent modes — already installed |
| Interactive prompt | `input()` with manual validation | `rich.prompt.Prompt.ask()` | Consistent with existing Rich Console usage; handles terminal state correctly |
| JSON lines protocol | Custom binary framing | One JSON object per `\n` (already in scraper-wrapper.js) | Already implemented; stdout line-by-line parse is sufficient |
| Vault dedup | Re-implement URL scan | `is_duplicate(config.vault.path, url)` from obsidian.py | Already handles normalized URL comparison; scanning all metadata.json files |
| Rate limiting | asyncio sleep | `time.sleep(config.rate_limit_seconds)` | Matches existing `_archive_file()` pattern exactly; config-driven |

**Key insight:** The scraper-wrapper.js already exists and works. The primary new code is a
Python module (`searcher.py`) that orchestrates: call wrapper → filter dupes → display table
→ get selection → batch archive with progress.

## Common Pitfalls

### Pitfall 1: Location string not translating to API filter
**What goes wrong:** User passes `--location Pennsylvania` and gets results from all US states — location filtering silently does nothing.
**Why it happens:** `buildSearchParams()` in NewspaperScraper.js checks `location.length === 2` for country codes and `location.startsWith("us-")` for regions. "Pennsylvania" fails both checks, so no location filter is added to the API query.
**How to avoid:** Map state names to Newspapers.com region codes before passing to the wrapper. "Pennsylvania" → `us-pa`. Include this mapping in `searcher.py`.
**Warning signs:** Results include newspapers from states other than the target.

### Pitfall 2: Year range splitting on single-year value
**What goes wrong:** `--years 1982` splits on `-` to `["1982"]` — which is a valid single-element array in the scraper. BUT `--years 1975-1985` splits to `["1975", "1985"]` which is also valid. The scraper interprets `[year]` as a single year filter and `[startYear, endYear]` as a range.
**Why it happens:** The wrapper uses `years.split('-')` which works correctly for both cases.
**How to avoid:** Pass years as a single string: `"1975-1985"` for range, `"1982"` for single year. Validate format in Python before passing: must match `^\d{4}(-\d{4})?$`.
**Warning signs:** Getting results outside expected date range.

### Pitfall 3: Scraper launches visible Chrome browser
**What goes wrong:** `NewspaperScraper` defaults to `headless: false`. The wrapper's monkey-patched `setupBrowser()` passes `headless: 'new'`, but Puppeteer v21 accepts either `true`, `false`, or `'new'`. Without the wrapper, a Chrome window appears.
**Why it happens:** The default config has `headless: false` for development convenience.
**How to avoid:** Always invoke via `scraper-wrapper.js` (not directly via `require`). The wrapper already handles this correctly.
**Warning signs:** Unexpected Chrome windows during search.

### Pitfall 4: Cloudflare block detected mid-scrape
**What goes wrong:** The scraper's Puppeteer page encounters a Cloudflare challenge. The scraper throws `CloudflareError` and exits with code 1. Stderr contains `{"type":"error","message":"Cloudflare challenge detected"}`.
**Why it happens:** Newspapers.com uses Cloudflare protection. The scraper uses puppeteer-extra-plugin-stealth to mitigate, but blocks still occur.
**How to avoid:** Detect in Python by checking stderr for `"Cloudflare"` in the error message, then show the specific guidance: "Session may have expired — run `mouse-research login newspapers.com`" (per locked decision in CONTEXT.md).
**Warning signs:** Scraper returns exit code 1 and stderr contains "Cloudflare".

### Pitfall 5: JSONL corruption in retry-failures
**What goes wrong:** If `retry-failures` crashes mid-run before rewriting failures.jsonl, users lose track of which failures were already retried.
**Why it happens:** Append pattern vs rewrite pattern — if we cleared entries one-by-one we'd risk partial writes.
**How to avoid:** Load all records first, process all, then write the `still_failed` list in a single `write_text()` call at the end. Atomicity at Python file write level is sufficient for this use case.
**Warning signs:** Duplicate entries in failures.jsonl after interrupted retry.

### Pitfall 6: subprocess timeout on large searches
**What goes wrong:** Large searches (hundreds of results, many pages) can take 5+ minutes. Default `subprocess.run` has no timeout — the Python process hangs indefinitely.
**Why it happens:** Each scraper page requires a Puppeteer browser tab to load the Newspapers.com search API, which can be slow.
**How to avoid:** Use `timeout=300` (5 minutes) as a reasonable upper bound for typical MOUSE searches. For larger searches, consider `--max-pages` to cap results.
**Warning signs:** CLI appears frozen with no output for > 5 minutes.

## Code Examples

### Search command skeleton (cli.py addition)
```python
# Source: existing cli.py pattern (verified by reading source)
@app.command()
def search(
    query: str = typer.Argument(..., help="Search term (e.g. 'Dave McCollum wrestling')"),
    years: Optional[str] = typer.Option(None, "--years", help="Year or range: 1982 or 1975-1985"),
    location: Optional[str] = typer.Option(None, "--location", help="State name or region code (e.g. 'Pennsylvania' or 'us-pa')"),
    auto_archive: bool = typer.Option(False, "--auto-archive", help="Archive all results without interactive review"),
    person: Optional[list[str]] = typer.Option(None, "--person", "-p", help="Person name(s) to associate"),
    tag: Optional[list[str]] = typer.Option(None, "--tag", "-t", help="Tag(s) to apply"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    """Search Newspapers.com and archive selected results.

    Examples:
      mouse-research search "Dave McCollum wrestling"
      mouse-research search "McCollum" --years 1975-1985 --location Pennsylvania
      mouse-research search "McCollum" --auto-archive --person "Dave McCollum"
    """
    from mouse_research.config import get_config
    from mouse_research.logger import setup_logging
    from mouse_research.searcher import run_search

    setup_logging(verbose=verbose)
    config = get_config()
    persons = list(person) if person else []
    tags = list(tag) if tag else ["newspaper", "archive"]

    run_search(query, years, location, auto_archive, config, persons, tags, console)
```

### retry-failures command skeleton (cli.py addition)
```python
# Source: logger.py FAILURE_LOG pattern (verified)
@app.command()
def retry_failures(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    """Reprocess failed URLs from failures.jsonl."""
    from mouse_research.config import get_config
    from mouse_research.logger import setup_logging
    from mouse_research.searcher import retry_failures_impl

    setup_logging(verbose=verbose)
    config = get_config()
    retry_failures_impl(config, console)
```

### Rich Table display for search results
```python
# Source: Rich docs (library 14.3.3 confirmed installed)
from rich.table import Table

def display_results(results: list[SearchResult], excluded_count: int, console) -> None:
    table = Table(title=f"Search Results ({len(results)} found)")
    table.add_column("#", style="bold", width=4)
    table.add_column("Newspaper", min_width=20)
    table.add_column("Date", width=12)
    table.add_column("Location", min_width=15)
    table.add_column("URL", overflow="fold", max_width=40)
    table.add_column("Matches", width=8, justify="right")

    for r in results:
        url_snippet = r.url.split("/image/")[-1].rstrip("/") if "/image/" in r.url else r.url[:40]
        table.add_row(
            str(r.number),
            r.title,
            r.date,
            r.location,
            f".../{url_snippet}",
            str(r.keyword_matches),
        )

    console.print(table)
    if excluded_count > 0:
        console.print(f"[dim]{excluded_count} result(s) excluded (already in vault)[/dim]")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `launch_persistent_context()` for cookies | `storage_state()` save/load | Phase 1 decision | Not relevant for search (scraper uses its own Puppeteer instance) |
| `subprocess.run(['node', 'scraper.js', '--query', ...])` (assumed CLI) | `node scraper-wrapper.js --keyword ...` (wrapper script) | Discovered Phase 3 research | Wrapper script already exists; `--keyword` not `--query` |

**Key discovery:** The CONTEXT.md says "parse scraper's actual CLI interface." Research confirms
the scraper has **no CLI** — it is a library. The wrapper script at `~/.mouse-research/scraper-wrapper.js`
IS the CLI interface, and it uses `--keyword` (not `--query`). The Python code must call
`scraper-wrapper.js --keyword` not any other argument name.

## Open Questions

1. **Cookie injection into scraper**
   - What we know: `~/.mouse-research/cookies/newspapers.com.json` exists with Playwright `storage_state` format (`{"cookies": [...], "origins": [...]}`)
   - What's unclear: The scraper-wrapper.js does NOT load these cookies. It launches a fresh Puppeteer session. Newspapers.com search may work without auth (only viewing requires login), but this has not been empirically confirmed.
   - Recommendation: Search appears to be unauthenticated based on the scraper README (no auth mentioned). Plan should include a note that if searches return 0 results unexpectedly, cookie injection into the wrapper may be needed.

2. **--location flag value format for user**
   - What we know: Scraper needs `us-pa` for Pennsylvania. CLI success criteria says `--location "Pennsylvania"`.
   - What's unclear: Whether the flag should accept both forms or only one.
   - Recommendation: Accept both. Map known state names to codes in `LOCATION_CODES` dict in searcher.py; pass unknown values through as-is (to support `us-pa` direct entry).

3. **Scraper session/rate limiting**
   - What we know: The scraper uses puppeteer-extra-plugin-stealth and internally handles retries. The Python 5-second rate limit is for archiving (Phase 2), not searching.
   - What's unclear: Whether running a large search followed immediately by batch archiving will trigger rate limits on Newspapers.com.
   - Recommendation: The 5-second delay between archive calls (already in `_archive_file()`) should be sufficient. No additional delay needed between search and first archive call.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | scraper-wrapper.js | ✓ | v24.14.1 | — |
| newspapers-com-scraper | search | ✓ | 1.1.0 | — |
| scraper-wrapper.js | search subprocess | ✓ | existing | — |
| Google Chrome | Puppeteer (in scraper) | ✓ (assumed, Phase 1 validated) | — | — |
| newspapers.com cookies | search auth | ✓ | newspapers.com.json present | Search may work unauthenticated |
| Python .venv | CLI | ✓ | 3.14.3 | — |
| rich 14.3.3 | Progress, Table, Prompt | ✓ | 14.3.3 | — |
| typer 0.24.1 | CLI commands | ✓ | 0.24.1 | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — all dependencies confirmed present.

## Sources

### Primary (HIGH confidence)
- `/Users/aumen-server/.mouse-research/node_modules/newspapers-com-scraper/lib/NewspaperScraper.js` — full scraper source; verified `buildSearchParams()` location handling, `retrieve()` API, article JSON shape, event names
- `/Users/aumen-server/.mouse-research/scraper-wrapper.js` — verified CLI interface (`--keyword`, `--years`, `--location`, `--max-pages`), JSON-lines stdout protocol, stderr protocol
- `/Users/aumen-server/Projects/researchpapers/src/mouse_research/cli.py` — verified lazy import pattern, `_archive_file()` rate limiting + summary pattern, Rich Console usage
- `/Users/aumen-server/Projects/researchpapers/src/mouse_research/logger.py` — verified `FAILURE_LOG` path, `log_failure()` signature, JSONL record format
- `/Users/aumen-server/Projects/researchpapers/src/mouse_research/obsidian.py` — verified `is_duplicate(vault_path, url)` signature
- `/Users/aumen-server/Projects/researchpapers/src/mouse_research/archiver.py` — verified `archive_url(url, config, person, tags)` return type `ArchiveResult`
- `/Users/aumen-server/Projects/researchpapers/src/mouse_research/installer.py` — verified `MOUSE_DIR`, `NODE_DIR` path constants

### Secondary (MEDIUM confidence)
- newspapers-com-scraper README.md — confirmed article shape, event names, `retrieve()` parameter names
- pyproject.toml — confirmed no new dependencies needed (all required libs present)

### Tertiary (LOW confidence)
- None — all findings verified from source code.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed installed, versions verified
- Architecture: HIGH — scraper-wrapper.js interface verified from source; CLI patterns verified from existing codebase
- Pitfalls: HIGH — location bug verified from NewspaperScraper.js source; other pitfalls from code analysis
- Scraper auth behavior: LOW — search without cookies untested empirically; assumed unauthenticated based on README omission

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable library versions; scraper source static)
