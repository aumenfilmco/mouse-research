# Scraper Validation: newspapers-com-scraper v1.1.0

**Date:** 2026-04-02
**Verdict:** PASS

## Test Setup

- **Package:** newspapers-com-scraper v1.1.0 (npm, installed in ~/.mouse-research/)
- **Wrapper:** scraper-wrapper.js with monkey-patched setupBrowser() to use macOS Chrome path
- **Chrome:** /Applications/Google Chrome.app (headless mode)
- **Query:** `--keyword "Bermudian Springs wrestling" --years 1985-1990 --max-pages 1`

## Results

**50 articles returned** from 1 page of results (134 total available).

### Sources Found

| Newspaper | Count | Location |
|-----------|-------|----------|
| The Gettysburg Times | 33 | Gettysburg, Pennsylvania |
| The Evening Sun | 11 | Hanover, Pennsylvania |
| The Patriot-News | 3 | Harrisburg, Pennsylvania |
| York Daily Record | 1 | York, Pennsylvania |
| Other | 2 | Various PA |

### JSON Structure Per Article

```json
{
  "title": "The Gettysburg Times",
  "pageNumber": "9",
  "date": "1990-03-05",
  "location": "Gettysburg, Pennsylvania",
  "keywordMatches": 15,
  "url": "https://www.newspapers.com/image/46677507?terms=Bermudian+Springs+wrestling"
}
```

All 6 expected fields present: title, pageNumber, date, location, keywordMatches, url.

### Performance

- 1 search page fetched in 4.5 seconds
- 50 articles with keyword match counts returned
- No Cloudflare blocks or anti-bot detection triggered

## Issues Found

1. **executablePath hardcoded:** The scraper's `NewspaperScraper.js` hardcodes `executablePath` to `/usr/bin/google-chrome` on non-Windows. The wrapper must monkey-patch `setupBrowser()` to use the macOS Chrome path. This is a one-time fix in the wrapper, not a runtime concern.

2. **npm install timeout:** The `mouse-research install` command's 120-second timeout is too short for first-time npm install (Puppeteer downloads Chromium). The scraper's own Puppeteer should be configured to use the system Chrome instead, or the timeout should be increased. (Note: npm install did complete, but the Python subprocess timed out.)

## Conclusion

newspapers-com-scraper v1.1.0 works against live Newspapers.com as of 2026-04-02. Returns structured JSON via event emitter. The search API does not require authentication. Results include all target Pennsylvania newspapers. Ready for Phase 3 integration.
