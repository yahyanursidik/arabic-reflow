"""Raw internal model mirroring PDF page primitives.

This model intentionally contains no semantics: no paragraphs, no reading
order, no language labels. Script/direction fields are attached by the
detection stage (engine.arabic.detector), not by the extractor.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from engine.reflowdoc.models import Direction, ScriptClass


class RawSpan(BaseModel):
    text: str
    font: str
    size: float
    flags: int = 0
    color: int = 0
    bbox: tuple[float, float, float, float]
    # Attached by script detection, not by the extractor:
    script: ScriptClass | None = None
    dir: Direction | None = None


class RawLine(BaseModel):
    bbox: tuple[float, float, float, float]
    spans: list[RawSpan] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)


class RawBlock(BaseModel):
    number: int
    type: str = Field(description="'text' or 'image' as reported by PyMuPDF")
    bbox: tuple[float, float, float, float]
    lines: list[RawLine] = Field(default_factory=list)
    # Attached by script detection:
    script: ScriptClass | None = None
    dir: Direction | None = None

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


class RawImage(BaseModel):
    bbox: tuple[float, float, float, float]
    width: int = Field(description="Pixel width")
    height: int = Field(description="Pixel height")


class RawPage(BaseModel):
    page: int = Field(ge=1, description="1-based page number")
    width: float
    height: float
    rotation: int = 0
    blocks: list[RawBlock] = Field(default_factory=list)
    images: list[RawImage] = Field(default_factory=list)


class RawDocument(BaseModel):
    source_filename: str | None = None
    page_count: int = Field(ge=0)
    pages: list[RawPage] = Field(default_factory=list)
