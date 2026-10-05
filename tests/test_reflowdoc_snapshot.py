"""ReflowDoc serialization snapshot (backlog M0-03).

The stored snapshot is the approved JSON rendering of a representative mixed
Arabic-Latin ReflowDoc. It changes only with an intentional schema/behavior
change: update it by running pytest with REFLOW_UPDATE_SNAPSHOT=1 and reviewing
the diff.
"""

from __future__ import annotations

import json
import os

import pytest

from engine.reflowdoc.models import (
    Chapter,
    DocumentMetadata,
    ParagraphBlock,
    QuoteBlock,
    ReflowDocument,
    ReflowWarning,
    Resource,
    SourceRef,
    SpanNode,
    TextNode,
)

SNAPSHOT_NAME = "reflowdoc-v0.1-sample.json"


def sample_document() -> ReflowDocument:
    doc = ReflowDocument(
        document_id="00000000-0000-0000-0000-000000000001",
        metadata=DocumentMetadata(
            title="Shahih Muslim Pilihan",
            author=["Imam Muslim"],
            publisher=None,
            languages=["id", "ar"],
            description=None,
            identifier=None,
            source_filename="sample.pdf",
        ),
        resources=[
            Resource(id="img-001", kind="image", media_type="image/png", source_page=2),
        ],
        warnings=[
            ReflowWarning(
                code="READING_ORDER_UNCERTAIN",
                severity="warning",
                message="Column boundary is ambiguous.",
                source_page=14,
                block_ids=["block-012"],
            ),
        ],
    )
    doc.chapters = [
        Chapter(
            id="chapter-001",
            title="Pendahuluan",
            level=1,
            blocks=[
                ParagraphBlock(
                    id="block-001",
                    source=SourceRef(page=3, bbox=[72.0, 120.0, 500.0, 180.0]),
                    lang="id",
                    script="Latin",
                    dir="ltr",
                    confidence=0.98,
                    content=[
                        TextNode(text="Hadits ini diriwayatkan dari "),
                        SpanNode(
                            text="أبي هريرة رضي الله عنه",
                            lang="ar",
                            script="Arabic",
                            dir="rtl",
                        ),
                        TextNode(text=" dalam Shahih Muslim."),
                    ],
                ),
                QuoteBlock(
                    id="block-002",
                    subtype="arabic",
                    lang="ar",
                    script="Arabic",
                    dir="rtl",
                    text="إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ",
                    confidence=0.99,
                ),
            ],
        ),
    ]
    return doc


def test_reflowdoc_serialization_snapshot(snapshot_path=None) -> None:
    from tests.conftest import SNAPSHOTS_DIR

    path = SNAPSHOTS_DIR / SNAPSHOT_NAME
    rendered = json.dumps(sample_document().model_dump(), indent=2, ensure_ascii=False) + "\n"

    if os.environ.get("REFLOW_UPDATE_SNAPSHOT"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, "utf-8")

    if not path.exists():
        pytest.fail(f"snapshot missing: {path}; run with REFLOW_UPDATE_SNAPSHOT=1 to create")

    stored = path.read_text("utf-8")
    assert rendered == stored, (
        "ReflowDoc serialization changed vs approved snapshot; if the schema change is "
        "intentional, re-run with REFLOW_UPDATE_SNAPSHOT=1 and review the diff"
    )
