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
    """Check if the page content is a Cloudflare challenge, not the real article."""
    indicators = [
        "Verifying you are human",
        "Performing security verification",
        "security service to protect against",
        "cf-browser-verification",
        "challenge-platform",
    ]
    return any(indicator.lower() in html.lower() for indicator in indicators)


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


def fetch_url(url: str, config: AppConfig, output_dir: Path) -> FetchResult:
    """Fetch a page and return raw artifacts.

    For Newspapers.com URLs: also extracts and crops the page image.
    For all URLs: captures screenshot and HTML.

    Args:
        url: The article URL to fetch
        config: AppConfig with browser settings and OCR settings
        output_dir: Directory to save screenshot and image files (must exist)

    Returns:
        FetchResult with all captured artifacts
    """
    is_ncm = _is_newspapers_com(url)
    domain = _extract_domain(url)
    storage = load_cookies(domain)

    screenshot_path = output_dir / "screenshot.png"
    page_image_path: Path | None = None
    article_image_path: Path | None = None

    try:
        with sync_playwright() as p:
            # CRITICAL: channel="chrome" required on macOS (Phase 1 finding)
            browser = p.chromium.launch(
                headless=config.browser.headless,
                channel="chrome",
            )

            context_kwargs: dict = {}
            if storage:
                context_kwargs["storage_state"] = storage

            context = browser.new_context(**context_kwargs)
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
                if config.browser.headless:
                    browser.close()
                    raise FetchError(
                        url,
                        "Cloudflare challenge detected in headless mode. "
                        "Set browser.headless=false in config or run: mouse-research login newspapers.com"
                    )
                # Non-headless: user can see the Chrome window — wait for them
                from rich.console import Console as _Con
                _Con().print(
                    "[yellow]Cloudflare challenge detected in the Chrome window. "
                    "Please solve it (click 'Verify you are human'), then wait...[/yellow]"
                )
                # Poll until Cloudflare resolves (up to 60s)
                for _attempt in range(12):
                    page.wait_for_timeout(5000)
                    try:
                        html = page.content()
                    except Exception:
                        continue
                    if not _detect_cloudflare(html):
                        break
                else:
                    browser.close()
                    raise FetchError(
                        url,
                        "Cloudflare challenge not resolved after 60s. "
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
            if storage:
                context.storage_state(path=storage)

            browser.close()

    except Exception as exc:
        raise FetchError(url, str(exc)) from exc

    return FetchResult(
        url=url,
        html=html,
        screenshot_path=screenshot_path,
        page_image_path=page_image_path,
        article_image_path=article_image_path,
        is_newspapers_com=is_ncm,
    )
