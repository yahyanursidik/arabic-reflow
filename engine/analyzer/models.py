"""Typed outputs of the PDF analyzer stage."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Classification(str, Enum):
    NATIVE = "native"
    SCANNED = "scanned"
    HYBRID = "hybrid"


class AnalyzerWarning(BaseModel):
    code: str
    message: str
    page: int | None = Field(default=None, ge=1)


class PageProfile(BaseModel):
    """Per-page signals. Coverage ratios are heuristic (0..1)."""

    page: int = Field(ge=1)
    width: float
    height: float
    rotation: int = 0
    text_chars: int = 0
    arabic_chars: int = 0
    text_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    image_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    image_count: int = 0
    has_text: bool = False
    scanned_like: bool = False
    likely_multicolumn: bool = False


class DocumentProfile(BaseModel):
    """Document-level profile (VIBE-CODING-INSTRUCTIONS.md Task 3 shape plus detail)."""

    page_count: int = Field(ge=1)
    text_layer: bool = False
    image_dominant: bool = False
    arabic_detected: bool = False
    classification: Classification = Classification.NATIVE
    classification_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    encrypted: bool = False
    pages: list[PageProfile] = Field(default_factory=list)
    embedded_fonts: list[str] = Field(default_factory=list)
    likely_multicolumn_pages: list[int] = Field(default_factory=list)
    warnings: list[AnalyzerWarning] = Field(default_factory=list)

    @property
    def scanned_pages(self) -> list[int]:
        return [p.page for p in self.pages if p.scanned_like]

    @property
    def candidate_problem_pages(self) -> list[int]:
        """Pages flagged for review: scanned-like, multi-column, or Arabic-bearing
        pages with very little text (possible extraction trouble)."""
        flagged = set(self.scanned_pages) | set(self.likely_multicolumn_pages)
        for p in self.pages:
            if p.arabic_chars > 0 and p.text_chars < 20:
                flagged.add(p.page)
        return sorted(flagged)
