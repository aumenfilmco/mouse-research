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

import httpx
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


def _download_page_image(
    image_url: str,
    output_path: Path,
    storage_path: str | None,
) -> bool:
    """Download a page image from img.newspapers.com via httpx.

    Returns True on success, False on failure.
    """
    cookies: dict[str, str] = {}

    # Load cookies from storage_state JSON if available
    if storage_path:
        import json

        try:
            with open(storage_path) as f:
                state = json.load(f)
            for cookie in state.get("cookies", []):
                cookies[cookie["name"]] = cookie["value"]
        except Exception:
            pass  # Proceed without cookies — image may still be accessible

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.newspapers.com/",
        }
        resp = httpx.get(
            image_url,
            follow_redirects=True,
            timeout=30,
            headers=headers,
            cookies=cookies,
        )
        if resp.status_code == 200:
            output_path.write_bytes(resp.content)
            return True
    except Exception:
        pass

    return False


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

            page.goto(url, wait_until="networkidle", timeout=30000)

            # Capture screenshot and HTML
            page.screenshot(path=str(screenshot_path), full_page=True)
            html = page.content()

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
                    success = _download_page_image(
                        image_url_to_download,
                        page_jpg_path,
                        storage,
                    )
                    if success:
                        page_image_path = page_jpg_path
                        article_jpg_path = output_dir / "article_image.jpg"
                        article_image_path = _crop_article_image(
                            page_jpg_path,
                            page,
                            article_jpg_path,
                        )

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
