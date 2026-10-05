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

    images = [
        RawImage(
            bbox=tuple(info["bbox"]),  # type: ignore[arg-type]
            width=int(info["width"]),
            height=int(info["height"]),
            xref=int(info.get("xref") or 0),
        )
        for info in page.get_image_info(xrefs=True)
    ]

    return RawPage(
        page=page_number,
        width=round(rect.width, 2),
        height=round(rect.height, 2),
        rotation=page.rotation,
        blocks=blocks,
        images=images,
    )


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
        return RawDocument(
            page_count=len(pages),
            pages=pages,
            source_filename=(
                Path(doc.name).name if not isinstance(source, bytes) else None
            ),
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
