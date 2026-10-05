"""Layout-stage typed outputs: furniture removal and column model records."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FurnitureItem(BaseModel):
    """A removed header/footer/page-number block, kept for provenance."""

    page: int = Field(ge=1)
    block_number: int
    kind: Literal["header", "footer", "page_number"]
    text: str
    printed_page_number: int | None = None


class LayoutReport(BaseModel):
    """Result of the layout/zoning stage (detect_layout)."""

    removed_furniture: list[FurnitureItem] = Field(default_factory=list)
    # PDF page (1-based) -> printed page number. "Preserve page provenance
    # internally" (M2-06): the mapping survives even though the block is gone.
    page_number_map: dict[int, int] = Field(default_factory=dict)
    # Page -> first detected column gutter x position.
    gutters: dict[int, float] = Field(default_factory=dict)
    # Page -> all detected gutters (M6-01, N-column layouts).
    all_gutters: dict[int, list[float]] = Field(default_factory=dict)


class OrderReport(BaseModel):
    """Result of the reading-order stage (M2-01)."""

    uncertain_pages: list[int] = Field(default_factory=list)
    confidence: dict[int, float] = Field(default_factory=dict)
