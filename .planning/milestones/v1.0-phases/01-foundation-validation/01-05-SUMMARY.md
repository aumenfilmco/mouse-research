# Plan 01-05: Empirical Validation — Summary

**Status:** Complete
**Duration:** ~45 min (including dependency installation)

## What Was Done

### newspapers-com-scraper Validation: PASS
- Scraper v1.1.0 works against live Newspapers.com (tested 2026-04-02)
- 50 results returned for "Bermudian Springs wrestling" (1985-1990)
- Structured JSON: title, pageNumber, date, location, keywordMatches, url
- Target papers found: Gettysburg Times (33), Evening Sun (11), Patriot-News (3), York Daily Record (1)
- Required monkey-patching `setupBrowser()` for macOS Chrome path
- npm install timeout needs to be increased (>120s for first-time Puppeteer download)

### GLM-OCR Validation: PASS (with constraints)
- GLM-OCR produces excellent text on article-level crops at 500px max dimension
- CER <5% on 1970s PA newspaper scans (headlines, scores, names all accurate)
- Full-page OCR crashes with GGML assertion error (known llama.cpp bug)
- Full-page OCR at reduced resolution hallucinates body text
- Tesseract 5.5.2 handles full pages at original resolution (acceptable accuracy, no hallucination)

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| GLM-OCR must process article crops, not full pages | GGML bug crashes on large images; hallucination at reduced resolution |
| Max 500px image dimension for GLM-OCR | Reliable threshold for avoiding GGML crashes |
| Tesseract as full-page fallback | No hallucination risk, handles original resolution |
| Scraper wrapper needs monkey-patched setupBrowser | executablePath hardcoded to /usr/bin/google-chrome in module |
| Playwright login uses channel="chrome" not Chromium | Playwright Chromium has macOS launch issues |

## Deviations

- **Playwright browser issue:** `mouse-research login` with Playwright's bundled Chromium fails with ValidationError 54 on macOS. Fixed by using `channel="chrome"` (system Google Chrome). This affects cookies.py — committed fix.
- **GLM-OCR full-page limitation:** Not anticipated in research. Pipeline design must crop articles before OCR. Aligns with ARCH-03 requirement (OCR target article, not full page).

## Dependencies Installed

- Ollama 0.19.0 (Homebrew)
- glm-ocr model (2.2 GB via ollama pull)
- Tesseract 5.5.2 (Homebrew)
- newspapers-com-scraper 1.1.0 (npm in ~/.mouse-research/)

## Files

- `validation/scraper-test.md` — Scraper test results
- `validation/ocr-test.md` — OCR benchmark results
- `validation/scans/` — Test scan images and OCR output

## Self-Check

- [x] newspapers-com-scraper returns valid JSON from live Newspapers.com
- [x] GLM-OCR produces readable text from 1970s scans (article crops)
- [x] CER documented (<5% on crops)
- [x] Both validation files have pass/fail verdicts
- [x] Pipeline implications documented for Phase 2
