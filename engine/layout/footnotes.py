"""Footnote candidate detection (backlog M6-03).

Heuristic zoning: footnote candidates are short, small-font, marker-prefixed
blocks in the bottom quarter of the page. Candidates become FootnoteBlock
entries with an explicit FOOTNOTE_UNCERTAIN warning — detection is
deliberately conservative and surfaced, never silent.
"""

from __future__ import annotations

import re

from engine.extraction.models import RawBlock

BOTTOM_BAND = 0.75  # block must start within the bottom 25% of the page
SIZE_RATIO = 0.98  # ...in a font no larger than 98% of the body size
MAX_FOOTNOTE_CHARS = 400

MARKER = re.compile(r"^\(?(\d{1,3})[.)\]]?\s+\S")


def detect_footnote_candidates(
    blocks: list[RawBlock], page_height: float, body_size: float
) -> dict[int, str]:
    """Return {block.number: marker} for footnote candidates on the page."""
    candidates: dict[int, str] = {}
    if body_size <= 0:
        return candidates
    for block in blocks:
        if block.bbox[1] < page_height * BOTTOM_BAND:
            continue
        text = " ".join(block.text.split())
        if not text or len(text) > MAX_FOOTNOTE_CHARS:
            continue
        sizes = [span.size for line in block.lines for span in line.spans]
        if not sizes or max(sizes) > body_size * SIZE_RATIO:
            continue
        match = MARKER.match(text)
        if match:
            candidates[block.number] = match.group(1)
    return candidates
