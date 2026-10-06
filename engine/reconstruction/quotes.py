"""Block-quote detection (PRD 8.10 structural reconstruction).

Conservative by design: a draft becomes a quote only when it is a single,
short, self-contained block indented on both sides of a single-column page —
the classic print block-quote silhouette. Multi-column pages are excluded
(column members always look indented).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from engine.reconstruction.paragraphs import ParagraphDraft

MAX_QUOTE_CHARS = 450
MIN_LEFT_INDENT = 18.0  # pt
LEFT_INDENT_SHARE = 0.06  # of the page reference width
RIGHT_INDENT_SHARE = 0.03
QUOTE_CONFIDENCE = 0.75


def is_quote_draft(
    draft: "ParagraphDraft",
    *,
    page_x0: float,
    page_x1: float,
    ref_width: float,
    single_column: bool,
    is_caption: bool = False,
) -> bool:
    """True when the draft has the geometry of a print block quote."""
    if not single_column or ref_width <= 0 or is_caption:
        return False
    if draft.is_heading or draft.footnote_marker is not None:
        return False
    if draft.merged_block_count > 1:
        return False
    if len(draft.text) > MAX_QUOTE_CHARS or not draft.text.strip():
        return False
    left_indent = draft.bbox[0] - page_x0
    right_indent = page_x1 - draft.bbox[2]
    if left_indent < max(MIN_LEFT_INDENT, LEFT_INDENT_SHARE * ref_width):
        return False
    if right_indent < RIGHT_INDENT_SHARE * ref_width:
        return False
    return True
