# Domain Pitfalls

**Domain:** Newspaper scraping / OCR pipeline with Obsidian output
**Project:** MOUSE Research Pipeline
**Researched:** 2026-04-01

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or complete pipeline failure.

---

### Pitfall 1: Unverified Dependency — newspapers-com-scraper

**What goes wrong:** The Node.js `newspapers-com-scraper` package is used for bulk search and discovery, but it has only 18 commits, no documented issues, no changelog, and no test suite visible in the repository. It was written for a specific snapshot of Newspapers.com's internal API. If Newspapers.com changes their search API response shape, field names, or pagination behavior, the scraper silently returns malformed data or nothing — with no error raised.

**Why it happens:** The package wraps Newspapers.com's undocumented internal search API. There is no contract. The author wrote it for their own use; stability was not a design goal.

**Consequences:**
- Bulk search returns empty results with no indication of why
- Malformed JSON propagates into Python via subprocess stdout, causing parse errors far from the source
- The pipeline's entire discovery phase is blocked until the issue is debugged across a language boundary

**Warning signs:**
- Zero results from searches that should return results
- `JSON.parse` errors in the Python subprocess wrapper
- Node process exits with code 0 but stdout is empty or partial

**Prevention:**
- Validate the scraper in Phase 1 before building anything that depends on it
- Write an integration smoke test: run a known search query (e.g., "wrestling Gettysburg 1978") against the live site and assert at least one result is returned with the expected fields (`title`, `date`, `url`, `publication`)
- Pin the exact npm package version; don't use `latest`
- Capture and log the raw stdout from the Node subprocess before parsing, so failures are diagnosable

**Phase to address:** Phase 1 (foundation/validation) — must be confirmed working before the bulk discovery phase is built.

---

### Pitfall 2: GLM-OCR Hallucination on Degraded 1970s–80s Newspaper Scans

**What goes wrong:** GLM-OCR is a generative model (0.9B vision-language decoder). Unlike deterministic OCR engines that either read a character or fail, a generative model fills in plausible-looking text when the image is ambiguous. On clean, high-contrast documents it performs well. On 1970s microfilm scans with ink bleed, column separators, torn margins, skewed text, and yellowed paper, it will invent text that was never there — names spelled differently, dates wrong, statistics fabricated.

**Why it happens:** Generative models rely on language priors when visual signal is weak. Research confirms that multimodal LLMs "often fail to adequately perceive visual degradation and ambiguity, leading to overreliance on linguistic priors and generating hallucinatory content." For historical newspapers specifically, studies found models "produced hallucinated content or failed to retain the reading order of multi-column layouts."

**Consequences:**
- Documentary research quotes fabricated content
- Person names in articles are wrong — backlinks in Obsidian point to the wrong person
- Errors are not detectable without comparing to the original image
- Trust in the entire archive is undermined once one fabrication is found

**Warning signs:**
- Output text looks fluent and plausible but key nouns (names, scores, dates) differ from what's visible in the screenshot
- OCR output is longer than the visible text — hallucinated continuation after the real content
- Confidence scores (if exposed by Ollama) are uniformly high even on obviously degraded inputs
- Column text is merged or reordered in ways that produce grammatically correct but factually wrong sentences

**Prevention:**
- Always embed the original screenshot in the Obsidian note alongside the OCR output — the human researcher is the final arbiter
- Store OCR output in a clearly labeled section (`## Extracted Text (OCR — verify against image`) never as a standalone source of truth
- For critical quotes intended for the documentary, flag OCR text as unverified until manually checked against the image
- Test GLM-OCR on a sample of 5–10 actual Gettysburg Times / York Daily Record scans from the 1970s before committing to it as the primary engine; if Character Error Rate is unacceptable, Tesseract with preprocessing (deskew, binarize, contrast stretch) may outperform it on this specific corpus
- Implement a word-count sanity check: if OCR output has dramatically more words than a rough pixel-area estimate would suggest, flag it

**Phase to address:** Phase 1 (OCR validation) — sample the real corpus before building the full pipeline around GLM-OCR.

---

### Pitfall 3: Newspapers.com Cookie Expiry With No Re-Login Prompt

**What goes wrong:** Playwright saves session state (cookies + localStorage) to a file via `context.storageState()`. Newspapers.com sessions expire. If the pipeline loads stale cookies and silently fails to authenticate, it will either fetch the unauthenticated version of an article (no image, no full text) or get redirected to a login page — and the pipeline proceeds as if it succeeded, storing empty or broken content.

**Why it happens:** Playwright's `storageState` has no expiry awareness. Loading a state file from last week gives no error — it just presents expired cookies to the server. Newspapers.com does not raise an HTTP error on expired sessions; it silently serves a degraded page.

