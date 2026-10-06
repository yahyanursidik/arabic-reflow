"""Integrity scoring, search normalization, and reporting (M3-01/02/06)."""

from __future__ import annotations

from pathlib import Path

from engine.arabic.integrity import (
    LEVEL_GOOD,
    LEVEL_PROBLEM,
    LEVEL_REVIEW,
    inspect_text,
    level_of,
)
from engine.arabic.normalization import search_normalized
from engine.arabic.report import attach_integrity, document_report
from engine.reflowdoc.models import ParagraphBlock, ReflowDocument, SpanNode

VOCALIZED = "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ"
REVERSED_VOCALIZED = "ِتاَّيِّنلاِب ُلاَمْعَأْلا اَمَّنِإ"
PRESENTATION_FORMS = "اﻟﻔﺎﺗﺤﺔ ﺑِﺴْﻢِ ﷲ"
UNUSUAL_MAPPING = "اﻟﺮﺣﻤﺎﻦ اﻟﺮﺣﻴﻢ სტ"  # Georgian-range extraction artifact


# --- Presentation forms (M3-02 via integrity) -----------------------------------


def test_presentation_forms_surfaced() -> None:
    integrity, issues = inspect_text(PRESENTATION_FORMS)
    assert integrity.presentation_forms_detected is True
    assert "PRESENTATION_FORMS_DETECTED" in issues
    assert level_of(integrity.score) in (LEVEL_GOOD, LEVEL_REVIEW)


def test_clean_core_arabic_scores_high() -> None:
    integrity, issues = inspect_text(VOCALIZED)
    assert integrity.presentation_forms_detected is False
    assert integrity.suspicious_spacing is False
    assert integrity.combining_mark_warnings == 0
    assert issues == []
    assert level_of(integrity.score) == LEVEL_GOOD


def test_unusual_characters_lower_score() -> None:
    clean, _ = inspect_text("اﻟﺮﺣﻤﺎﻦ اﻟﺮﺣﻴﻢ")
    dirty, issues = inspect_text(UNUSUAL_MAPPING)
    assert "UNUSUAL_CHARACTERS" in issues
    assert dirty.score < clean.score


def test_suspicious_spacing_penalizes() -> None:
    clean, _ = inspect_text("بسم الله الرحمن الرحيم")
    dirty, issues = inspect_text("ب س م الله الرحمن الرحيم")
    assert "SUSPICIOUS_SPACING" in issues
    assert dirty.suspicious_spacing is True
    assert dirty.score < clean.score


# --- Reversed glyph-order detection (extraction artifact) -----------------------


def test_reversed_arabic_flagged_as_problem() -> None:
    """Glyph-order reversal (text drawn LTR by the producer) must not pass as
    healthy: word-initial harakat are impossible in correct Arabic."""
    integrity, issues = inspect_text(REVERSED_VOCALIZED)
    assert "REVERSED_ORDER_SUSPECTED" in issues
    assert integrity.reversed_order_suspected is True
    assert level_of(integrity.score) == LEVEL_PROBLEM


def test_correct_vocalized_not_flagged_as_reversed() -> None:
    integrity, issues = inspect_text(VOCALIZED)
    assert "REVERSED_ORDER_SUSPECTED" not in issues
    assert integrity.reversed_order_suspected is False


def test_waqf_annotation_after_space_not_reversal() -> None:
    """Qur'anic annotation signs may follow whitespace; only harakat-range
    marks at word start count as reversal evidence."""
    integrity, issues = inspect_text("قَالَ ۖ وَقَالَ ۚ رَسُولُ اللَّهِ ۘ")
    assert "REVERSED_ORDER_SUSPECTED" not in issues
    assert integrity.reversed_order_suspected is False


