"""Lightweight local OCR readiness checks; never download or initialize models."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

LANGUAGE_CODES = {"ar": "ara", "ara": "ara", "id": "ind", "ind": "ind", "en": "eng", "eng": "eng"}
DEFAULT_LANGUAGES = ["ar", "id", "en"]


def language_codes(languages: list[str] | None = None) -> list[str]:
    result = []
    for language in languages or DEFAULT_LANGUAGES:
        if language not in LANGUAGE_CODES:
            raise ValueError(f"unsupported OCR language: {language}")
        code = LANGUAGE_CODES[language]
        if code not in result:
            result.append(code)
    return result


def tesseract_command() -> str | None:
    configured = os.environ.get("TESSERACT_CMD")
    if configured:
        return configured
    executable = shutil.which("tesseract")
    if executable:
        return executable
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Tesseract-OCR/tesseract.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def tesseract_status(languages: list[str] | None = None) -> dict:
    status = {"name": "tesseract", "available": False, "languages": [], "message": ""}
    if importlib.util.find_spec("pytesseract") is None or importlib.util.find_spec("PIL") is None:
        status["message"] = 'Install pip package with: pip install ".[ocr-tesseract]".'
        return status
    command = tesseract_command()
    if not command:
        status["message"] = "Tesseract binary is missing. Install Tesseract and set TESSERACT_CMD or PATH; pip extra .[ocr-tesseract] alone is not sufficient."
        return status
    try:
        output = subprocess.run([command, "--list-langs"], capture_output=True, text=True, timeout=10, check=True)
        packs = sorted({line.strip() for line in output.stdout.splitlines() if line.strip() in LANGUAGE_CODES.values()})
        status["languages"] = [key for key in DEFAULT_LANGUAGES if LANGUAGE_CODES[key] in packs]
        missing = sorted(set(language_codes(languages)) - set(packs))
        if missing:
            status["message"] = f"Missing language data: {', '.join(missing)}. Install traineddata or configure TESSDATA_PREFIX; see the .[ocr-tesseract] setup."
        else:
            status["available"] = True
            status["message"] = "Binary and requested language data are available."
    except (OSError, subprocess.SubprocessError):
        status["message"] = "Cannot execute Tesseract. Check TESSERACT_CMD, language data, and the .[ocr-tesseract] setup."
    return status


def ocr_capabilities(languages: list[str] | None = None) -> dict:
    language_codes(languages)
    paddle = importlib.util.find_spec("paddleocr") is not None and importlib.util.find_spec("paddle") is not None
    engines = [
        {"name": "paddle", "available": paddle, "languages": DEFAULT_LANGUAGES if paddle else [], "message": "Package installed; model availability is checked when OCR starts. Models may require setup." if paddle else 'PaddleOCR runtime is not installed. Install .[ocr-paddle] with a compatible PaddlePaddle runtime.'},
        tesseract_status(languages),
    ]
    return {"engines": engines, "modes": ["native", "auto", "force"], "languages": DEFAULT_LANGUAGES}
