"""Playwright-based page fetcher for mouse-research pipeline.

Handles two fetch paths:
  1. Newspapers.com: network interception for full-page JPG, DOM crop, 500px resize
  2. Modern web articles: screenshot + HTML only

Critical constraints (Phase 1 validated):
  - channel="chrome" required on macOS — Playwright Chromium fails with ValidationError 54
  - GLM-OCR crashes on images >~500px — article_image_path MUST be ≤500px max dim
  - GLM-OCR hallucinates on full-page images — MUST crop to article region first
"""
import re
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image
from playwright.sync_api import sync_playwright

from mouse_research.config import AppConfig
from mouse_research.cookies import load_cookies
from mouse_research.types import FetchResult


class FetchError(Exception):
    """Raised when fetching a URL fails unrecoverably."""

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"FetchError for {url}: {reason}")


class BrowserSession:
    """Persistent browser session for batch fetching.

    Keeps one browser + context alive across multiple fetch_url calls.
    One browser launch, one Cloudflare solve → all subsequent fetches reuse
    the same context with accumulated cookies.

    Usage:
        with BrowserSession(config) as session:
            for url in urls:
                result = fetch_url(url, config, output_dir, session=session)
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._pw = None
        self._browser = None
        self._contexts: dict[str, object] = {}

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.config.browser.headless,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        return self

    def __exit__(self, *exc):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._contexts.clear()

    def get_context(self, domain: str):
        """Get or create a browser context for the given domain."""
        if domain in self._contexts:
            return self._contexts[domain]

        storage = load_cookies(domain)
        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }
        if storage:
            context_kwargs["storage_state"] = storage

        ctx = self._browser.new_context(**context_kwargs)
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self._contexts[domain] = ctx
        return ctx

    def save_cookies(self, domain: str) -> None:
        """Persist cookies for a domain (call after successful page load)."""
        ctx = self._contexts.get(domain)
        if ctx:
            from mouse_research.cookies import cookie_path
            path = cookie_path(domain)
            path.parent.mkdir(parents=True, exist_ok=True)
            ctx.storage_state(path=str(path))


def _is_newspapers_com(url: str) -> bool:
    return "newspapers.com" in url.lower()


def _extract_domain(url: str) -> str:
    return urlparse(url).netloc.lstrip("www.")


def _download_page_image_via_browser(
    image_url: str,
    output_path: Path,
    context: object,  # Playwright BrowserContext
) -> bool:
    """Download a page image using the authenticated browser context.

    Uses Playwright (not httpx) so the browser's session cookies are sent
    automatically — avoids 403 from img.newspapers.com's Cloudflare protection.

    Returns True on success, False on failure.
    """
    try:
        img_page = context.new_page()
        response = img_page.goto(image_url, wait_until="load", timeout=30000)
        if response and response.ok:
            output_path.write_bytes(response.body())
            img_page.close()
            return True
        img_page.close()
    except Exception:
        pass
    return False


def _detect_cloudflare(html: str) -> bool:
    """Check if the page is a Cloudflare challenge page, not a real article.

    Must be strict — Newspapers.com pages include residual Cloudflare scripts
    even after the challenge resolves. Only trigger on the actual challenge page
    which has a distinctive <title> and lacks real article content.
    """
    lower = html.lower()
    # Cloudflare challenge pages always have "Just a moment" as the title
    if "<title>just a moment</title>" in lower:
        return True
    # Or the explicit verification interstitial (no article content present)
    if "verifying you are human" in lower and "newspapers.com/image" not in lower:
        return True
    return False


def _solve_cloudflare_turnstile(page) -> None:
    """Attempt to auto-solve a Cloudflare Turnstile challenge.

    Looks for the Turnstile iframe, clicks the checkbox inside it,
    and waits briefly for the challenge to process.
    """
    try:
        # Turnstile renders in an iframe with cf-turnstile in the src or parent
        for frame in page.frames:
            if "challenges.cloudflare.com" in (frame.url or ""):
                # Try clicking the checkbox inside the Turnstile iframe
                try:
                    checkbox = frame.locator("input[type='checkbox']")
                    if checkbox.count() > 0:
                        checkbox.first.click(timeout=5000)
                        page.wait_for_timeout(3000)
                        return
                except Exception:
                    pass
                # Alternative: click the label/div wrapping the checkbox
                try:
                    frame.locator("#challenge-stage").click(timeout=5000)
                    page.wait_for_timeout(3000)
                    return
                except Exception:
                    pass

        # Fallback: try clicking the turnstile widget div on the main page
        try:
            page.locator("div.cf-turnstile").click(timeout=5000)
            page.wait_for_timeout(3000)
        except Exception:
            pass

        # Last resort: try clicking in the center of the iframe element
        try:
            iframe_el = page.locator("iframe[src*='challenges.cloudflare.com']")
            if iframe_el.count() > 0:
                iframe_el.first.click(timeout=5000)
                page.wait_for_timeout(3000)
        except Exception:
            pass

    except Exception:
        # Auto-solve failed — the 30s poll loop will catch it
        pass


def _construct_fallback_image_url(article_url: str) -> str | None:
    """Try to construct an img.newspapers.com URL from the article URL's image ID."""
    match = re.search(r"/image/(\d+)", article_url)
    if match:
        image_id = match.group(1)
        return f"https://img.newspapers.com/img/img?id={image_id}&width=2000"
    return None


