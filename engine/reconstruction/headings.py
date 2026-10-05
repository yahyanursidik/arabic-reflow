"""Heading detection (backlog M2-04).

Signals (PRD 8.10, backlog M2-04): font hierarchy relative to the body size,
bold spans, brevity, absence of terminal punctuation, and numbering patterns
("Bab ...", "1. ...", "1.2 ...", roman numerals). Levels come from the size
ratio; numbering patterns starting with "Bab" map to level 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from engine.extraction.models import RawBlock
from engine.reconstruction.paragraphs import TERMINAL_PUNCTUATION

MAX_HEADING_CHARS = 90
BOLD_FLAG = 16  # PyMuPDF span flag bit for bold

_NUMBERING = re.compile(
    r"^(?:(?P<word>bab|bagian|pasal|jilid|chapter)\s+\S+"
    r"|(?P<numeric>\d{1,2}(?:\.\d{1,2})*)[.)]?\s+\S+"
    r"|(?P<roman>[IVXLC]{1,6})[.)]?\s+\S+)",
    re.IGNORECASE,
)


@dataclass
class HeadingInfo:
    level: int
    confidence: float


def body_font_size(blocks: list[RawBlock]) -> float:
    """Length-weighted median span size — dominated by body text."""
    samples: list[float] = []
    for block in blocks:
        for line in block.lines:
            for span in line.spans:
                samples.extend([span.size] * max(1, len(span.text)))
    if not samples:
        return 0.0
    samples.sort()
    return samples[len(samples) // 2]


def detect_headings(
    blocks: list[RawBlock], body_size: float
) -> dict[int, HeadingInfo]:
    """Return {block.number: HeadingInfo} for blocks that look like headings."""
    result: dict[int, HeadingInfo] = {}
    for block in blocks:
        text = " ".join(block.text.split())
        if not text or len(text) > MAX_HEADING_CHARS:
            continue
        if text[-1] in TERMINAL_PUNCTUATION:
            continue

        sizes = [span.size for line in block.lines for span in line.spans]
        size = max(sizes) if sizes else 0.0
        bold = any(
            span.flags & BOLD_FLAG for line in block.lines for span in line.spans
        )
        match = _NUMBERING.match(text)
        numbered = match is not None
        is_bab = bool(match and match.group("word") and
                      match.group("word").casefold() == "bab")

        ratio = size / body_size if body_size else 1.0
        signals = 0
        if ratio >= 1.15:
            signals += 2
        if bold:
            signals += 1
        if numbered:
            signals += 2

        if signals < 2:
            continue

        if ratio >= 1.5 or is_bab:
            level = 1
        elif ratio >= 1.25:
            level = 2
        else:
            level = 3
        result[block.number] = HeadingInfo(
            level=level, confidence=min(0.9, 0.5 + 0.1 * signals)
        )
    return result
