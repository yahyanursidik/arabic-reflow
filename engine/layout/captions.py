"""Image/caption relationship detection (backlog M6-05).

A caption is a text block sitting just below an image, horizontally
overlapping it, that starts with a known caption word (or is small-font and
short). The relationship is recorded as ImageBlock.caption_block_id.
"""

from __future__ import annotations

from engine.extraction.models import RawBlock, RawImage

CAPTION_GAP = 40.0  # pt between image bottom and caption top
CAPTION_OVERLAP = 0.3  # share of the image width the caption must span
CAPTION_WORDS = ("gambar", "figure", "fig.", "الشكل", "صورة")
MAX_CAPTION_CHARS = 200


def _overlaps_horizontally(image: RawImage, block: RawBlock) -> bool:
    overlap = min(image.bbox[2], block.bbox[2]) - max(image.bbox[0], block.bbox[0])
    image_width = max(1.0, image.bbox[2] - image.bbox[0])
    return overlap / image_width >= CAPTION_OVERLAP


def _looks_like_caption(text: str, size: float, body_size: float) -> bool:
    stripped = text.strip()
    if len(stripped) > MAX_CAPTION_CHARS:
        return False
    lowered = stripped.casefold()
    if lowered.startswith(CAPTION_WORDS):
        return True
    return body_size > 0 and size <= body_size * 0.98 and len(stripped) <= 80


def find_captions(
    images: list[RawImage], blocks: list[RawBlock], body_size: float
) -> dict[int, int]:
    """Return {image_index: caption_block_number}."""
    result: dict[int, int] = {}
    for index, image in enumerate(images):
        for block in blocks:
            if not block.text.strip():
                continue
            below = block.bbox[1] >= image.bbox[3] - 2
            within_reach = block.bbox[1] <= image.bbox[3] + CAPTION_GAP
            if not (below and within_reach):
                continue
            if not _overlaps_horizontally(image, block):
                continue
            sizes = [span.size for line in block.lines for span in line.spans]
            size = max(sizes) if sizes else 0.0
            if _looks_like_caption(block.text, size, body_size):
                result[index] = block.number
                break
    return result
