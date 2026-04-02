"""OCR layer for mouse-research pipeline.

Three-tier fallback:
  1. GLM-OCR via Ollama (primary) — highest accuracy on 1970s newsprint
  2. Tesseract (fallback) — when Ollama unavailable; runs on full image at original res
  3. OCR queue — when neither engine available; saves image path to ocr-queue.jsonl

CRITICAL constraints (Phase 1 validated):
  - GLM-OCR MUST receive preprocessed images at ≤500px max dimension
  - GLM-OCR crashes with GGML assertion on images >~500px
  - GLM-OCR hallucinates on full-page images — always crop first (fetcher.py responsibility)
  - Tesseract handles full pages at original resolution without these issues
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from mouse_research.config import AppConfig
from mouse_research.logger import get_logger
from mouse_research.types import OcrResult

_GLM_OCR_PROMPT = (
    "Extract all text from this newspaper article image. "
    "Preserve headlines, subheadlines, bylines, and body text. "
    "Output as clean Markdown. "
    "If text is illegible, mark it as [illegible]. "
    "Do not guess or fabricate text that cannot be read."
)

_OCR_QUEUE_PATH = Path.home() / ".mouse-research" / "ocr-queue.jsonl"


def _ollama_available(ollama_url: str) -> bool:
    """Check if Ollama server is reachable and glm-ocr model is loaded."""
    import httpx
    try:
        resp = httpx.get(f"{ollama_url}/api/tags", timeout=5.0)
        if resp.status_code != 200:
            return False
        models = [m["name"] for m in resp.json().get("models", [])]
        return any("glm-ocr" in m for m in models)
    except Exception:
        return False


def _ocr_with_glm(image_path: Path, ollama_url: str) -> str:
    """Run GLM-OCR via Ollama. Raises on failure."""
    import ollama
    from mouse_research.preprocessor import preprocess_for_ocr

    # Preprocess: grayscale → CLAHE → denoise → deskew → 500px resize
    # This is MANDATORY — do not skip even if image looks small
    image_bytes = preprocess_for_ocr(image_path, max_dim=500)

    client = ollama.Client(host=ollama_url)
    response = client.generate(
        model="glm-ocr",
        prompt=_GLM_OCR_PROMPT,
        images=[image_bytes],  # bytes accepted directly — no manual base64
    )
    return response.response   # GenerateResponse.response field (verified in .venv)


def _ocr_with_tesseract(image_path: Path) -> str:
    """Run Tesseract on the image at original resolution.

    Tesseract handles full-page images at original resolution correctly
    (no GGML crash, no hallucination). Use --psm 1 for automatic page
    segmentation with OSD.
    """
    import pytesseract
    from PIL import Image
    img = Image.open(str(image_path))
    return pytesseract.image_to_string(img, config="--psm 1")


def _enqueue_for_ocr(image_path: Path, url: str, article_dir: Optional[Path]) -> None:
    """Append image to OCR queue for later processing."""
    _OCR_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "image_path": str(image_path),
        "url": url,
        "article_dir": str(article_dir) if article_dir else None,
        "queued_at": datetime.now().isoformat(),
    }
    with _OCR_QUEUE_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def ocr_image(
    image_path: Path,
    config: AppConfig,
    url: str = "",
    article_dir: Optional[Path] = None,
) -> OcrResult:
    """OCR an article image with three-tier fallback.

    Args:
        image_path: Path to the article crop image (should be ≤500px for GLM-OCR)
        config: AppConfig with ocr.ollama_url
        url: Article URL (for OCR queue record)
        article_dir: Article output directory (for OCR queue record)

    Returns:
        OcrResult with text, engine used, and queued flag
    """
    logger = get_logger(__name__)

    # Tier 1: GLM-OCR
    if _ollama_available(config.ocr.ollama_url):
        try:
            text = _ocr_with_glm(image_path, config.ocr.ollama_url)
            logger.info("GLM-OCR succeeded: %d chars", len(text))
            return OcrResult(text=text, engine="glm-ocr")
        except Exception as e:
            logger.warning("GLM-OCR failed: %s — trying Tesseract", e)

    # Tier 2: Tesseract
    try:
        text = _ocr_with_tesseract(image_path)
        logger.info("Tesseract OCR succeeded: %d chars", len(text))
        return OcrResult(text=text, engine="tesseract")
    except Exception as e:
        logger.warning("Tesseract failed: %s — queuing for later OCR", e)

    # Tier 3: Queue
    _enqueue_for_ocr(image_path, url, article_dir)
    logger.warning("OCR queued: %s", image_path)
    return OcrResult(text="", engine="queued", queued=True)
