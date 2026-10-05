"""OCR layer (backlog M5): replaceable engines behind one interface.

ARCHITECTURE.md 3.5: OCR must be replaceable through a common adapter
interface, and OCR is a fallback, never the default. Engines are lazily
imported — the pipeline works without any OCR dependency installed.
"""

from __future__ import annotations

import struct
from typing import Protocol

import pymupdf
from pydantic import BaseModel, Field


class OcrBox(BaseModel):
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float = Field(ge=0.0, le=1.0)


class OcrLine(BaseModel):
    bbox: tuple[float, float, float, float]
    words: list[OcrBox] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words if w.text.strip())


class OcrPage(BaseModel):
    page: int = Field(
        default=0, ge=0,
        description="1-based PDF page once assigned; 0 while unassigned",
    )
    width: float
    height: float
    lines: list[OcrLine] = Field(default_factory=list)
    engine: str
    mean_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


class OcrEngine(Protocol):
    """Common adapter interface (ARCHITECTURE.md 3.5)."""

    name: str

    def recognize(self, image: bytes, languages: list[str]) -> OcrPage:
        """Recognize a rendered page image (PNG bytes)."""
        ...


class OcrEngineUnavailable(Exception):
    """Raised when a requested engine's dependency is not installed."""


class OcrResult:
    """Internal tag distinguishing OCR-synthesized pages from native ones."""

    pass


def render_page_png(page: pymupdf.Page, dpi: int = 200) -> bytes:
    """Rasterize a PDF page to PNG bytes for OCR input."""
    return page.get_pixmap(dpi=dpi).tobytes("png")


def png_size(image: bytes) -> tuple[float, float]:
    """Pixel dimensions of a PNG (IHDR header), for OCR coordinate scaling."""
    if image[:8] != b"\x89PNG\r\n\x1a\n" or len(image) < 24:
        raise ValueError("not a PNG image")
    width, height = struct.unpack(">II", image[16:24])
    return float(width), float(height)
