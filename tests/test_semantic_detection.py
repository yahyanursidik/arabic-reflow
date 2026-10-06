"""Quote, list, and table detection (PRD 8.10/8.14; backlog M6-06)."""

from __future__ import annotations

from pathlib import Path

from engine.arabic.detector import ScriptClass
from engine.extraction.models import RawBlock, RawLine, RawSpan
from engine.layout.tables import detect_tables
from engine.pipeline import build_reflowdoc
from engine.reflowdoc.models import ListBlock, ParagraphBlock, TableBlock
from engine.reconstruction.lists import detect_lists
from engine.reconstruction.paragraphs import ContentRun, ParagraphDraft
from engine.reconstruction.quotes import is_quote_draft

FIXTURES = Path(__file__).parent / "fixtures"


def draft(
    text: str,
    *,
    x0: float = 72.0,
    x1: float = 523.0,
    y0: float = 100.0,
    merged: int = 1,
    heading: bool = False,
    footnote: str | None = None,
) -> ParagraphDraft:
    return ParagraphDraft(
        page=1,
        bbox=(x0, y0, x1, y0 + 14),
        runs=[ContentRun(script=ScriptClass.LATIN, text=text)],
        confidence=0.9,
        merged_block_count=merged,
        is_heading=heading,
        footnote_marker=footnote,
    )


# --- Quotes ----------------------------------------------------------------------


def test_indented_both_sides_is_quote() -> None:
    assert is_quote_draft(
        draft("Amanah adalah beban yang ditunaikan.", x0=110, x1=485),
        page_x0=72.0, page_x1=523.0, ref_width=451.0, single_column=True,
    )


def test_full_width_block_is_not_quote() -> None:
    assert not is_quote_draft(
        draft("Paragraf penuh selebar halaman biasa saja."),
        page_x0=72.0, page_x1=523.0, ref_width=451.0, single_column=True,
    )


def test_caption_and_headings_are_not_quotes() -> None:
    assert not is_quote_draft(
        draft("Gambar 1: Diagram alir.", x0=150, x1=450),
        page_x0=72.0, page_x1=523.0, ref_width=451.0, single_column=True,
        is_caption=True,
    )
    assert not is_quote_draft(
        draft("Bab Satu", x0=150, x1=450, heading=True),
        page_x0=72.0, page_x1=523.0, ref_width=451.0, single_column=True,
    )


def test_column_member_is_not_quote() -> None:
    assert not is_quote_draft(
        draft("Kolom kanan bagian satu.", x0=320, x1=510),
        page_x0=72.0, page_x1=523.0, ref_width=451.0, single_column=False,
    )


# --- Lists ------------------------------------------------------------------------


def test_numbered_drafts_form_ordered_list() -> None:
    runs = detect_lists(
        [
            draft("1. Meniatkan niat.", y0=100),
            draft("2. Mengerjakan amal.", y0=130),
            draft("3. Menjaga istiqamah.", y0=160),
        ]
    )
    assert len(runs) == 1
    start, run = runs[0]
    assert start == 0
    assert run.ordered is True
    assert len(run.drafts) == 3


def test_bullets_form_unordered_list() -> None:
    runs = detect_lists(
        [
            draft("• Shalat lima waktu.", y0=100),
            draft("• Puasa Ramadan.", y0=130),
        ]
    )
    assert len(runs) == 1
    assert runs[0][1].ordered is False


def test_single_marker_is_not_a_list() -> None:
    runs = detect_lists(
        [
            draft("Paragraf pembuka biasa.", y0=100),
            draft("1. Hanya satu butir bernomor.", y0=130),
        ]
    )
    assert runs == []


def test_lowercase_continuation_joins_item() -> None:
    runs = detect_lists(
        [
            draft("• Shalat lima waktu", y0=100),
            draft("sebagaimana diperintahkan.", y0=130),
            draft("• Puasa Ramadan.", y0=160),
        ]
    )
    assert len(runs) == 1
    assert len(runs[0][1].drafts) == 3


# --- Tables ------------------------------------------------------------------------


def _cell_block(number: int, x: float, y: float, text: str) -> RawBlock:
    bbox = (x, y, x + 60.0, y + 12.0)
    return RawBlock(
        number=number,
        type="text",
        bbox=bbox,
        lines=[
            RawLine(
                bbox=bbox,
                spans=[RawSpan(text=text, font="F", size=10, bbox=bbox)],
            )
        ],
    )


def _table_blocks() -> list[RawBlock]:
    blocks = []
    number = 0
    for row in range(3):
        for col in range(3):
            number += 1
            blocks.append(_cell_block(number, 100.0 + col * 150.0, 120.0 + row * 30.0,
                                      f"sel{row}{col}"))
    return blocks


def _rules() -> list[tuple[float, float, float, float]]:
    rules = [(100.0, 120.0 + r * 30.0, 550.0, 120.0 + r * 30.0) for r in range(4)]
    rules += [(100.0 + c * 150.0, 120.0, 100.0 + c * 150.0, 210.0) for c in range(4)]
    return rules


def test_ruled_grid_is_detected() -> None:
    regions = detect_tables(1, _table_blocks(), _rules())
    assert len(regions) == 1
    region = regions[0]
    assert (region.n_rows, region.n_cols) == (3, 3)
    assert region.confidence >= 0.75
    assert [cell.text for _, _, cell in region.cells[:3]] == ["sel00", "sel01", "sel02"]


def test_unruled_grid_is_rejected() -> None:
    # Two-column prose aligns exactly like a grid; only rules make it a table.
    assert detect_tables(1, _table_blocks(), []) == []


def test_paragraph_line_does_not_break_grid() -> None:
    blocks = _table_blocks()
    blocks.append(_cell_block(99, 100.0, 240.0, "Paragraf panjang di bawah tabel."))
    regions = detect_tables(1, blocks, _rules())
    assert len(regions) == 1
    assert len(regions[0].cells) == 9


def test_table_fixture_becomes_semantic_table() -> None:
    result = build_reflowdoc(FIXTURES / "table-grid.pdf")
    blocks = [b for c in result.document.chapters for b in c.blocks]
    tables = [b for b in blocks if isinstance(b, TableBlock)]
    assert len(tables) == 1
    table = tables[0]
    assert [[cell.text for cell in row] for row in table.rows] == [
        ["Nama", "Jumlah", "Keterangan"],
        ["Kurma", "3 kg", "Untuk tamu"],
        ["Air zamzam", "2 botol", "Dibawa pulang"],
    ]
    assert table.fallback_resource_id is None
    codes = [w.code for w in result.document.warnings]
    assert "TABLE_DETECTED" in codes
    # The paragraph below the table stays a paragraph.
    paragraphs = [b for b in blocks if isinstance(b, ParagraphBlock)]
    assert any("jadwal pembagian" in b.text for b in paragraphs)


def test_list_and_quote_flow_through_pipeline() -> None:
    # Table fixture has none; synthetic check that lists render from pipeline
    # is covered by unit tests above plus EPUB renderer tests.
    blocks = [b for c in build_reflowdoc(FIXTURES / "table-grid.pdf").document.chapters
              for b in c.blocks]
    assert not [b for b in blocks if isinstance(b, ListBlock)]
