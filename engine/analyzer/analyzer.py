"""PDF analyzer built on PyMuPDF (backlog M1-01).

Determines native vs scanned vs hybrid classification, text/image coverage,
Arabic presence, embedded fonts, and likely multi-column pages.

Heuristics are intentionally simple and expose confidence; the reading-order
engine (M2/M6) owns real layout analysis.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

from engine.arabic.unicode import is_arabic_char
from engine.analyzer.models import (
    AnalyzerWarning,
    Classification,
    DocumentProfile,
    PageProfile,
)

# A page counts as having a text layer above this many extracted characters.
MIN_TEXT_CHARS = 20
# A page looks scanned when it carries (almost) no text but images cover a
# substantial share of the page area.
SCANNED_IMAGE_COVERAGE = 0.4

WARN_UNSUPPORTED_ENCRYPTION = "ENCRYPTED_PDF"


def _coverage(areas: list[float], page_area: float) -> float:
    """Sum of areas clipped to the page area, as a ratio. Overlaps may double
    count; this is a heuristic signal, not a measurement."""
    if page_area <= 0:
        return 0.0
    return min(1.0, sum(areas) / page_area)


def _page_profile(page: pymupdf.Page, page_number: int) -> PageProfile:
    rect = page.rect
    page_area = abs(rect)

    text_chars = 0
    arabic_chars = 0
    block_areas: list[float] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:  # text blocks only
            continue
        x0, y0, x1, y1 = block["bbox"]
        block_areas.append(max(0.0, x1 - x0) * max(0.0, y1 - y0))
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for ch in span.get("text", ""):
                    text_chars += 1
                    if is_arabic_char(ch):
                        arabic_chars += 1

    image_areas: list[float] = []
    image_count = 0
    for info in page.get_image_info():
        image_count += 1
        x0, y0, x1, y1 = info["bbox"]
        image_areas.append(max(0.0, x1 - x0) * max(0.0, y1 - y0))

    text_coverage = _coverage(block_areas, page_area)
    image_coverage = _coverage(image_areas, page_area)
    has_text = text_chars >= MIN_TEXT_CHARS
    scanned_like = text_chars < MIN_TEXT_CHARS and image_coverage >= SCANNED_IMAGE_COVERAGE

    return PageProfile(
        page=page_number,
        width=round(rect.width, 2),
        height=round(rect.height, 2),
        rotation=page.rotation,
        text_chars=text_chars,
        arabic_chars=arabic_chars,
        text_coverage=round(text_coverage, 3),
        image_coverage=round(image_coverage, 3),
        image_count=image_count,
        has_text=has_text,
        scanned_like=scanned_like,
        likely_multicolumn=_likely_multicolumn(page),
    )


def _likely_multicolumn(page: pymupdf.Page) -> bool:
    """Cheap gutter probe: is there a vertical strip splitting text blocks into
    two non-trivial sides with almost nothing crossing it? Real column
    detection arrives with the layout engine (M6-01); this only flags 'likely'."""
    blocks = [
        pymupdf.Rect(b["bbox"]) for b in page.get_text("dict")["blocks"] if b.get("type") == 0
    ]
    if len(blocks) < 4:
        return False

    width = page.rect.width
    best = False
    for fraction in (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65):
        x = width * fraction
        left = [b for b in blocks if b.x1 < x - 3]
        right = [b for b in blocks if b.x0 > x + 3]
        crossing = len(blocks) - len(left) - len(right)
        if len(left) >= 2 and len(right) >= 2 and crossing <= max(1, len(blocks) // 10):
            best = True
    return best


def analyze(source: Path | bytes | str) -> DocumentProfile:
    """Analyze a PDF from a path, file bytes, or a filename string."""
    if isinstance(source, bytes):
        doc = pymupdf.open(stream=source, filetype="pdf")
    else:
        doc = pymupdf.open(source)

    try:
        if doc.needs_pass:
            # MVP policy: we do not crack or persist passwords (PRD section 12).
            return DocumentProfile(
                page_count=max(1, doc.page_count if not doc.is_encrypted else 0) or 1,
                encrypted=True,
                classification=Classification.SCANNED,
                warnings=[
                    AnalyzerWarning(
                        code=WARN_UNSUPPORTED_ENCRYPTION,
                        message="PDF is encrypted; provide the password to process it.",
                    )
                ],
            )

        pages = [
            _page_profile(doc.load_page(i), i + 1)
            for i in range(doc.page_count)
        ]
        if not pages:
            raise ValueError("PDF contains no pages")

        page_count = len(pages)
        scanned_count = sum(1 for p in pages if p.scanned_like)
        native_count = page_count - scanned_count

        if scanned_count == 0:
            classification = Classification.NATIVE
        elif native_count == 0:
            classification = Classification.SCANNED
        else:
            classification = Classification.HYBRID
        confidence = max(scanned_count, native_count) / page_count

        fonts: list[str] = []
        for i in range(doc.page_count):
            for f in doc.get_page_fonts(i):
                name = f[3]
                if name not in fonts:
                    fonts.append(name)

        return DocumentProfile(
            page_count=page_count,
            text_layer=(native_count / page_count) >= 0.5,
            image_dominant=(scanned_count / page_count) >= 0.5,
            arabic_detected=any(p.arabic_chars > 0 for p in pages),
            classification=classification,
            classification_confidence=round(confidence, 3),
            encrypted=False,
            pages=pages,
            embedded_fonts=fonts[:100],
            likely_multicolumn_pages=[p.page for p in pages if p.likely_multicolumn],
        )
    finally:
        doc.close()