**Consequences:**
- Screenshots capture login wall pages, not article content
- OCR runs on a login prompt image, producing garbage
- Obsidian notes are created with broken content and the user doesn't know until they open them
- Bulk batch of 50 articles is silently archived as empty

**Warning signs:**
- Screenshots show a Newspapers.com login or subscribe page instead of article content
- HTML capture includes phrases like "Sign in", "Subscribe", "Create account"
- newspaper4k/Trafilatura extracts near-zero text from pages that should have articles

**Prevention:**
- After loading `storageState`, perform an explicit authentication check before every scraping session: fetch a known authenticated URL and assert a logged-in indicator is present (e.g., account menu element, absence of "Sign in" text)
- If the check fails, halt immediately with a clear human-readable error: `"Session expired. Run: mouse-research login"` — do not silently proceed
- Implement the `mouse-research login` interactive flow as a first-class command (not an afterthought) that opens a visible browser window for manual login, then saves fresh `storageState`
- Store the `storageState` file timestamp and warn if it is older than 7 days even if the check passes
- Never run batch archiving without a pre-flight auth check

**Phase to address:** Phase 1 (auth foundation) — the session check and login command must exist before any URL archiving is built.

---

## Moderate Pitfalls

---

### Pitfall 4: Multi-Column Layout Destroys OCR Reading Order

**What goes wrong:** 1970s Pennsylvania newspapers used dense 6–8 column layouts. Without explicit layout analysis, GLM-OCR (and Tesseract) process the full page image and return text in the wrong reading order — mixing columns together or reading across columns horizontally rather than down each column. The resulting text is grammatically incoherent: half a sentence from column 1 is followed by the first word of column 3.

**Why it happens:** Neither Tesseract nor generative vision models reliably detect column boundaries in historical newspaper scans. Tesseract's default page segmentation mode (`--psm 3`) attempts auto-layout but "often fails" on multi-column historical content. Generative models attempt to produce readable text using language priors, which sometimes produces plausible-sounding but column-mixed output.

**Warning signs:**
- OCR output contains sentence fragments that switch topic mid-sentence
- Sports statistics appear mid-paragraph in a story about an event
- Names appear without context (e.g., "Smith 14 the crowd gathered")

**Prevention:**
- If the source is a full newspaper page, crop to the target article region before OCR — Playwright screenshot of the clipped article element, not the whole page
- For Newspapers.com article pages, the platform typically presents the article image already cropped; verify this is what's being screenshotted
- For local image OCR (`mouse-research ocr <image>`), document that full-page scans with multiple columns will produce degraded results and the user should crop to the article first
- Test on actual 1970s Gettysburg Times layout during Phase 1 OCR validation

**Phase to address:** Phase 1 (OCR validation), with documentation in user-facing help text.

---

### Pitfall 5: Python/Node.js Subprocess Interop Failures Are Silent

**What goes wrong:** The Node.js scraper is invoked as a Python subprocess. If Node.js is not in `PATH`, if the `node_modules` directory is missing, if the scraper emits a warning to stderr instead of stdout, or if it exits with code 0 but produces partial JSON — Python receives bad data with no clear error message. Errors in one language don't propagate cleanly to the other.

**Why it happens:** Python `subprocess` captures stdout and stderr separately. Node.js processes commonly print warnings, deprecation notices, and debug output to stderr while putting real data on stdout. If stderr is not captured and logged, critical error messages from the Node.js process are silently discarded. Additionally, Node.js process startup failure (missing dependency, syntax error in package) returns exit code 1 — which Python must explicitly check.

**Consequences:**
- Pipeline fails with a cryptic `json.JSONDecodeError` in Python, pointing at Python code rather than the Node.js problem
- Node.js dependency installation problems only surface at runtime
- `npm install` not being run on first use causes immediate failures

**Warning signs:**
- `JSONDecodeError` or empty results on the first run of bulk search
- Python process hangs waiting for stdout that never comes (Node process crashed)
- `mouse-research doctor` reports Node.js present but scraper still fails

**Prevention:**
- Always capture both stdout and stderr from the subprocess; log stderr separately before attempting to parse stdout
- Check subprocess exit code explicitly; raise a descriptive Python exception if non-zero: `"newspapers-com-scraper exited with code 1. stderr: [...]"`
- The `mouse-research doctor` health check must verify: Node.js version, `node_modules` presence in the scraper directory, and a dry-run invocation returning valid JSON
- Document the required `npm install` step clearly; consider automating it in the `doctor` command

