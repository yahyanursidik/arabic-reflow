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
from engine.layout.columns import find_gutters
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


def _column_order(
    blocks: list[RawBlock], gutters: list[float], page_width: float
) -> list[RawBlock]:
    """Order blocks column by column, keeping full-width blocks in place.

    Gutters partition the page into N+1 column regions. Blocks lying fully
    inside one region read top-to-bottom; regions read left-to-right (in
    logical order — RTL column layouts remain a known limitation, see
    docs/reconstruction.md). Blocks crossing any gutter are section
    separators and stay at their vertical position.
    """
    boundaries = [float("-inf")] + list(gutters) + [float("inf")]
    columns: list[list[RawBlock]] = [[] for _ in range(len(boundaries) - 1)]
    full: list[RawBlock] = []

    for block in blocks:
        placed = False
        for i in range(len(columns)):
            left = boundaries[i] + COLUMN_TOLERANCE
            right = boundaries[i + 1] - COLUMN_TOLERANCE
            if block.bbox[0] > left and block.bbox[2] < right:
                columns[i].append(block)
                placed = True
                break
        if not placed:
            full.append(block)

    for column in columns:
        column.sort(key=lambda b: b.bbox[1])
    full.sort(key=lambda b: b.bbox[1])

    segment_tops = [float("-inf")] + [f.bbox[3] for f in full]
    segment_bottoms = [f.bbox[1] for f in full] + [float("inf")]
    result: list[RawBlock] = []
    for segment in range(len(full) + 1):
        top, bottom = segment_tops[segment], segment_bottoms[segment]
        for column in columns:
            result.extend(b for b in column if b.bbox[1] >= top and b.bbox[3] <= bottom)
        if segment < len(full):
            result.append(full[segment])
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
        gutters = find_gutters([b.bbox for b in page.blocks], 0.0, page.width)
        if gutters and len(text_blocks) >= 4:
            ordered = _column_order(text_blocks, gutters, page.width)
            page_confidence = 0.85 if len(gutters) == 1 else 0.8
            gutters_record = [round(g, 1) for g in gutters]
        else:
            ordered = _row_order(text_blocks, _page_is_rtl(text_blocks))
            page_confidence = 0.95
            if page.page in flagged:
                # Analyzer sees column structure we could not establish.
                uncertain_pages.append(page.page)
                page_confidence = 0.5
            gutters_record = []
        confidence[page.page] = page_confidence
        if gutters_record and layout is not None:
            layout.gutters[page.page] = gutters_record[0]
            layout.all_gutters[page.page] = gutters_record
        new_pages.append(page.model_copy(update={"blocks": ordered}))

    report = OrderReport(
        uncertain_pages=uncertain_pages, confidence=confidence
    )
    return raw.model_copy(update={"pages": new_pages}), report
