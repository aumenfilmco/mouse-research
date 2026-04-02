"""Shared dataclasses for the mouse-research pipeline stages.

All pipeline modules (fetcher, extractor, preprocessor, ocr, obsidian, archiver)
import from here. Changing a field here affects all consumers.
"""
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional


@dataclass
class FetchResult:
    """Output of fetcher.py — raw page artifacts from Playwright fetch."""
    url: str
    html: str
    screenshot_path: Path
    page_image_path: Optional[Path]    # Newspapers.com full-page JPG (if extracted)
    article_image_path: Optional[Path] # Cropped + resized article image for OCR
    is_newspapers_com: bool


@dataclass
class ArticleData:
    """Output of extractor.py — structured text from newspaper4k/trafilatura."""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    publish_date: Optional[date] = None
    text: str = ""
    extraction_method: str = "none"    # "newspaper4k" | "trafilatura" | "none"


@dataclass
class OcrResult:
    """Output of ocr.py — text from GLM-OCR or Tesseract."""
    text: str = ""
    engine: str = "none"               # "glm-ocr" | "tesseract" | "queued" | "none"
    queued: bool = False


@dataclass
class ArticleRecord:
    """Complete article record assembled by archiver.py before Obsidian export."""
    slug: str
    url: str
    source_name: str
    article_data: ArticleData
    ocr_result: OcrResult
    screenshot_path: Path
    page_image_path: Optional[Path]
    article_image_path: Optional[Path]
    person: list[str]
    tags: list[str]
    captured: date