**Phase to address:** Phase 2 (bulk search integration) — but the subprocess wrapper pattern should be established in Phase 1.

---

### Pitfall 6: Obsidian File Naming Collisions and Broken Wikilinks

**What goes wrong:** Wikilinks in Obsidian resolve by filename (without extension). If two articles about the same person are titled similarly, or if a person note and an article note share a similar filename, links silently resolve to the wrong file. Additionally, article titles from Newspapers.com often contain characters that are illegal or problematic in filenames: colons, slashes, question marks, quotes.

**Why it happens:** Obsidian's wikilink resolution is case-insensitive and matches on filename stem. Automated file creation from article metadata may produce names like `Wrestling - Gettysburg 1978.md` and `Wrestling — Gettysburg 1978.md` (em-dash vs hyphen) that appear identical to humans but create two separate files with neither linking to the other.

**Consequences:**
- `[[John Smith]]` in one article resolves to a different note than expected if another note with "John Smith" in its filename exists in a different folder
- Person notes accumulate duplicates (one per article that mentions the person) instead of a single canonical note
- Renaming a file breaks all wikilinks pointing to it (Obsidian updates links interactively, but automated pipeline doesn't use the Obsidian app's rename)

**Warning signs:**
- Multiple notes for the same person appear in the vault
- Backlinks count in person notes is lower than the number of articles mentioning them
- File creation errors due to OS-illegal characters in filenames

**Prevention:**
- Implement a canonical filename sanitizer: strip/replace all non-alphanumeric characters except hyphens and spaces; normalize unicode; truncate at 100 characters; use a consistent slug format
- Before creating a person note, check for an existing file matching the person's name (case-insensitive); append to the existing note rather than creating a new one
- Never include the article title raw in the filename; derive it from a sanitized slug of `{publication}-{date}-{slug}`
- Test filename generation against a list of real Newspapers.com article titles before writing to the vault

**Phase to address:** Phase 2 (Obsidian output) — establish the naming convention before the first note is written.

---

### Pitfall 7: newspaper4k Resource Exhaustion on Bulk Runs

**What goes wrong:** A confirmed GitHub issue shows that after downloading several hundred articles, `newspaper4k` enters a failure state where `article.parse()` raises "the article was not downloaded" for all subsequent URLs. The root cause is resource exhaustion in newspaper4k's temporary directory — accumulated files prevent further parsing until the process is restarted.

**Why it happens:** newspaper4k caches article resources in a temp directory (`~/.newspaper_scraper/article_resources`). During long-running batch operations this directory accumulates files. The library does not clean up between articles.

**Consequences:**
- Bulk archive job of 50+ articles silently fails partway through
- Failure logs show errors but the user may not check them during an unattended run
- Re-running the job re-processes already-completed articles

**Warning signs:**
- Errors appear after a certain article count (not on first few articles)
- Error message contains "the article was not downloaded" despite successful Playwright fetch
- Restarting the process makes the error go away temporarily

