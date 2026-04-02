---
phase: 02-single-url-archive-pipeline
plan: "01"
subsystem: fetcher
tags: [playwright, fetch, newspapers-com, image-interception, crop, ocr-prep]
dependency_graph:
  requires:
    - 02-00 (types.py FetchResult dataclass)
    - cookies.py (load_cookies)
    - config.py (AppConfig, BrowserSettings)
  provides:
    - fetcher.py fetch_url(url, config, output_dir) -> FetchResult
    - FetchError exception class
  affects:
    - 02-02 (extractor.py — consumes FetchResult.html)
    - 02-03 (ocr.py — consumes FetchResult.article_image_path)
    - 02-06 (archiver.py — consumes full FetchResult)
tech_stack:
  added: []
  patterns:
    - Playwright sync_playwright with channel="chrome" (macOS-required)
    - page.on("response") network interception for img.newspapers.com
    - httpx.get() image download with storage_state cookie passthrough
    - Pillow crop + LANCZOS resize to <=500px max dimension
    - DOM bounding box crop with center-crop fallback
key_files:
  created:
    - src/mouse_research/fetcher.py
  modified: []
decisions:
  - channel="chrome" hardcoded unconditionally — not configurable — Phase 1 validated this is required on macOS
  - intercepted_image_urls uses list for nonlocal mutation inside closure (Playwright response handler pattern)
  - httpx downloads image with cookies extracted from storage_state JSON to avoid re-auth
  - URL fallback uses /image/(\d+) regex from article URL to construct img.newspapers.com endpoint
  - DOM crop validates width/height >=100px before accepting; otherwise falls to center-crop
metrics:
  duration: "~70 seconds"
  completed: "2026-04-01"
  tasks: 1
  files: 1
---

# Phase 02 Plan 01: Fetcher Implementation Summary

**One-liner:** Playwright fetch with channel="chrome", img.newspapers.com network interception, DOM-bbox crop falling back to center-crop, Pillow resize to <=500px for GLM-OCR.

## What Was Built

`src/mouse_research/fetcher.py` — the first step in the 5-step pipeline. Implements two fetch paths:

1. **Newspapers.com path:** network interception captures the full-page JPG URL from `img.newspapers.com` responses, httpx downloads it with cookie passthrough from storage_state JSON, then Pillow crops the article region (DOM bbox Option A, center-crop Option B fallback) and resizes to <=500px max dimension.

2. **Modern web path:** screenshot + HTML only (no image processing).

### Key Implementation Details

- `fetch_url(url, config, output_dir) -> FetchResult` — single public interface
- `FetchError(url, reason)` — exception class for caller error handling
- `channel="chrome"` hardcoded in every Playwright launch — Phase 1 critical finding; Playwright bundled Chromium fails with ValidationError 54 on macOS
- Response listener registered before `page.goto()` to guarantee interception
- Fallback image URL construction via regex on article URL: `/image/(\d+)` → `img.newspapers.com/img/img?id={id}&width=2000`
- Cookie injection: reads `cookies[]` array from storage_state JSON and passes to httpx
- DOM crop scale factors computed as `image.width / page.scrollWidth` and `image.height / page.scrollHeight` to map CSS pixels to native image pixels
- Crop validated: if <100x100px after DOM extraction, falls to center-crop

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 3d96887 | feat(02-01): implement fetcher.py with Playwright fetch and Newspapers.com image extraction |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all FetchResult fields are wired. article_image_path is None for non-Newspapers.com URLs by design (no crop needed for modern web articles).

## Self-Check: PASSED

- [x] src/mouse_research/fetcher.py exists
- [x] `from mouse_research.fetcher import fetch_url, FetchError` imports without error
- [x] channel="chrome" present in Playwright launch call (line 211)
- [x] page.on("response") intercept registered (line 234)
- [x] 500px resize logic present (lines 171-176)
- [x] DOM crop Option A (lines 117-154) and center-crop Option B (lines 157-163) both present
- [x] Returns FetchResult dataclass (not dict/tuple)
- [x] FetchError defined (lines 25-31)
- [x] Commit 3d96887 exists
