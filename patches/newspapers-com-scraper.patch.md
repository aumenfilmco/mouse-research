# newspapers-com-scraper patches

Applied to `~/.mouse-research/node_modules/newspapers-com-scraper/lib/NewspaperScraper.js`

These fixes are needed because the npm package (v1.1.0) has two bugs that prevent
article extraction. Re-apply after `mouse-research install` or `npm install`.

## Patch 1: Cloudflare CAPTCHA detection (line ~234)

```diff
- if (await page.$('text="Verifying you are human"')) {
+ if ((await page.content()).includes('Verifying you are human')) {
```

**Why:** `page.$('text=...')` is not valid Puppeteer syntax — always returns null,
so CAPTCHAs are never detected and `response.json()` crashes on HTML.

## Patch 2: Empty records handling (line ~242)

```diff
- throw new RetryableError("No records found");
+ return null;
```

**Why:** The library already handles null results via `filter(result => result !== null)`
and `if (!validResults.length) break`. Throwing crashes the entire run instead of
gracefully stopping at the last page of results.
