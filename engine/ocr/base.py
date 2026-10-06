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


EDGE_INK_THRESHOLD = 235  # channels below this count as ink, not paper
EDGE_STRIP_PX = 3
INITIAL_PADDING = 6.0  # pt
MAX_PADDING = 36.0  # pt; real-world PDFs often report bboxes tighter than ink
PADDING_STEP = 6.0


def _edges_have_ink(pix: "pymupdf.Pixmap") -> bool:
    """True when the outer EDGE_STRIP_PX pixel ring contains non-paper ink."""
    width, height, n = pix.width, pix.height, pix.n
    samples = pix.samples
    if width <= 2 * EDGE_STRIP_PX or height <= 2 * EDGE_STRIP_PX:
        return False
    stride = width * n

    def ink_at(x: int, y: int) -> bool:
        offset = y * stride + x * n
        return any(samples[offset + c] < EDGE_INK_THRESHOLD for c in range(min(n, 3)))

    for y in range(height):
        if y < EDGE_STRIP_PX or y >= height - EDGE_STRIP_PX:
            xs = range(width)
        else:
            xs = list(range(EDGE_STRIP_PX)) + list(range(width - EDGE_STRIP_PX, width))
        for x in xs:
            if ink_at(x, y):
                return True
    return False


def render_region_png(
    page: "pymupdf.Page",
    bbox: "tuple[float, float, float, float]",
    *,
    dpi: int = 200,
) -> bytes:
    """Rasterize a page region, expanding until the edges are ink-free.

    Real-world PDFs frequently report text bboxes tighter than the actual
    glyph ink (broken font metrics in subset fonts — common with Arabic), so
    a fixed small padding clips harakat and descenders. Render with padding,
    inspect the outer pixel ring, and grow the padding until the ring is
    clean paper (or the page edge / MAX_PADDING is reached).
    """
    padding = INITIAL_PADDING
    while True:
        x0, y0, x1, y1 = bbox
        clip = pymupdf.Rect(x0 - padding, y0 - padding, x1 + padding, y1 + padding) & page.rect
        pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), clip=clip)
        if not _edges_have_ink(pix) or padding >= MAX_PADDING:
            return pix.tobytes("png")
        if (
            clip.x0 <= page.rect.x0 + 0.5
            and clip.y0 <= page.rect.y0 + 0.5
            and clip.x1 >= page.rect.x1 - 0.5
            and clip.y1 >= page.rect.y1 - 0.5
        ):
            # Already the whole page; edges are whatever they are.
            return pix.tobytes("png")
        padding = min(padding + PADDING_STEP, MAX_PADDING)


def png_size(image: bytes) -> tuple[float, float]:
    """Pixel dimensions of a PNG (IHDR header), for OCR coordinate scaling."""
    if image[:8] != b"\x89PNG\r\n\x1a\n" or len(image) < 24:
        raise ValueError("not a PNG image")
    width, height = struct.unpack(">II", image[16:24])
    return float(width), float(height)