**Prevention:**
- Use Playwright as the primary fetch mechanism (not newspaper4k's built-in download); pass pre-fetched HTML to newspaper4k for parsing only
- Alternatively, instantiate a fresh `newspaper4k` article object per item rather than reusing state
- Implement the failure retry mechanism specified in the project requirements; log failures to a file so they can be re-run in isolation
- For batch runs, add a progress checkpoint: write a completion marker per article so reruns skip already-completed items

**Phase to address:** Phase 3 (batch processing) — design the batch loop with resource cleanup in mind from the start.

---

## Minor Pitfalls

---

### Pitfall 8: Playwright Screenshot Captures Login Overlay Instead of Article

**What goes wrong:** Some Newspapers.com article pages load with a modal or overlay (subscription prompt, cookie consent banner) that obscures the article image. The screenshot captures the overlay rather than the article, and OCR runs on the overlay text.

**Prevention:**
- Before taking the screenshot, check for and dismiss known overlay selectors (cookie banners, subscription modals)
- Compare screenshot dimensions or color histogram to a known "good" article screenshot to detect full-page overlay capture
- Store the raw HTML alongside the screenshot so problems are diagnosable

**Phase to address:** Phase 1 (single URL archiving).

---

### Pitfall 9: GLM-OCR Ollama Model Not Loaded — Slow First Run

**What goes wrong:** The first invocation of GLM-OCR via Ollama triggers a model load that can take 30–60 seconds on Apple Silicon (model is ~2 GB). If the timeout for the subprocess call is too short, the first OCR call appears to fail.

**Prevention:**
- Warm the model during `mouse-research doctor` (run a trivial OCR call to force load)
- Set a generous timeout (120s) on the first Ollama call; subsequent calls are fast once the model is resident
- Detect "model loading" in Ollama's response rather than treating slow responses as errors

**Phase to address:** Phase 1 (OCR integration).

---

### Pitfall 10: Rate Limiting Insufficient — IP Flagged by Newspapers.com

**What goes wrong:** The project specifies 5-second delays between fetches. This is a reasonable starting point, but Newspapers.com may additionally detect automation via browser fingerprinting (headless Chromium presents different TLS/HTTP2 fingerprints than real Chrome), unusual request patterns (same article metadata fetched seconds apart), or session reuse without human navigation patterns.

**Why it happens:** Modern anti-bot systems (Cloudflare and similar) build composite fingerprints from canvas, WebGL, audio context, header ordering, and TLS cipher suites — not just request rate. Playwright's headless mode is detectable without stealth modifications.

**Warning signs:**
- CAPTCHAs appear after a few requests
- HTTP 429 or 403 responses during batch runs
- Redirect to a "verify you are human" page

**Prevention:**
- Use Playwright with the full Google Chrome executable (`--channel=chrome`) rather than the bundled Chromium — real Chrome has different fingerprints
- Keep the 5-second delay; increase to 10–15 seconds if blocks are encountered
- Avoid running bulk batches of more than 20 articles in a single session; pause between batches
- The project correctly excludes login automation for the scraper search (which doesn't need auth) — this reduces fingerprinting surface

**Phase to address:** Phase 3 (batch processing) — validate rate limits during Phase 1 single-URL testing.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| Foundation / dependency setup | newspapers-com-scraper untested | Smoke test in Phase 1 before any integration work |
| Auth and cookie management | Stale session proceeds silently | Auth check as precondition to every Playwright session |
| OCR engine selection | GLM-OCR hallucination on degraded scans | Sample real 1970s scans before committing to primary engine |
| Obsidian note writing | Filename collisions, duplicate person notes | Canonical slug format + existence check before creating files |
| Batch article processing | newspaper4k resource exhaustion | Use Playwright for fetch; newspaper4k for parse only; retry/checkpoint logging |
| Bulk search via Node.js | Subprocess interop failures are opaque | Capture stderr; check exit code; doctor command validates scraper |
| Multi-column 1970s layouts | Reading order errors in OCR | Crop to article region; document full-page scan limitations |
| Rate limiting | IP flagged after batch runs | Real Chrome binary; 5–15s delays; batch size limits |

---

## Sources

- GLM-OCR hallucination on degraded inputs: [arXiv 2501.11623 — Early evidence of LLMs for OCR/HTR](https://arxiv.org/html/2501.11623v1)
- LLM OCR post-correction failure modes: [OCR Error Post-Correction with LLMs: No Free Lunches — arXiv 2502.01205](https://arxiv.org/html/2502.01205v1)
- Multi-column layout OCR problems: [DocBed: Multi-Stage OCR for Complex Layouts — arXiv 2202.01414](https://arxiv.org/abs/2202.01414)
- Historical newspaper OCR layout analysis: [Enhancing OCR in Historical Documents — Springer Nature](https://link.springer.com/article/10.1007/s00799-025-00413-z)
- GLM-OCR model and architecture: [GLM-OCR on Ollama](https://ollama.com/library/glm-ocr) / [GLM-OCR GitHub](https://github.com/zai-org/GLM-OCR)
- Playwright cookie/session expiry: [Playwright storageState — BrowserStack](https://www.browserstack.com/guide/playwright-storage-state)
- Playwright bot detection: [How to Avoid Bot Detection with Playwright — BrowserStack](https://www.browserstack.com/guide/playwright-bot-detection)
- Playwright Cloudflare bypass challenges: [Playwright Stealth: What Works in 2026](https://dicloak.com/blog-detail/playwright-stealth-what-works-in-2026-and-where-it-falls-short)
- newspapers-com-scraper: [GitHub — njraladdin/newspapers-com-scraper](https://github.com/njraladdin/newspapers-com-scraper)
- newspaper4k resource exhaustion issue: [GitHub Issue #546 — mass fails after hundreds of articles](https://github.com/AndyTheFactory/newspaper4k/issues/546)
- Python/Node.js subprocess interop: [FreeCodeCamp — child_process.spawn](https://www.freecodecamp.org/news/how-to-integrate-a-python-ruby-php-shell-script-with-node-js-using-child-process-spawn-e26ca3268a11/)
- Obsidian wikilink path inconsistencies: [Obsidian Forum — Inconsistent Treatment of Wikilink Path](https://forum.obsidian.md/t/inconsistent-treatment-of-wikilink-path/112694)
