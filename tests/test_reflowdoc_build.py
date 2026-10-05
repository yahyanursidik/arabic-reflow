"""End-to-end pipeline tests: PDF -> ReflowDoc (Milestone 2 acceptance)."""

from __future__ import annotations

import pytest

from engine.arabic.unicode import count_harakat, is_arabic_letter
from engine.pipeline import build_reflowdoc
from engine.reflowdoc.models import HeadingBlock, ParagraphBlock, SpanNode


def _blocks_of(document):
    return [b for chapter in document.chapters for b in chapter.blocks]


def test_indonesian_native_build(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "indonesian-native.pdf")
    doc = result.document
    assert doc.schema_version == "0.1"
    assert doc.metadata.source_filename == "indonesian-native.pdf"

    assert len(doc.chapters) == 1
    chapter = doc.chapters[0]
    assert chapter.title is None  # ungrouped chapter until chapter detection
    blocks = chapter.blocks
    assert [type(b).__name__ for b in blocks] == [
        "HeadingBlock", "ParagraphBlock", "ParagraphBlock", "ParagraphBlock",
    ]

    heading = blocks[0]
    assert isinstance(heading, HeadingBlock)
    assert heading.text == "Pendahuluan"
    assert heading.level == 1

    first = blocks[1]
    assert first.text.startswith("Kitab ini mengumpulkan hadits-hadits pilihan")
    assert first.text.endswith("tanpa kesulitan.")
    assert first.lang == "id"
    assert first.dir == "ltr"
    assert first.source.page == 1
    assert first.modified_by_user is False

    # The printed page number must not appear as content.
    assert all(b.text.strip() != "1" for b in blocks)
    assert any(w.code == "PAGE_NUMBERS_REMOVED" for w in doc.warnings)
    assert doc.metadata.languages == ["id"]
    assert result.layout.page_number_map == {1: 1}


def test_mixed_fixture_produces_arabic_span_nodes(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "mixed-id-ar.pdf")
    blocks = _blocks_of(result.document)
    assert isinstance(blocks[0], HeadingBlock)
    assert blocks[0].text == "Bab Pertama: Niat"
    assert blocks[0].level == 1

    inline = next(b for b in blocks if isinstance(b, ParagraphBlock)
                  and "Hadits ini diriwayatkan dari" in b.text)
    assert inline.dir == "ltr"
    span = next(n for n in inline.content if isinstance(n, SpanNode))
    assert span.lang == "ar"
    assert span.script.value == "Arabic"
    assert span.dir == "rtl"
    assert span.text.strip() == "أﺑﻲ ﻫࣱﻳﺮة رﺿﻲ ﷲ ﻋﻨﻪ"
    text_before = next(n for n in inline.content if n is not span
                       and n.text.strip().endswith("dari"))
    assert isinstance(text_before, SpanNode) is False

    assert result.document.metadata.languages == ["id", "ar"]


def test_arabic_fixture_blocks_are_rtl_and_unmodified(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "arabic-native.pdf")
    blocks = _blocks_of(result.document)
    assert isinstance(blocks[0], HeadingBlock)
    assert blocks[0].text == "اﻟﻔﺎﺗﺤﺔ"

    paragraphs = [b for b in blocks if isinstance(b, ParagraphBlock)]
    assert len(paragraphs) == 2
    main = paragraphs[0]
    assert main.lang == "ar"
    assert main.dir == "rtl"
    assert main.text == (
        "اﻟﺤﻤﺪ ﻟﻠﻪ رب اﻟﻌﺎﻟﻤﻴﻦ، واﻟﺼﻼة واﻟﺴﻼم ﻋﻠﻰ أﺷﺮف اﻷﻧﺒﻴﺎء واﻟﻤﺮﺳﻠﻴﻦ، "
        "ﻧﺎﺑﻌﺎ إﻟﻰ ﻳﻮم اﻟﺪﻳﻦ، أﻣﺎ ﺑﻌﺪ:"
    )
    # Presentation forms pass through without normalization (M3 will decide).
    assert any(is_arabic_letter(ch) for ch in main.text)


def test_vocalized_fixture_keeps_harakat_through_pipeline(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "arabic-vocalized.pdf")
    blocks = _blocks_of(result.document)
    paragraphs = [b for b in blocks if isinstance(b, ParagraphBlock)]
    assert len(paragraphs) == 3
    assert sum(count_harakat(p.text) for p in paragraphs) >= 60
    assert all(p.dir == "rtl" and p.lang == "ar" for p in paragraphs)


def test_two_column_reading_order_in_reflowdoc(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "two-column.pdf")
    blocks = _blocks_of(result.document)
    texts = [b.text for b in blocks]

    def pos(needle: str) -> int:
        return next(i for i, t in enumerate(texts) if needle in t)

    assert texts[0].startswith("Dua Kolom")
    assert pos("Kolom kiri bagian 1") < pos("Kolom kanan bagian 3")
    assert not any(w.code == "READING_ORDER_UNCERTAIN" for w in result.document.warnings)
    assert result.order.confidence[1] == 0.85


def test_scanned_fixture_yields_empty_document(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "scanned.pdf")
    assert _blocks_of(result.document) == []
    assert result.document.chapters[0].blocks == []


def test_hybrid_fixture_only_native_page_contributes(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "hybrid.pdf")
    blocks = _blocks_of(result.document)
    assert blocks
    assert {b.source.page for b in blocks} == {1}
    assert any(isinstance(b, HeadingBlock) and b.text == "Halaman Teks Asli"
               for b in blocks)


def test_block_ids_are_sequential_and_unique(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "mixed-id-ar.pdf")
    ids = [b.id for b in _blocks_of(result.document)]
    assert ids == [f"block-{i:03d}" for i in range(1, len(ids) + 1)]


def test_build_is_deterministic(fixtures_dir) -> None:
    a = build_reflowdoc(fixtures_dir / "indonesian-native.pdf").document
    b = build_reflowdoc(fixtures_dir / "indonesian-native.pdf").document
    assert a.chapters == b.chapters
    assert a.metadata == b.metadata
    assert a.warnings == b.warnings


def test_serializable_to_json(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "mixed-id-ar.pdf")
    payload = result.document.model_dump_json()
    assert "أﺑﻲ ﻫࣱﻳﺮة رﺿﻲ ﷲ ﻋﻨﻪ" in payload
