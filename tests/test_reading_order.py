"""Reading-order tests (backlog M2-01).

Per the testing rules, reading-order changes are tested on a single-column
page, a multi-column page, and a footnote page.
"""

from __future__ import annotations

from engine.analyzer.models import Classification, DocumentProfile, PageProfile
from engine.extraction.extractor import extract
from engine.extraction.models import RawBlock, RawDocument, RawLine, RawPage, RawSpan
from engine.layout.furniture import detect_layout
from engine.layout.reading_order import reconstruct_reading_order


def _ordered_texts(pdf) -> list[str]:
    raw = extract(pdf)
    raw, _ = detect_layout(raw)
    ordered, report = reconstruct_reading_order(raw)
    return (
        [b.text for b in ordered.pages[0].blocks],
        report,
    )


def test_single_column_top_to_bottom(fixtures_dir) -> None:
    texts, report = _ordered_texts(fixtures_dir / "indonesian-native.pdf")
    assert texts[0].startswith("Pendahuluan")
    intro = texts.index(next(t for t in texts if "Kitab ini mengumpulkan" in t))
    body = texts.index(next(t for t in texts if "Para ulama sepakat" in t))
    closing = texts.index(next(t for t in texts if "Demikian uraian" in t))
    assert intro < body < closing
    assert report.confidence[1] == 0.95
    assert report.uncertain_pages == []


def test_multi_column_left_then_right(fixtures_dir) -> None:
    texts, report = _ordered_texts(fixtures_dir / "two-column.pdf")
    assert texts[0].startswith("Dua Kolom")

    def pos(needle: str) -> int:
        return next(i for i, t in enumerate(texts) if needle in t)

    assert pos("Kolom kiri bagian 1") < pos("Kolom kiri bagian 2") < pos("Kolom kiri bagian 3")
    assert pos("Kolom kanan bagian 1") < pos("Kolom kanan bagian 2") < pos("Kolom kanan bagian 3")
    assert pos("Kolom kiri bagian 1") < pos("Kolom kanan bagian 1")
    assert report.confidence[1] == 0.85
    assert report.uncertain_pages == []


def test_footnote_page_body_before_notes(fixtures_dir) -> None:
    texts, report = _ordered_texts(fixtures_dir / "footnote-heavy.pdf")
    body_positions = [i for i, t in enumerate(texts) if "Para ulama sepakat" in t]
    note_positions = [i for i, t in enumerate(texts) if "al-Bukhari" in t]
    assert body_positions and note_positions
    assert max(body_positions) < min(note_positions)
    assert report.uncertain_pages == []


def test_flagged_page_without_gutter_is_uncertain() -> None:
    """Analyzer flags multi-column, no gutter found -> explicit uncertainty."""
    blocks = [
        RawBlock(number=1, type="text", bbox=(60, 100, 500, 130),
                 lines=[RawLine(bbox=(60, 100, 500, 130),
                                spans=[RawSpan(text="Satu", font="H", size=11,
                                               bbox=(60, 100, 500, 130))])]),
        RawBlock(number=2, type="text", bbox=(60, 150, 500, 180),
                 lines=[RawLine(bbox=(60, 150, 500, 180),
                                spans=[RawSpan(text="Dua", font="H", size=11,
                                               bbox=(60, 150, 500, 180))])]),
        RawBlock(number=3, type="text", bbox=(60, 200, 500, 230),
                 lines=[RawLine(bbox=(60, 200, 500, 230),
                                spans=[RawSpan(text="Tiga", font="H", size=11,
                                               bbox=(60, 200, 500, 230))])]),
    ]
    raw = RawDocument(page_count=1, pages=[RawPage(page=1, width=595, height=842,
                                                   blocks=blocks)])
    profile = DocumentProfile(
        page_count=1,
        classification=Classification.NATIVE,
        pages=[PageProfile(page=1, width=595, height=842)],
        likely_multicolumn_pages=[1],
    )
    _, report = reconstruct_reading_order(raw, profile)
    assert report.uncertain_pages == [1]
    assert report.confidence[1] == 0.5


def test_input_document_is_not_mutated(fixtures_dir) -> None:
    raw = extract(fixtures_dir / "two-column.pdf")
    before = [b.number for b in raw.pages[0].blocks]
    reconstruct_reading_order(raw)
    assert [b.number for b in raw.pages[0].blocks] == before
