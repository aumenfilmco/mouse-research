---
phase: 02-single-url-archive-pipeline
plan: "02"
subsystem: text-extraction-preprocessing
tags: [extractor, preprocessor, newspaper4k, trafilatura, opencv, ocr-pipeline]
dependency_graph:
  requires:
    - 02-00  # types.py with ArticleData dataclass
  provides:
    - extract_text (newspaper4k primary, trafilatura fallback)
    - detect_source (domain → publication name)
    - detect_date (article_data → URL pattern → HTML meta → None)
    - preprocess_for_ocr (OpenCV pipeline → PNG bytes)
  affects:
    - 02-03  # fetcher.py (FetchResult feeds into extract_text)
    - 02-05  # archiver.py (consumes both extractor and preprocessor)
tech_stack:
  added: []
  patterns:
    - newspaper4k: article.html + download_state injection (no set_html)
    - trafilatura: bare_extraction() with attribute access (doc.title, doc.text, doc.date)
    - OpenCV: grayscale → CLAHE → fastNlMeansDenoising → minAreaRect deskew → Pillow resize
key_files:
  created:
    - src/mouse_research/extractor.py
    - src/mouse_research/preprocessor.py
  modified: []
decisions:
  - "article.publish_date may be datetime — coerce to date() via hasattr check before storing in ArticleData"
  - "trafilatura bare_extraction() returns Document object with attributes, not a dict"
  - "preprocessor max_dim=500 is a hard validated limit from Phase 1 GLM-OCR crash threshold"
metrics:
  duration: "2 minutes"
  completed: "2026-04-02"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Phase 02 Plan 02: Extractor and Preprocessor Summary

**One-liner:** newspaper4k+trafilatura text extraction pipeline and OpenCV grayscale→CLAHE→denoise→deskew→500px preprocessing pipeline for GLM-OCR.

## What Was Built

### extractor.py
Three public functions consuming pre-fetched HTML:

- **extract_text(url, html) -> ArticleData** — newspaper4k primary (falls back to trafilatura when text < 50 chars). Uses `article.html = html; article.download_state = ArticleDownloadState.SUCCESS; article.parse()` pattern (no `set_html()` call). Trafilatura result accessed via `doc.title`, `doc.text`, `doc.date` attributes (not dict). Returns `ArticleData` from `types.py`.
- **detect_source(url, html) -> str** — `_DOMAIN_MAP` covering newspapers.com (HTML JSON parse), lancasteronline.com, ydr.com, eveningsun.com, gettysburgtimes.com, pennlive.com. Unknown domains titlecased from subdomain.
- **detect_date(url, article_data, html) -> Optional[date]** — 3-level priority: parsed date from article_data → URL patterns (3 variants) → HTML meta tags (datePublished, article:published_time) → None.

### preprocessor.py
One public function:

- **preprocess_for_ocr(image_path, max_dim=500) -> bytes** — Full OpenCV pipeline: grayscale → CLAHE (clipLimit=2.0, tileGridSize=(8,8)) → fastNlMeansDenoising (h=10) → minAreaRect deskew (skips if angle < 0.5°) → Pillow LANCZOS resize to max_dim. Returns PNG bytes ready for `ollama.Client.generate(images=[...])`. max_dim hardcoded to 500 — documented as Phase 1 validated GLM-OCR crash threshold.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1    | 3574b81 | feat(02-02): implement extractor.py |
| 2    | 0f611f9 | feat(02-02): implement preprocessor.py |

## Decisions Made

1. **article.publish_date datetime coercion** — newspaper4k returns a `datetime` object; added `hasattr(x, "date")` guard to coerce to `date` before storing in `ArticleData.publish_date` (field type is `Optional[date]`).
2. **trafilatura attribute access** — `bare_extraction()` returns a `Document` object; all field access uses attribute syntax (`doc.title`, `doc.text`, `doc.date`, `doc.author`).
3. **preprocessor max_dim=500 hard limit** — Documented in both module docstring and function docstring. Phase 1 validation showed GGML assertion crash above ~500px on this hardware.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Coerce article.publish_date datetime to date**
- **Found during:** Task 1 implementation
- **Issue:** Plan template had bare `article.publish_date` — newspaper4k returns a `datetime` object but `ArticleData.publish_date` is typed `Optional[date]`. Direct assignment would store a `datetime`, causing type mismatch downstream.
- **Fix:** Added `article.publish_date.date() if hasattr(article.publish_date, "date") else article.publish_date`
- **Files modified:** src/mouse_research/extractor.py
- **Commit:** 3574b81

**2. [Rule 1 - Bug] Fixed article variable scoping in fallback return**
- **Found during:** Task 1 implementation
- **Issue:** Plan template used `'article' in dir()` to check if article was initialized — unreliable. Replaced with `article is not None` guard using explicit `article = None` initialization before the try block.
- **Fix:** Initialize `article = None` before try, use `article is not None` in fallback return.
- **Files modified:** src/mouse_research/extractor.py
- **Commit:** 3574b81

## Known Stubs

None — both modules are fully implemented with no placeholder data or hardcoded empty values.

## Self-Check: PASSED
