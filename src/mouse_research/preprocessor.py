"""OpenCV preprocessing pipeline for OCR input.

Prepares scanned newspaper images for GLM-OCR:
  grayscale → CLAHE contrast enhancement → denoising → deskew → resize to ≤500px

Returns PNG bytes suitable for passing directly to ollama.Client.generate(images=[...]).

Critical: max_dim=500 is the validated safe threshold for GLM-OCR on this hardware
(Phase 1: GGML assertion crash above ~500px). Do not raise this without re-validation.
"""
import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def preprocess_for_ocr(image_path: Path, max_dim: int = 500) -> bytes:
    """Preprocess a scanned newspaper image for GLM-OCR.

    Pipeline: grayscale → CLAHE contrast → denoise → deskew → resize to max_dim.

    Args:
        image_path: Path to the article crop image (JPEG or PNG)
        max_dim: Maximum dimension in pixels. Default 500 — DO NOT exceed without
                 re-running Phase 1 GLM-OCR validation (GGML crash threshold).

    Returns:
        PNG image bytes ready for ollama.Client.generate(images=[result])
    """
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    # Step 1: Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 2: CLAHE contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Step 3: Denoise
    denoised = cv2.fastNlMeansDenoising(
        enhanced, h=10, templateWindowSize=7, searchWindowSize=21
    )

    # Step 4: Deskew using minAreaRect on non-zero pixel coordinates
    coords = np.column_stack(np.where(denoised > 0))
    if len(coords) > 10:
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        # Normalize angle to [-45, 45] range
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) > 0.5:  # Only deskew if meaningful skew detected
            (h, w) = denoised.shape[:2]
            M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            denoised = cv2.warpAffine(
                denoised, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

    # Step 5: Resize to max_dim (default 500px — GLM-OCR safe threshold)
    pil_img = Image.fromarray(denoised)
    w, h = pil_img.size
    scale = max_dim / max(w, h)
    if scale < 1.0:
        pil_img = pil_img.resize(
            (int(w * scale), int(h * scale)),
            Image.Resampling.LANCZOS,
        )

    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()
