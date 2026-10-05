"""Basic reading-order engine (backlog M2-01).

Simple y,x sorting is never used alone (ARCHITECTURE.md 3.7):

- single-column pages are ordered in visual rows (top to bottom), with
  within-row order following the page's dominant direction;
- pages with a detected column gutter are ordered column by column, with
  full-width blocks (headings, spanning elements) kept at their vertical
  position;
- pages the analyzer flagged as multi-column but where no gutter can be
  established produce an explicit READING_ORDER_UNCERTAIN outcome instead of
  a silent guess.
"""

from __future__ import annotations

from engine.arabic.detector import classify_block
from engine.extraction.models import RawBlock, RawDocument
from engine.layout.columns import find_gutter
from engine.layout.models import LayoutReport, OrderReport
from engine.reflowdoc.models import Direction

ROW_OVERLAP = 0.5  # share of the shorter block's height needed to share a row
COLUMN_TOLERANCE = 3.0  # pt; matches find_gutter


def _vertical_overlap(a: tuple[float, float, float, float],
                      b: tuple[float, float, float, float]) -> float:
    top = max(a[1], b[1])
    bottom = min(a[3], b[3])
    if bottom <= top:
        return 0.0
    shorter = min(a[3] - a[1], b[3] - b[1])
    return (bottom - top) / shorter if shorter > 0 else 0.0


def _row_order(blocks: list[RawBlock], rtl: bool) -> list[RawBlock]:
    """Group blocks into visual rows, then order within rows by direction."""
    ordered = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
    rows: list[list[RawBlock]] = []
    for block in ordered:
        if rows and _vertical_overlap(rows[-1][-1].bbox, block.bbox) >= ROW_OVERLAP:
            rows[-1].append(block)
        else:
            rows.append([block])
    result: list[RawBlock] = []
    for row in rows:
        result.extend(sorted(row, key=lambda b: b.bbox[0], reverse=rtl))
    return result


def _column_order(blocks: list[RawBlock], gutter: float) -> list[RawBlock]:
    """Order left column, right column, keeping full-width blocks in place."""
    left: list[RawBlock] = []
    right: list[RawBlock] = []
    full: list[RawBlock] = []
    for block in blocks:
        if block.bbox[0] > gutter + COLUMN_TOLERANCE:
            right.append(block)
        elif block.bbox[2] < gutter - COLUMN_TOLERANCE:
            left.append(block)
        else:
            full.append(block)
    left.sort(key=lambda b: b.bbox[1])
    right.sort(key=lambda b: b.bbox[1])
    full.sort(key=lambda b: b.bbox[1])

    segment_tops = [float("-inf")] + [f.bbox[3] for f in full]
    segment_bottoms = [f.bbox[1] for f in full] + [float("inf")]
    segments_left = [
        [b for b in left if b.bbox[1] >= segment_tops[i] and b.bbox[3] <= segment_bottoms[i]]
        for i in range(len(full) + 1)
    ]
    segments_right = [
        [b for b in right if b.bbox[1] >= segment_tops[i] and b.bbox[3] <= segment_bottoms[i]]
        for i in range(len(full) + 1)
    ]

    result: list[RawBlock] = []
    for i in range(len(full) + 1):
        result.extend(segments_left[i])
        result.extend(segments_right[i])
        if i < len(full):
            result.append(full[i])
    return result


def _page_is_rtl(blocks: list[RawBlock]) -> bool:
    page_text = "\n".join(b.text for b in blocks)
    return classify_block(page_text).dir is Direction.RTL


def reconstruct_reading_order(
    raw: RawDocument,
    profile: object | None = None,  # DocumentProfile, optional
    layout: LayoutReport | None = None,
) -> tuple[RawDocument, OrderReport]:
    """Order blocks within each page; returns a new RawDocument + OrderReport."""
    flagged: set[int] = set()
    if profile is not None:
        flagged = set(getattr(profile, "likely_multicolumn_pages", []))

    uncertain_pages: list[int] = []
    confidence: dict[int, float] = {}
    gutters: dict[int, float] = {}

    new_pages = []
    for page in raw.pages:
        text_blocks = [b for b in page.blocks if b.type == "text" and b.text.strip()]
        gutter = find_gutter([b.bbox for b in page.blocks], page.width)
        if gutter is not None and len(text_blocks) >= 4:
            ordered = _column_order(text_blocks, gutter)
            page_confidence = 0.85
            gutters[page.page] = round(gutter, 1)
        else:
            ordered = _row_order(text_blocks, _page_is_rtl(text_blocks))
            page_confidence = 0.95
            if page.page in flagged:
                # Analyzer sees column structure we could not establish.
                uncertain_pages.append(page.page)
                page_confidence = 0.5
        confidence[page.page] = page_confidence
        new_pages.append(page.model_copy(update={"blocks": ordered}))

    report = OrderReport(
        uncertain_pages=uncertain_pages, confidence=confidence
    )
    if layout is not None:
        layout.gutters.update(gutters)
    return raw.model_copy(update={"pages": new_pages}), report