def _crop_article_image(
    page_image_path: Path,
    page: object,  # Playwright page
    output_path: Path,
) -> Path:
    """Crop and resize article region from a full Newspapers.com page scan.

    Tries DOM bounding box first (Option A), falls back to center-crop (Option B).
    Resizes result to ≤500px max dimension before saving.

    Returns the output_path on success.
    """
    img = Image.open(str(page_image_path))

    cropped = None

    # Option A: DOM bounding box
    try:
        bbox = page.evaluate("""() => {
            const selectors = [
                '.clip-region', '[class*="clip"]', '[class*="article-image"]',
                '[class*="ArticleImage"]', '[data-testid*="article"]'
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 50 && r.height > 50) {
                        return {x: r.x, y: r.y, width: r.width, height: r.height,
                                selector: sel};
                    }
                }
            }
            return null;
        }""")

        if bbox is not None:
            # Compute scale: DOM CSS pixels → page image native pixels
            page_dims = page.evaluate(
                "() => ({w: document.scrollingElement.scrollWidth, "
                "h: document.scrollingElement.scrollHeight})"
            )
            if page_dims["w"] > 0 and page_dims["h"] > 0:
                scale_x = img.width / page_dims["w"]
                scale_y = img.height / page_dims["h"]

                left = int(bbox["x"] * scale_x)
                top = int(bbox["y"] * scale_y)
                right = int((bbox["x"] + bbox["width"]) * scale_x)
                bottom = int((bbox["y"] + bbox["height"]) * scale_y)

                # Clamp to image bounds
                left = max(0, min(left, img.width))
                top = max(0, min(top, img.height))
                right = max(0, min(right, img.width))
                bottom = max(0, min(bottom, img.height))

                candidate = img.crop((left, top, right, bottom))
                if candidate.width >= 100 and candidate.height >= 100:
                    cropped = candidate
    except Exception:
        pass  # Fall through to Option B

    # Option B: Center-crop fallback
    if cropped is None:
        w, h = img.size
        left = int(w * 0.10)
        top = int(h * 0.20)
        right = w - left
        bottom = top + int(h * 0.60)
        cropped = img.crop((left, top, right, bottom))

    # Resize to ≤500px max dimension
    w, h = cropped.size
    scale = 500 / max(w, h)
    if scale < 1.0:
        cropped = cropped.resize(
            (int(w * scale), int(h * scale)),
            Image.Resampling.LANCZOS,
        )

    cropped.save(str(output_path), "JPEG", quality=85)
    return output_path


