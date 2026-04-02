"""Pipeline orchestrator for mouse-research single-URL archiving.

Implements the 5-step pipeline:
  Step 1: Fetch  — Playwright fetch, screenshot, Newspapers.com image extraction
  Step 2: Extract — newspaper4k/trafilatura text extraction, source/date detection
  Step 3: OCR    — GLM-OCR (Newspapers.com always) or Tesseract fallback
  Step 4: Metadata — assemble ArticleRecord, detect duplicates
  Step 5: Export  — write vault folder, article.md, metadata.json, copy artifacts

OCR trigger rules (from 02-CONTEXT.md decisions):
  - Newspapers.com: ALWAYS trigger OCR (source is scanned page)
  - Modern web articles: trigger OCR only when text extraction returns < 50 chars
"""
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date as date_cls
from pathlib import Path
from typing import Optional

from mouse_research.config import AppConfig
from mouse_research.extractor import detect_date, detect_source, extract_text
from mouse_research.fetcher import BrowserSession, FetchError, fetch_url
from mouse_research.logger import get_logger, log_failure
from mouse_research.obsidian import (
    create_article_folder,
    is_duplicate,
    make_slug,
    write_article_note,
    write_metadata_json,
)
from mouse_research.ocr import ocr_image
from mouse_research.types import ArticleRecord, OcrResult

logger = get_logger(__name__)


@dataclass
class ArchiveResult:
    """Outcome of a single archive_url() call."""

    url: str
    slug: str
    folder: Optional[Path]
    skipped: bool = False       # True when duplicate detected
    skip_reason: str = ""
    ocr_queued: bool = False    # True when OCR was deferred to queue
    error: Optional[str] = None  # Set when archive failed with exception
    success: bool = False


