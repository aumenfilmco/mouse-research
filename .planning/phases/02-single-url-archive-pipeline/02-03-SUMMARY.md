---
phase: 02-single-url-archive-pipeline
plan: "03"
subsystem: ocr
tags: [ocr, glm-ocr, tesseract, ollama, preprocessing]
dependency_graph:
  requires:
    - 02-00  # types.py (OcrResult)
    - 02-02  # preprocessor.py (preprocess_for_ocr)
  provides:
    - ocr.py (ocr_image)
  affects:
    - 02-04  # archiver.py will call ocr_image()
tech_stack:
  added: []
  patterns:
    - Three-tier OCR fallback: GLM-OCR → Tesseract → queue
    - Mandatory preprocessing before GLM-OCR (max_dim=500 hard limit)
    - httpx availability check before attempting Ollama connection
key_files:
  created:
    - src/mouse_research/ocr.py
  modified: []
decisions:
  - "response.response attribute (not dict key) used for ollama GenerateResponse — verified against .venv SDK"
  - "preprocess_for_ocr() called unconditionally inside _ocr_with_glm() — cannot be bypassed by callers"
  - "Tesseract runs on raw image at original resolution (no preprocessing) — avoids GGML constraints"
metrics:
  duration: 54s
  completed: "2026-04-02"
  tasks: 1
  files: 1
requirements:
  - ARCH-03
  - ARCH-04
---

# Phase 02 Plan 03: OCR Layer Summary

**One-liner:** GLM-OCR via Ollama as primary with mandatory 500px preprocessing, Tesseract fallback, and jsonl queue when neither engine is available.

## What Was Built

`src/mouse_research/ocr.py` — the OCR layer implementing a three-tier fallback pipeline:

1. **GLM-OCR (Tier 1):** Checks Ollama availability via `/api/tags`, preprocesses the image to ≤500px PNG bytes via `preprocess_for_ocr()`, then calls `ollama.Client.generate(model="glm-ocr", images=[bytes])`. Returns `OcrResult(engine="glm-ocr")`.

2. **Tesseract (Tier 2):** Opens the image at original resolution with Pillow and runs `pytesseract.image_to_string(img, config="--psm 1")`. Returns `OcrResult(engine="tesseract")`.

3. **OCR Queue (Tier 3):** Appends a JSON record to `~/.mouse-research/ocr-queue.jsonl` with `image_path`, `url`, `article_dir`, and `queued_at`. Returns `OcrResult(engine="queued", queued=True)`.

## Key Contracts Enforced

- `_GLM_OCR_PROMPT` contains the `[illegible]` instruction — unchangeable constant
- `preprocess_for_ocr(image_path, max_dim=500)` called inside `_ocr_with_glm()` — mandatory, not optional
- `response.response` attribute access (not `response["response"]`) for `GenerateResponse`
- `_OCR_QUEUE_PATH = Path.home() / ".mouse-research" / "ocr-queue.jsonl"`

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Task | Description | Hash |
|------|-------------|------|
| 1 | feat(02-03): implement ocr.py with GLM-OCR, Tesseract fallback, and OCR queue | 813ea40 |

## Self-Check: PASSED

- `src/mouse_research/ocr.py` — FOUND
- Commit `813ea40` — FOUND
- Import `.venv/bin/python3 -c "from mouse_research.ocr import ocr_image"` — exits 0
- All acceptance criteria verified: `[illegible]` in prompt, `max_dim=500`, `response.response`, `--psm 1`, `ocr-queue.jsonl`, correct tier order
