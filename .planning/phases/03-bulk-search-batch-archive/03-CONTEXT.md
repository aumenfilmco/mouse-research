# Phase 3: Bulk Search + Batch Archive - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can search Newspapers.com from the CLI, review results interactively, and send selected articles (or all results) into the archive pipeline with progress tracking and deduplication against the existing vault.

Requirements: BULK-01 through BULK-08

</domain>

<decisions>
## Implementation Decisions

### Search Result Display & Filtering
- Rich Table with columns: #, Newspaper, Date, Location, URL snippet, Match count — consistent with existing Rich Console pattern in cli.py
- Show all results without pagination — scraper returns manageable counts, keeps interactive selection simple
- Exclude vault duplicates from results entirely (success criteria: "filtered to exclude articles already in the vault") with a count footer: "N results excluded (already in vault)"
- Zero results: print "No results found for {query}" with suggestion to broaden search (remove --years/--location)

### Node.js Scraper Integration & Error Handling
- Call via `subprocess.run(['node', scraper_path, ...])` with JSON stdout capture — matches installer.py pattern
- Scraper failure (non-zero exit): print stderr, log to failures.jsonl, exit with error — consistent with Phase 2 error pattern
- Rate-limit/block detection: warn user "Session may have expired — run `mouse-research login newspapers.com`" — aligns with Phase 1 cookie management
- Pass search params as CLI args: `node scraper.js --query "..." --years "1975-1985" --location "Pennsylvania"` — parse scraper's actual CLI interface

### Interactive Selection & Batch Processing UX
- Rich Prompt with `Enter selection (e.g. 1,3,5-12,all):` — matches success criteria syntax exactly
- Rich Progress bar with live task count: `Archiving: [####....] 3/12 — current-article-title`
- Graceful Ctrl+C: print summary of archived-so-far and remaining URLs, don't corrupt failures.jsonl
- retry-failures: read failures.jsonl, show count, reprocess all with same progress display, clear successful entries from log

### Claude's Discretion
- Area 1 (Search Result Display) confirmed by user as Claude's judgment call — recommendations held based on codebase patterns and success criteria alignment
- Exact scraper CLI argument parsing (depends on newspapers-com-scraper's actual interface — will discover during research)
- Internal module structure for search functionality (new searcher.py module vs extending cli.py)
- Selection input parsing implementation details (regex for "1,3,5-12,all" syntax)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/mouse_research/archiver.py` — `archive_url()` is the core pipeline entry point; returns `ArchiveResult` with success/error/skipped status
- `src/mouse_research/cli.py` — Typer app with `_archive_file()` pattern for batch URL processing with 5-second rate limiting
- `src/mouse_research/installer.py` — `MOUSE_DIR` path constant (`~/.mouse-research/`), `NODE_DIR` for scraper location
- `src/mouse_research/logger.py` — `log_failure(url, reason, phase)` for failures.jsonl, `FAILURE_LOG` path constant
- `src/mouse_research/obsidian.py` — `is_duplicate(vault_path, url)` for dedup checking against vault
- `src/mouse_research/types.py` — `ArticleRecord`, `ArchiveResult` dataclasses
- `src/mouse_research/config.py` — `AppConfig` with vault path, rate_limit_seconds, browser settings

### Established Patterns
- Lazy imports inside command functions (install, doctor, login, archive all use this pattern)
- Rich Console for all terminal output (`console = Console()` in cli.py)
- Typer commands with `--verbose` flag for debug logging
- `setup_logging(verbose=verbose)` at CLI entry
- Error handling: catch exceptions, log_failure(), return result object (don't raise in batch mode)
- Rate limiting: `time.sleep(config.rate_limit_seconds)` between fetches in _archive_file()

### Integration Points
- CLI: add `search` and `retry-failures` commands to cli.py Typer app
- Scraper: `~/.mouse-research/node_modules/newspapers-com-scraper/` installed by `mouse-research install`
- Vault dedup: `is_duplicate(config.vault.path, url)` for filtering results
- Archive pipeline: `archive_url(url, config, person=persons, tags=tags)` per selected result
- Failures: `FAILURE_LOG` path for retry-failures, `log_failure()` for recording new failures

</code_context>

<specifics>
## Specific Ideas

- Success criteria defines exact CLI syntax: `mouse-research search "<query>"`, `--years`, `--location`, `--auto-archive`
- Selection syntax from success criteria: `1,3,5-12,all`
- Rate limiting: 5-second delays between fetches (from project constraints)
- Completion summary must show archived/failed counts (success criteria #4)
- `mouse-research retry-failures` reads failures.jsonl specifically (success criteria #5)

</specifics>

<deferred>
## Deferred Ideas

- People notes auto-linking on archive (Phase 4: Research Graph)
- Source notes auto-linking on archive (Phase 4)
- Master article index generation (Phase 4)

</deferred>
