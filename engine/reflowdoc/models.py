"""Typed ReflowDoc models (schema v0.1, per REFLOWDOC-SPEC.md).

ReflowDoc answers "what is this content and how should it be read?" — never
"at which exact PDF pixel should this content appear?".
"""

from __future__ import annotations

import base64
import uuid
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

SCHEMA_VERSION = "0.1"


class Direction(str, Enum):
    """Inline base direction for blocks and spans."""

    LTR = "ltr"
    RTL = "rtl"


class ScriptClass(str, Enum):
    """Script classification. Script matters more than natural language (PRD 8.6)."""

    ARABIC = "Arabic"
    LATIN = "Latin"
    MIXED = "Mixed"
    NUMERIC = "Numeric"
    NEUTRAL = "Neutral"


class SourceRef(BaseModel):
    """Extraction provenance, kept for diagnostics only.

    Coordinates are PDF points and must never be used by renderers for layout.
    """

    page: int = Field(ge=1, description="1-based source page number")
    bbox: list[float] | None = Field(
        default=None, description="[x0, y0, x1, y1] in PDF points, diagnostics only"
    )


class ArabicIntegrity(BaseModel):
    """Arabic diagnostic metadata attached to blocks/spans when applicable."""

    score: float = Field(ge=0.0, le=1.0)
    presentation_forms_detected: bool = False
    suspicious_spacing: bool = False
    combining_mark_warnings: int = 0
    bidi_warning: bool = False


class DocumentMetadata(BaseModel):
    title: str = ""
    author: list[str] = Field(default_factory=list)
    publisher: str | None = None
    languages: list[str] = Field(
        default_factory=list,
        description="BCP-47 style labels; minimum supported: id, ar, en, unknown",
    )
    description: str | None = None
    identifier: str | None = None
    source_filename: str | None = None


class Resource(BaseModel):
    """A binary resource referenced by blocks (image, font, table fallback)."""

    id: str
    kind: str = Field(description="e.g. 'image' or 'font'")
    media_type: str | None = None
    filename: str | None = None
    source_page: int | None = Field(default=None, ge=1)
    content: bytes | None = Field(
        default=None,
        description="Encoded payload (base64 in JSON). MVP: images are carried "
        "inline so a ReflowDoc JSON is self-contained.",
    )

    @field_serializer("content", when_used="json")
    def _serialize_content(self, value):
        return base64.b64encode(value).decode("ascii") if value is not None else None

    @field_validator("content", mode="before")
    @classmethod
    def _load_content(cls, value):
        if isinstance(value, str):
            return base64.b64decode(value)
        return value


class ReflowWarning(BaseModel):
    """Explicit, non-silent uncertainty (ARCHITECTURE.md section 10)."""

    code: str = Field(
        description="Warning code, e.g. READING_ORDER_UNCERTAIN, LOW_ARABIC_CONFIDENCE"
    )
    severity: Literal["info", "warning", "error"] = "warning"
    message: str
    source_page: int | None = Field(default=None, ge=1)
    block_ids: list[str] = Field(default_factory=list)


# --- Inline content -----------------------------------------------------------


class TextNode(BaseModel):
    """A run of text in the block's primary language/direction."""

    type: Literal["text"] = "text"
    text: str
    source_text: str | None = Field(
        default=None,
        description="Original extraction when a transformation was applied",
    )
    transformations: list[str] = Field(
        default_factory=list,
        description="Applied transformations, e.g. ['dehyphenation']",
    )


class SpanNode(BaseModel):
    """An inline span with its own language/script/direction (mixed-direction text)."""

    type: Literal["span"] = "span"
    text: str
    lang: str = "unknown"
    script: ScriptClass = ScriptClass.NEUTRAL
    dir: Direction | None = None
    source_text: str | None = None
    transformations: list[str] = Field(default_factory=list)
    arabic_integrity: ArabicIntegrity | None = None


ContentNode = Annotated[Union[TextNode, SpanNode], Field(discriminator="type")]


# --- Blocks -------------------------------------------------------------------


class BlockBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    source: SourceRef | None = None
    lang: str = "unknown"
    script: ScriptClass | None = None
    dir: Direction | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    modified_by_user: bool = Field(
        default=False,
        description="True only when a human explicitly edited the content",
    )
    arabic_integrity: ArabicIntegrity | None = Field(
        default=None,
        description="Arabic diagnostic metadata when the block carries Arabic",
    )


class HeadingBlock(BlockBase):
    type: Literal["heading"] = "heading"
    level: int = Field(default=1, ge=1, le=6)
    text: str
    source_text: str | None = None
    transformations: list[str] = Field(default_factory=list)


class ParagraphBlock(BlockBase):
    type: Literal["paragraph"] = "paragraph"
    content: list[ContentNode] = Field(min_length=1)

    @property
    def text(self) -> str:
        """Convenience view of the paragraph's text (content nodes joined)."""
        return "".join(node.text for node in self.content)


class QuoteBlock(BlockBase):
    type: Literal["quote"] = "quote"
    subtype: str | None = Field(
        default=None, description="e.g. 'arabic' for Arabic quote blocks"
    )
    text: str
    source_text: str | None = None
    transformations: list[str] = Field(default_factory=list)


class ListItem(BaseModel):
    blocks: list["Block"] = Field(default_factory=list)


class ListBlock(BlockBase):
    type: Literal["list"] = "list"
    ordered: bool = False
    items: list[ListItem] = Field(default_factory=list)


class ImageBlock(BlockBase):
    type: Literal["image"] = "image"
    resource_id: str
    alt: str | None = None
    caption_block_id: str | None = None


class FootnoteBlock(BlockBase):
    type: Literal["footnote"] = "footnote"
    marker: str
    blocks: list["Block"] = Field(default_factory=list)


class TableCell(BaseModel):
    text: str
    lang: str | None = None
    dir: Direction | None = None


class TableBlock(BlockBase):
    type: Literal["table"] = "table"
    rows: list[list[TableCell]] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    fallback_resource_id: str | None = None


class PageBreakBlock(BlockBase):
    type: Literal["page_break"] = "page_break"


Block = Annotated[
    Union[
        HeadingBlock,
        ParagraphBlock,
        QuoteBlock,
        ListBlock,
        ImageBlock,
        FootnoteBlock,
        TableBlock,
        PageBreakBlock,
    ],
    Field(discriminator="type"),
]


class Chapter(BaseModel):
    id: str
    title: str | None = Field(
        default=None,
        description="None while chapter detection is incomplete (ungrouped chapter)",
    )
    level: int = Field(default=1, ge=1)
    blocks: list[Block] = Field(default_factory=list)


class ReflowDocument(BaseModel):
    schema_version: str = SCHEMA_VERSION
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    chapters: list[Chapter] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    warnings: list[ReflowWarning] = Field(default_factory=list)


ListItem.model_rebuild()
FootnoteBlock.model_rebuild()


def new_document(source_filename: str | None = None) -> ReflowDocument:
    """Create an empty ReflowDoc with a fresh document id."""
    return ReflowDocument(
        metadata=DocumentMetadata(source_filename=source_filename),
    )


def new_block_id(sequence: int) -> str:
    """Deterministic block ids keep snapshots stable across runs."""
    return f"block-{sequence:03d}"
