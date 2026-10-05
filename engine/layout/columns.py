"""Column gutter detection shared by the analyzer and the reading-order engine.

`find_gutter` returns a single gutter (two-column layout); `find_gutters`
recursively splits sub-regions to support N-column layouts (M6-01). The
recursion replaces a full projection-profile analysis while keeping the same
verification rule: a gutter only counts when it splits blocks into two
non-trivial sides with almost nothing crossing it.
"""

from __future__ import annotations

# Candidate gutter positions as fractions of the region width.
GUTTER_FRACTIONS = (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65)
GUTTER_TOLERANCE = 3.0  # pt
MAX_COLUMNS = 4  # sanity cap for recursion


def _verify(bboxes: list[tuple[float, float, float, float]], x: float) -> bool:
    left = [b for b in bboxes if b[2] < x - GUTTER_TOLERANCE]
    right = [b for b in bboxes if b[0] > x + GUTTER_TOLERANCE]
    crossing = len(bboxes) - len(left) - len(right)
    return len(left) >= 2 and len(right) >= 2 and crossing <= max(1, len(bboxes) // 10)


def find_gutter(
    bboxes: list[tuple[float, float, float, float]], width: float
) -> float | None:
    """Return a gutter x position, or None when the page reads as one column."""
    if len(bboxes) < 4:
        return None

    for fraction in GUTTER_FRACTIONS:
        x = width * fraction
        if _verify(bboxes, x):
            return x
    return None


def find_gutters(
    bboxes: list[tuple[float, float, float, float]],
    region_left: float,
    region_right: float,
    depth: int = 0,
) -> list[float]:
    """Detect all gutters inside [region_left, region_right] (M6-01).

    Returns sorted gutter x positions. Recursion stops when a side cannot be
    split further, when too few blocks remain, or at MAX_COLUMNS depth.
    """
    inside = [
        b for b in bboxes
        if b[0] >= region_left - GUTTER_TOLERANCE and b[2] <= region_right + GUTTER_TOLERANCE
    ]
    if depth >= MAX_COLUMNS or len(inside) < 4:
        return []

    region_width = region_right - region_left
    for fraction in GUTTER_FRACTIONS:
        x = region_left + region_width * fraction
        if x <= region_left + GUTTER_TOLERANCE or x >= region_right - GUTTER_TOLERANCE:
            continue
        if not _verify(inside, x):
            continue
        left_gutters = find_gutters(bboxes, region_left, x, depth + 1)
        right_gutters = find_gutters(bboxes, x, region_right, depth + 1)
        return sorted(left_gutters + [x] + right_gutters)
    return []