def test_reversed_fixture_flagged_by_pipeline() -> None:
    import pytest

    fixture = Path(__file__).parent / "fixtures" / "reversed-extraction.pdf"
    if not fixture.exists():
        pytest.skip("reversed-extraction.pdf fixture not generated")
    from engine.arabic.report import document_report
    from engine.pipeline import build_reflowdoc

    result = build_reflowdoc(fixture.read_bytes())
    report = document_report(result.document)
    assert "REVERSED_ORDER_SUSPECTED" in report["issues"]
    assert report["level"] == LEVEL_PROBLEM
    codes = [w.code for w in result.document.warnings]
    assert "LOW_ARABIC_CONFIDENCE" in codes


# --- Search normalization (section 11) ------------------------------------------


def test_search_normalization_strips_harakat_and_folds_forms() -> None:
    normalized = search_normalized(VOCALIZED)
    assert normalized == "انما الاعمال بالنيات"
    folded = search_normalized(PRESENTATION_FORMS)
    assert "ﻓ" not in folded and "ﷲ" not in folded
    assert "الفاتحة" in folded  # NFKC maps ligature/presentation to core


def test_source_text_is_never_replaced() -> None:
    source = PRESENTATION_FORMS
    search_normalized(source)
    assert source == PRESENTATION_FORMS  # untouched


def test_tatweel_removed_in_search_form() -> None:
    assert search_normalized("راﺋــﺪ") == "رائد"


# --- Reporting and wire-in (M3-06) ------------------------------------------------


def _mixed_document() -> ReflowDocument:
    return ReflowDocument(
        metadata={"languages": ["id", "ar"]},
        chapters=[
            {
                "id": "chapter-001",
                "blocks": [
                    {
                        "id": "block-001",
                        "type": "paragraph",
                        "lang": "id",
                        "dir": "ltr",
                        "content": [
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
                    },
                    {
                        "id": "block-002",
                        "type": "paragraph",
                        "lang": "ar",
                        "dir": "rtl",
                        "content": [
                            {"type": "span", "text": PRESENTATION_FORMS,
                             "lang": "ar", "script": "Arabic", "dir": "rtl"},
                        ],
                    },
                    {
                        "id": "block-003",
                        "type": "paragraph",
                        "lang": "id",
                        "dir": "ltr",
                        "content": [
                            {"type": "text", "text": "Kalimat Latin tanpa Arab sama sekali."},
                        ],
                    },
                ],
            }
        ],
    )


def test_attach_integrity_annotates_arabic_blocks_only() -> None:
    doc = _mixed_document()
    attach_integrity(doc)
    blocks = doc.chapters[0].blocks
    assert blocks[0].arabic_integrity is not None
    assert blocks[1].arabic_integrity is not None
    assert blocks[2].arabic_integrity is None
    assert blocks[0].warnings == []  # healthy isolated mixture


def test_low_confidence_blocks_get_document_warning() -> None:
    doc = _mixed_document()
    # make block-002 clearly problematic: isolated-letter spacing plus
    # unusual-mapping characters push the score below the problem threshold
    block = doc.chapters[0].blocks[1]
    block.content[0].text = "ا ل س ل ا م სტ სტ"
    attach_integrity(doc)
    assert "LOW_ARABIC_CONFIDENCE" in block.warnings
    codes = [w.code for w in doc.warnings]
    assert "LOW_ARABIC_CONFIDENCE" in codes
    warning = next(w for w in doc.warnings if w.code == "LOW_ARABIC_CONFIDENCE")
    assert warning.block_ids == ["block-002"]


def test_document_report_aggregates() -> None:
    doc = _mixed_document()
    report = document_report(doc)
    assert report["block_count"] == 2
    assert 0.0 <= report["score"] <= 1.0
    assert 1 in report["page_scores"] or report["page_scores"] == {}
    assert report["low_confidence_block_ids"] == []


def test_block_without_source_still_reported() -> None:
    block = ParagraphBlock(
        id="block-009",
        content=[
            SpanNode(text=VOCALIZED, lang="ar", script="Arabic", dir="rtl"),
        ],
    )
    integrity, issues = inspect_text(block.text)
    assert integrity is not None
    assert issues == []
