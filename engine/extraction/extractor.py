"""PyMuPDF extraction of pages, blocks, lines, and spans (backlog M1-02).

The extractor is pure observation: it preserves what PyMuPDF reports
(text in logical order, fonts, sizes, bboxes) and transforms nothing.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

from engine.extraction.models import RawBlock, RawDocument, RawImage, RawLine, RawPage, RawSpan


def extract_page(page: pymupdf.Page, page_number: int) -> RawPage:
    rect = page.rect
    blocks: list[RawBlock] = []
    inline_images = []

    for block in page.get_text("dict")["blocks"]:
        if block.get("type") == 0:
            lines = [
                RawLine(
                    bbox=tuple(line["bbox"]),  # type: ignore[arg-type]
                    spans=[
                        RawSpan(
                            text=span["text"],
                            font=span["font"],
                            size=round(float(span["size"]), 2),
                            flags=span.get("flags", 0),
                            color=span.get("color", 0),
                            bbox=tuple(span["bbox"]),  # type: ignore[arg-type]
                        )
                        for span in line.get("spans", [])
                    ],
                )
                for line in block.get("lines", [])
            ]
            blocks.append(
                RawBlock(
                    number=block.get("number", len(blocks)),
                    type="text",
                    bbox=tuple(block["bbox"]),  # type: ignore[arg-type]
                    lines=lines,
                )
            )
        elif block.get("type") == 1 and block.get("image"):
            inline_images.append(block)

    images = [
        RawImage(
            bbox=tuple(info["bbox"]),  # type: ignore[arg-type]
            width=int(info["width"]),
            height=int(info["height"]),
            xref=int(info.get("xref") or 0),
        )
        for info in page.get_image_info(xrefs=True)
    ]

    # Inline PDF images have xref=0 and cannot be passed to extract_image().
    # get_text('dict') already exposes their encoded payloads. Match each
    # occurrence by geometry/dimensions, consuming it once rather than making
    # a resource with no bytes (which produces broken EPUB image links).
    for image in images:
        if image.xref:
            continue
        candidates = [
            (sum(abs(a - b) for a, b in zip(block["bbox"], image.bbox)), index)
            for index, block in enumerate(inline_images)
            if (
                int(block.get("width", 0)) == image.width
                and int(block.get("height", 0)) == image.height
                # Some PDFs report image_info bounds rounded outwards to
                # whole points while dict bounds retain the transform floats.
                and all(abs(a - b) <= 1.01 for a, b in zip(block["bbox"], image.bbox))
            )
        ]
        if candidates:
            _, index = min(candidates)
            block = inline_images.pop(index)
            image.content = block["image"]
            image.media_type = f"image/{block.get('ext', 'png')}".replace("jpg", "jpeg")

    return RawPage(
        page=page_number,
        width=round(rect.width, 2),
        height=round(rect.height, 2),
        rotation=page.rotation,
        blocks=blocks,
        images=images,
        rule_segments=_rule_segments(page),
    )


MAX_RULE_SEGMENTS = 200
_RULE_THICKNESS = 2.5  # pt; drawings thicker than this are shapes, not rules


def _rule_segments(page: pymupdf.Page) -> list[tuple[float, float, float, float]]:
    """Thin straight vector segments (table rules, underlines), capped.

    PyMuPDF reports drawings as rects; a rect thin in one dimension is a
    rule line. Table detection requires these — geometry alone cannot
    distinguish a grid from a two-column prose page.
    """
    segments: list[tuple[float, float, float, float]] = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None:
            continue
        width = rect.width
        height = rect.height
        if width <= 0 and height <= 0:
            continue
        if min(width, height) > _RULE_THICKNESS:
            continue
        segments.append((round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)))
        if len(segments) >= MAX_RULE_SEGMENTS:
            break
    return segments


def extract(source: str | bytes) -> RawDocument:
    """Extract raw primitives from a PDF path or bytes."""
    if isinstance(source, bytes):
        doc = pymupdf.open(stream=source, filetype="pdf")
    else:
        doc = pymupdf.open(source)

    try:
        if doc.needs_pass:
            raise ValueError("PDF is encrypted; refuse to extract without a password")
        pages = [extract_page(doc.load_page(i), i + 1) for i in range(doc.page_count)]
        _attach_image_contents(doc, pages)
        info = doc.metadata or {}
        return RawDocument(
            page_count=len(pages),
            pages=pages,
            source_filename=(
                Path(doc.name).name if not isinstance(source, bytes) else None
            ),
            pdf_title=(info.get("title") or "").strip() or None,
            pdf_author=(info.get("author") or "").strip() or None,
        )
    finally:
        doc.close()


def _attach_image_contents(doc: pymupdf.Document, pages: list[RawPage]) -> None:
    """Pull encoded image bytes from the PDF into the raw model (M6-05)."""
    for page in pages:
        for image in page.images:
            if not image.xref:
                continue
            try:
                info = doc.extract_image(image.xref)
            except Exception:
                continue
            image.content = info["image"]
            image.media_type = f"image/{info['ext']}".replace("jpg", "jpeg")