def archive_url(
    url: str,
    config: AppConfig,
    person: list[str] | None = None,
    tags: list[str] | None = None,
    session: BrowserSession | None = None,
) -> ArchiveResult:
    """Archive a single URL into the Obsidian vault.

    Runs the full 5-step pipeline:
      1. Fetch — Playwright fetch, screenshot, Newspapers.com image extraction
      2. Extract — text extraction, source detection, date detection
      3. OCR — GLM-OCR (always for Newspapers.com) or Tesseract fallback
      4. Metadata — assemble ArticleRecord
      5. Export — write vault folder, article.md, metadata.json, copy artifacts

    Args:
        url: Article URL (Newspapers.com or modern web)
        config: AppConfig with vault, ocr, browser settings
        person: Person names to associate with this article (for frontmatter)
        tags: Tags to apply to the article note

    Returns:
        ArchiveResult with outcome details
    """
    person = person or []
    tags = tags or ["newspaper", "archive"]

    # Step 4 pre-check: Duplicate detection (before any I/O)
    if is_duplicate(config.vault.path, url):
        logger.info("Duplicate detected, skipping: %s", url)
        return ArchiveResult(
            url=url,
            slug="",
            folder=None,
            skipped=True,
            skip_reason="URL already in vault",
        )

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Step 1: Fetch
            logger.info("Step 1: Fetching %s", url)
            fetch_result = fetch_url(url, config, tmp_path, session=session)

            # Step 2: Extract text, source, date
            logger.info("Step 2: Extracting text")
            article_data = extract_text(url, fetch_result.html)
            source_name = detect_source(url, fetch_result.html)
            publish_date = detect_date(url, article_data, fetch_result.html)
            article_data.publish_date = publish_date

            # For Newspapers.com: the <title> tag returns the newspaper name,
            # not the article headline. Title will be patched from OCR in Step 3.

            # Step 3: OCR
            # Trigger rules (from 02-CONTEXT.md):
            #   - Newspapers.com: ALWAYS (source is scanned page)
            #   - Modern web: only when text < 50 chars
            ocr_result = OcrResult()
            should_ocr = (
                fetch_result.is_newspapers_com
                or len(article_data.text.strip()) < 50
            )
            if should_ocr:
                ocr_target = (
                    fetch_result.article_image_path or fetch_result.screenshot_path
                )
                if ocr_target and ocr_target.exists():
                    logger.info("Step 3: OCR on %s", ocr_target.name)
                    ocr_result = ocr_image(ocr_target, config, url=url, article_dir=None)
                    # Patch title from first OCR line if newspaper4k returned
                    # empty/generic title (always the case for Newspapers.com)
                    if (
                        (not article_data.title or fetch_result.is_newspapers_com)
                        and ocr_result.text
                    ):
                        first_line = (
                            ocr_result.text.strip().splitlines()[0]
                            .lstrip("#")
                            .strip()
                        )
                        if first_line and len(first_line) < 120:
                            article_data.title = first_line
                else:
                    logger.warning("Step 3: No image available for OCR — skipping")
            else:
                logger.info(
                    "Step 3: OCR skipped (web article with sufficient text: %d chars)",
                    len(article_data.text.strip()),
                )

            # Step 4: Assemble metadata
            logger.info("Step 4: Assembling metadata")
            slug = make_slug(
                article_data.publish_date,
                source_name,
                article_data.title or "article",
            )
            today = date_cls.today()

            # Create vault folder — all artifacts go here after temp work is done
            folder = create_article_folder(config.vault.path, slug)

            # Copy screenshot
            dest_screenshot = folder / "screenshot.png"
            if fetch_result.screenshot_path.exists():
                shutil.copy2(str(fetch_result.screenshot_path), str(dest_screenshot))

            # Copy page image (Newspapers.com full-page JPG)
            dest_page_image: Optional[Path] = None
            if fetch_result.page_image_path and fetch_result.page_image_path.exists():
                dest_page_image = folder / "page_image.jpg"
                shutil.copy2(
                    str(fetch_result.page_image_path), str(dest_page_image)
                )

            # Copy article crop (Newspapers.com 500px crop)
            dest_article_image: Optional[Path] = None
            if (
                fetch_result.article_image_path
                and fetch_result.article_image_path.exists()
            ):
                dest_article_image = folder / "article_image.jpg"
                shutil.copy2(
                    str(fetch_result.article_image_path), str(dest_article_image)
                )

            # Save raw HTML for reference / re-extraction
            (folder / "source.html").write_text(fetch_result.html, encoding="utf-8")

            # Save raw OCR text when present
            if ocr_result.text:
                (folder / "ocr_raw.md").write_text(
                    ocr_result.text, encoding="utf-8"
                )

            record = ArticleRecord(
                slug=slug,
                url=url,
                source_name=source_name,
                article_data=article_data,
                ocr_result=ocr_result,
                screenshot_path=dest_screenshot,
                page_image_path=dest_page_image,
                article_image_path=dest_article_image,
                person=person,
                tags=tags,
                captured=today,
            )

            # Step 5: Export to vault
            logger.info("Step 5: Writing vault output to %s", folder)
            write_article_note(folder, record)
            write_metadata_json(folder, record)

            # Step 6: Update research graph (non-fatal)
            try:
                from mouse_research.graph import update_graph
                update_graph(record, config)
            except Exception as e:
                logger.error("Graph update failed (non-fatal): %s", e, exc_info=True)

            logger.info("Archive complete: %s", slug)
            return ArchiveResult(
                url=url,
                slug=slug,
                folder=folder,
                ocr_queued=ocr_result.queued,
                success=True,
            )

    except FetchError as e:
        reason = f"Fetch failed: {e}"
        logger.error(reason)
        log_failure(url, reason, phase="archive")
        return ArchiveResult(url=url, slug="", folder=None, error=reason)

    except Exception as e:
        reason = f"Archive failed: {type(e).__name__}: {e}"
        logger.error(reason, exc_info=True)
        log_failure(url, reason, phase="archive")
        return ArchiveResult(url=url, slug="", folder=None, error=reason)
