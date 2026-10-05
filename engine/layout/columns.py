"""Column gutter detection shared by the analyzer and the reading-order engine.

Returns the x position of a vertical gutter that splits text blocks into two
non-trivial sides with almost nothing crossing it, or None. The real layout
engine (M6-01) replaces this probe.
"""

from __future__ import annotations

# Candidate gutter positions as fractions of the page width.
GUTTER_FRACTIONS = (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65)
GUTTER_TOLERANCE = 3.0  # pt


def find_gutter(
    bboxes: list[tuple[float, float, float, float]], width: float
) -> float | None:
    """Return a gutter x position, or None when the page reads as one column."""
    if len(bboxes) < 4:
        return None

    for fraction in GUTTER_FRACTIONS:
        x = width * fraction
        left = [b for b in bboxes if b[2] < x - GUTTER_TOLERANCE]
        right = [b for b in bboxes if b[0] > x + GUTTER_TOLERANCE]
        crossing = len(bboxes) - len(left) - len(right)
        if len(left) >= 2 and len(right) >= 2 and crossing <= max(1, len(bboxes) // 10):
            return x
    return None