def fetch_url(
    url: str,
    config: AppConfig,
    output_dir: Path,
    session: BrowserSession | None = None,
) -> FetchResult:
    """Fetch a page and return raw artifacts.

    For Newspapers.com URLs: also extracts and crops the page image.
    For all URLs: captures screenshot and HTML.

    Args:
        url: The article URL to fetch
        config: AppConfig with browser settings and OCR settings
        output_dir: Directory to save screenshot and image files (must exist)
        session: Optional BrowserSession for reusing browser across batch fetches.
                 If None, a one-shot browser is created and closed after this fetch.

    Returns:
        FetchResult with all captured artifacts
    """
    is_ncm = _is_newspapers_com(url)
    domain = _extract_domain(url)

    screenshot_path = output_dir / "screenshot.png"
    page_image_path: Path | None = None
    article_image_path: Path | None = None

    # Use persistent session or create a one-shot browser
    own_browser = session is None

    try:
        if own_browser:
            _pw_ctx = sync_playwright().start()
            browser = _pw_ctx.chromium.launch(
                headless=config.browser.headless,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"],
            )
            storage = load_cookies(domain)
            context_kwargs: dict = {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }
            if storage:
                context_kwargs["storage_state"] = storage
            context = browser.new_context(**context_kwargs)
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        else:
            _pw_ctx = None
            browser = None
            context = session.get_context(domain)

        page = context.new_page()

        # For Newspapers.com: intercept the full-page JPG URL before navigation
        intercepted_image_urls: list[str] = []

        if is_ncm:
            def capture_image(response) -> None:
                if (
                    "img.newspapers.com" in response.url
                    and response.status == 200
                ):
                    ct = response.headers.get("content-type", "")
                    if "image" in ct and not intercepted_image_urls:
                        intercepted_image_urls.append(response.url)

            page.on("response", capture_image)

        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # Check for Cloudflare challenge
        try:
            html = page.content()
        except Exception:
            html = ""

        if _detect_cloudflare(html):
            # Try to auto-solve the Turnstile challenge by clicking the checkbox
            _solve_cloudflare_turnstile(page)

            # Poll until Cloudflare resolves (up to 30s)
            resolved = False
            for _attempt in range(6):
                page.wait_for_timeout(5000)
                try:
                    html = page.content()
                except Exception:
                    continue
                if not _detect_cloudflare(html):
                    resolved = True
                    break

            if not resolved:
                if own_browser:
                    browser.close()
                    _pw_ctx.stop()
                raise FetchError(
                    url,
                    "Cloudflare challenge not resolved after 30s. "
                    "Run: mouse-research login newspapers.com"
                )

        # Capture screenshot and HTML (after Cloudflare check passes)
        page.screenshot(path=str(screenshot_path), full_page=True)

        # Newspapers.com-specific: download page image and crop article region
        if is_ncm:
            page_jpg_path = output_dir / "page_image.jpg"
            image_url_to_download: str | None = None

            if intercepted_image_urls:
                image_url_to_download = intercepted_image_urls[0]
            else:
                # Fallback: construct URL from article URL image ID
                image_url_to_download = _construct_fallback_image_url(url)

            if image_url_to_download:
                # Use browser context (not httpx) to carry session cookies
                success = _download_page_image_via_browser(
                    image_url_to_download,
                    page_jpg_path,
                    context,
                )
                if success:
                    page_image_path = page_jpg_path
                    article_jpg_path = output_dir / "article_image.jpg"
                    article_image_path = _crop_article_image(
                        page_jpg_path,
                        page,
                        article_jpg_path,
                    )

        # Refresh cookies on successful authenticated load
        if own_browser:
            storage = load_cookies(domain)
            if storage:
                context.storage_state(path=storage)
            browser.close()
            _pw_ctx.stop()
        else:
            session.save_cookies(domain)
            page.close()

    except Exception as exc:
        if own_browser and browser:
            try:
                browser.close()
            except Exception:
                pass
            if _pw_ctx:
                try:
                    _pw_ctx.stop()
                except Exception:
                    pass
        elif session and page:
            try:
                page.close()
            except Exception:
                pass
        raise FetchError(url, str(exc)) from exc

    return FetchResult(
        url=url,
        html=html,
        screenshot_path=screenshot_path,
        page_image_path=page_image_path,
        article_image_path=article_image_path,
        is_newspapers_com=is_ncm,
    )
