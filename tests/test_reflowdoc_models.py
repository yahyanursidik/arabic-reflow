"""ReflowDoc model contract tests (backlog M0-03)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from engine.reflowdoc.models import (
    Chapter,
    Direction,
    FootnoteBlock,
    ParagraphBlock,
    QuoteBlock,
    ReflowDocument,
    ReflowWarning,
    SCHEMA_VERSION,
    SpanNode,
    TextNode,
    new_block_id,
    new_document,
)
from engine.reflowdoc.schema import json_schema


def spec_paragraph() -> ParagraphBlock:
    """The mixed-direction paragraph from REFLOWDOC-SPEC.md section 7."""
    return ParagraphBlock(
        id="block-001",
        source={"page": 3, "bbox": [72, 120, 500, 180]},
        lang="id",
        script="Latin",
        dir="ltr",
        confidence=0.98,
        content=[
            {"type": "text", "text": "Hadits ini diriwayatkan dari "},
            {
                "type": "span",
                "text": "أبي هريرة رضي الله عنه",
                "lang": "ar",
                "script": "Arabic",
                "dir": "rtl",
            },
            {"type": "text", "text": " dalam Shahih Muslim."},
        ],
    )


def test_schema_version_is_pinned() -> None:
    assert ReflowDocument().schema_version == SCHEMA_VERSION == "0.1"


def test_new_document_has_uuid_and_source_filename() -> None:
    doc = new_document("book.pdf")
    assert len(doc.document_id) == 36
    assert doc.metadata.source_filename == "book.pdf"
    assert doc.chapters == []


def test_spec_paragraph_parses_with_mixed_spans() -> None:
    block = spec_paragraph()
    assert block.content[1] == SpanNode(
        type="span",
        text="أبي هريرة رضي الله عنه",
        lang="ar",
        script="Arabic",
        dir=Direction.RTL,
    )
    assert block.content[0].type == "text"


def test_arabic_quote_block_from_spec() -> None:
    block = QuoteBlock(
        id="block-002",
        subtype="arabic",
        lang="ar",
        script="Arabic",
        dir="rtl",
        text="إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ",
        confidence=0.99,
    )
    assert block.subtype == "arabic"
    assert block.dir is Direction.RTL


def test_footnote_may_contain_nested_blocks() -> None:
    footnote = FootnoteBlock(
        id="fn-12",
        marker="12",
        blocks=[
            {
                "id": "block-050",
                "type": "paragraph",
                "content": [{"type": "text", "text": "Shahih Muslim, hadits 16."}],
            }
        ],
    )
    assert footnote.blocks[0].id == "block-050"


def test_unknown_block_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ParagraphBlock.model_validate({"id": "block-001", "type": "poem", "content": []})


def test_invalid_direction_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SpanNode(type="span", text="halo", lang="id", dir="down")


def test_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        ParagraphBlock(id="b1", confidence=1.5, content=[{"type": "text", "text": "x"}])
    with pytest.raises(ValidationError):
        ParagraphBlock(id="b1", confidence=-0.1, content=[{"type": "text", "text": "x"}])


def test_transformation_provenance_fields() -> None:
    node = TextNode(
        text="pembelajaran",
        source_text="pembe-\nlajaran",
        transformations=["dehyphenation"],
    )
    assert node.source_text == "pembe-\nlajaran"
    assert node.transformations == ["dehyphenation"]


def test_json_round_trip_preserves_everything() -> None:
    doc = new_document("book.pdf")
    doc.metadata.languages = ["id", "ar"]
    doc.chapters = [
        Chapter(id="chapter-001", title="Pendahuluan", level=1, blocks=[spec_paragraph()])
    ]
    doc.warnings = [
        ReflowWarning(
            code="READING_ORDER_UNCERTAIN",
            severity="warning",
            message="Column boundary is ambiguous.",
            source_page=14,
            block_ids=["block-001"],
        )
    ]
    revived = ReflowDocument.model_validate_json(doc.model_dump_json())
    assert revived == doc
    assert revived.chapters[0].blocks[0].content[1].lang == "ar"


def test_block_id_helper_is_stable() -> None:
    assert new_block_id(1) == "block-001"
    assert new_block_id(42) == "block-042"


def test_json_schema_is_exportable() -> None:
    schema = json_schema()
    assert schema["$schema"].startswith("https://json-schema.org/")
    assert "chapters" in schema["properties"]
    assert "ReflowDocument" in schema["title"] or "title" in schema
