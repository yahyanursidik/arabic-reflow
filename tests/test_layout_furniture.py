"""Header/footer and page-number removal tests (backlog M2-05, M2-06)."""

from __future__ import annotations

from engine.extraction.extractor import extract
from engine.extraction.models import RawBlock, RawDocument, RawLine, RawPage, RawSpan
from engine.layout.furniture import detect_layout


def make_block(number: int, bbox: tuple[float, float, float, float], text: str,
               size: float = 11.0) -> RawBlock:
    return RawBlock(
        number=number,
        type="text",
        bbox=bbox,
        lines=[RawLine(bbox=bbox, spans=[RawSpan(text=text, font="Helv", size=size, bbox=bbox)])],
    )


def make_page(number: int, blocks: list[RawBlock], height: float = 842.0) -> RawPage:
    return RawPage(page=number, width=595.0, height=height, blocks=blocks)


def body_block(number: int) -> RawBlock:
    return make_block(
        number, (60, 200, 535, 600),
        "Isi utama dokumen berada di tengah halaman dan tidak boleh dihapus "
        "sebagai catatan kaki atau header.",
    )


def test_repeated_header_and_page_numbers_removed() -> None:
    pages = []
    for i in range(1, 4):
        pages.append(
            make_page(
                i,
                [
                    make_block(1, (60, 20, 535, 50), "Kitab Reflow Edisi Revisi"),
                    body_block(2),
                    make_block(3, (250, 800, 345, 820), str(i)),
                ],
            )
        )
    raw = RawDocument(page_count=3, pages=pages)
    cleaned, report = detect_layout(raw)

    assert len(report.removed_furniture) == 6
    kinds = sorted(item.kind for item in report.removed_furniture)
    assert kinds == ["header"] * 3 + ["page_number"] * 3
    assert report.page_number_map == {1: 1, 2: 2, 3: 3}
    for page in cleaned.pages:
        assert [b.text for b in page.blocks] == [body_block(0).text]


def test_unique_top_block_is_kept() -> None:
    raw = RawDocument(page_count=1, pages=[make_page(1, [
        make_block(1, (60, 60, 535, 100), "Pendahuluan", size=18),
        body_block(2),
    ])])
    cleaned, report = detect_layout(raw)
    assert report.removed_furniture == []
    assert len(cleaned.pages[0].blocks) == 2


def test_numeric_top_block_is_page_number() -> None:
    raw = RawDocument(page_count=1, pages=[make_page(1, [
        make_block(1, (250, 20, 345, 40), "5"),
        body_block(2),
    ])])
    _, report = detect_layout(raw)
    assert len(report.removed_furniture) == 1
    item = report.removed_furniture[0]
    assert item.kind == "page_number"
    assert item.printed_page_number == 5
    assert report.page_number_map == {1: 5}


def test_page_number_with_decoration() -> None:
    raw = RawDocument(page_count=1, pages=[make_page(1, [
        make_block(1, (250, 800, 345, 820), "- 7 -"),
        body_block(2),
    ])])
    _, report = detect_layout(raw)
    assert report.page_number_map == {1: 7}


def test_long_top_block_is_not_furniture() -> None:
    long_text = "Ini adalah sebuah blok panjang di bagian atas halaman yang " * 3
    raw = RawDocument(page_count=1, pages=[make_page(1, [
        make_block(1, (60, 20, 535, 60), long_text),
        body_block(2),
    ])])
    _, report = detect_layout(raw)
    assert report.removed_furniture == []


def test_fixture_page_number_removed_and_footnotes_survive(fixtures_dir) -> None:
    raw = extract(fixtures_dir / "indonesian-native.pdf")
    cleaned, report = detect_layout(raw)
    assert report.page_number_map == {1: 1}
    remaining_text = "\n".join(b.text for b in cleaned.pages[0].blocks)
    assert remaining_text.strip().split("\n")[-1].strip() != "1"
    assert "Demikian uraian singkat" in remaining_text

    footnote_raw = extract(fixtures_dir / "footnote-heavy.pdf")
    _, footnote_report = detect_layout(footnote_raw)
    assert footnote_report.removed_furniture == []
    assert "Muslim ibn al-Hajjaj" in "\n".join(
        b.text for b in footnote_raw.pages[0].blocks
    )


def test_input_document_is_not_mutated(fixtures_dir) -> None:
    raw = extract(fixtures_dir / "indonesian-native.pdf")
    before = [b.number for b in raw.pages[0].blocks]
    detect_layout(raw)
    assert [b.number for b in raw.pages[0].blocks] == before
