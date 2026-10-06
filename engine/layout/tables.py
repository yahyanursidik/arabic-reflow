"""Basic table detection (backlog M6-06; PRD 8.14).

Conservative, ruled-line-gated grid detector: candidate tables are sets of
short, cell-like blocks whose left edges align into >= 2 columns and whose
tops align into >= 2 rows with no conflicting cell assignment, AND whose
region contains vector rule lines (a horizontal rule spanning most of the
grid or a vertical rule spanning most of its height).

The rule gate is what keeps two-column prose (short blocks that align in
columns by construction) out of the table bucket — geometry alone cannot
make that distinction. High-confidence regions become semantic TableBlocks;
low-confidence ones fall back to a rendered page image with a
TABLE_FALLBACK_IMAGE warning (PRD 8.14), never silent guessing.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.extraction.models import RawBlock

CLUSTER_TOLERANCE = 6.0  # pt; x0/y0 alignment tolerance
MIN_ROWS = 2
MIN_COLS = 2
MIN_FILL = 0.6  # fraction of grid positions that must hold a cell
MAX_CELL_CHARS = 80
MAX_BLOCK_LINES = 6  # a block with more lines is prose, not a table row-group
PROSE_LINE_SHARE = 0.85  # a line wider than this share of the grid is prose
RULE_SPAN_SHARE = 0.6  # a rule must span >= 60% of the grid width/height
RULE_TOLERANCE = 3.0  # pt beyond the grid bbox when matching rules
SEMANTIC_CONFIDENCE = 0.75


@dataclass
class TableRegion:
    page: int
    bbox: tuple[float, float, float, float]
    cells: list[tuple[int, int, object]]  # (row, col, line-like), sorted reading order
    n_rows: int
    n_cols: int
    confidence: float


class _Cell:
    """A line acting as a table cell (block number kept for flow exclusion)."""

    __slots__ = ("bbox", "text", "block_number")

    def __init__(self, bbox, text, block_number):
        self.bbox = bbox
        self.text = text
        self.block_number = block_number


def _clusters(values: list[float], tolerance: float) -> list[list[int]]:
    """Group indices whose values sit within tolerance of a running mean."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    clusters: list[list[int]] = []
    current: list[int] = []
    anchor = 0.0
    for index in order:
        if not current:
            current = [index]
            anchor = values[index]
            continue
        if values[index] - anchor <= tolerance:
            current.append(index)
            anchor = sum(values[i] for i in current) / len(current)
        else:
            clusters.append(current)
            current = [index]
            anchor = values[index]
    if current:
        clusters.append(current)
    return clusters


def _cell_like(block: RawBlock) -> bool:
    """A block whose every line could be a cell (short, few lines)."""
    if not block.lines or len(block.lines) > MAX_BLOCK_LINES:
        return False
    return all(line.text.strip() and len(line.text) <= MAX_CELL_CHARS for line in block.lines)


def detect_tables(
    page_number: int,
    blocks: list[RawBlock],
    rule_segments: list[tuple[float, float, float, float]] | None = None,
) -> list[TableRegion]:
    """Find conservative ruled table grids among a page's text blocks.

    Works at LINE level: real-world table rows frequently extract as one
    multi-line block with each cell on its own line, so the grid signal
    lives in line geometry, not block geometry. Two-column prose cannot
    masquerade as a table because the rule gate is mandatory.
    """
    cell_blocks = [b for b in blocks if _cell_like(b)]
    cells = [
        _Cell(line.bbox, line.text, block.number)
        for block in cell_blocks
        for line in block.lines
        if line.text.strip()
    ]
    if len(cells) < MIN_ROWS * MIN_COLS:
        return []

    x0_values = [cell.bbox[0] for cell in cells]
    y0_values = [cell.bbox[1] for cell in cells]
    x_clusters = [c for c in _clusters(x0_values, CLUSTER_TOLERANCE) if len(c) >= MIN_ROWS]
    y_clusters = [c for c in _clusters(y0_values, CLUSTER_TOLERANCE) if len(c) >= MIN_COLS]
    if len(x_clusters) < MIN_COLS or len(y_clusters) < MIN_ROWS:
        return []

    col_of = {}
    for col, cluster in enumerate(x_clusters):
        for index in cluster:
            col_of[index] = col
    row_of = {}
    for row, cluster in enumerate(y_clusters):
        for index in cluster:
            row_of.setdefault(index, row)

    members = [i for i in range(len(cells)) if i in col_of and i in row_of]
    if len(members) < MIN_ROWS * MIN_COLS:
        return []

    bbox = (
        min(cells[i].bbox[0] for i in members),
        min(cells[i].bbox[1] for i in members),
        max(cells[i].bbox[2] for i in members),
        max(cells[i].bbox[3] for i in members),
    )
    # A line spanning nearly the whole grid is prose flowing around the
    # table (a caption, a paragraph whose left edge happens to align), not a
    # cell. Real cells stay well below the grid width.
    grid_width = bbox[2] - bbox[0]
    members = [
        i for i in members
        if cells[i].bbox[2] - cells[i].bbox[0] <= PROSE_LINE_SHARE * grid_width
    ]
    if len(members) < MIN_ROWS * MIN_COLS:
        return []

    # Recompute the bbox from actual cells (the dropped prose line inflated it).
    bbox = (
        min(cells[i].bbox[0] for i in members),
        min(cells[i].bbox[1] for i in members),
        max(cells[i].bbox[2] for i in members),
        max(cells[i].bbox[3] for i in members),
    )

    seen: set[tuple[int, int]] = set()
    grid: list[tuple[int, int, _Cell]] = []
    for index in members:
        position = (row_of[index], col_of[index])
        if position in seen:
            return []  # conflicting assignment: not a clean grid
        seen.add(position)
        grid.append((position[0], position[1], cells[index]))

    n_rows = max(row for row, _, _ in grid) + 1
    n_cols = max(col for _, col, _ in grid) + 1
    fill = len(grid) / (n_rows * n_cols)
    if n_rows < MIN_ROWS or n_cols < MIN_COLS or fill < MIN_FILL:
        return []

    if not _has_rule_support(bbox, rule_segments or []):
        return []

    grid.sort(key=lambda cell: (cell[0], cell[1]))
    confidence = round(min(0.9, fill * 0.9 + 0.1), 3)
    return [
        TableRegion(
            page=page_number,
            bbox=bbox,
            cells=grid,
            n_rows=n_rows,
            n_cols=n_cols,
            confidence=confidence,
        )
    ]


def _has_rule_support(
    bbox: tuple[float, float, float, float],
    rule_segments: list[tuple[float, float, float, float]],
) -> bool:
    """True when a ruled line frames the grid (PRD 8.14 gate)."""
    x0, y0, x1, y1 = bbox
    grid_width = x1 - x0
    grid_height = y1 - y0
    if grid_width <= 0 or grid_height <= 0:
        return False
    for rx0, ry0, rx1, ry1 in rule_segments:
        horizontal_span = min(rx1, x1 + RULE_TOLERANCE) - max(rx0, x0 - RULE_TOLERANCE)
        if (
            ry0 >= y0 - RULE_TOLERANCE
            and ry1 <= y1 + RULE_TOLERANCE
            and horizontal_span >= RULE_SPAN_SHARE * grid_width
        ):
            return True
        vertical_span = min(ry1, y1 + RULE_TOLERANCE) - max(ry0, y0 - RULE_TOLERANCE)
        if (
            rx0 >= x0 - RULE_TOLERANCE
            and rx1 <= x1 + RULE_TOLERANCE
            and vertical_span >= RULE_SPAN_SHARE * grid_height
        ):
            return True
    return False


