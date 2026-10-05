"""Paragraph reconstruction, dehyphenation, and heading detection tests
(backlog M2-02, M2-03, M2-04)."""

from __future__ import annotations

from engine.arabic.unicode import count_harakat
from engine.extraction.extractor import extract
from engine.extraction.models import RawBlock, RawLine, RawSpan
from engine.layout.furniture import detect_layout
from engine.layout.reading_order import reconstruct_reading_order
from engine.reconstruction.headings import HeadingInfo, detect_headings
from engine.reconstruction.paragraphs import block_runs, build_paragraphs


def make_block(number: int, bbox: tuple[float, float, float, float],
               lines: list[str], size: float = 11.0, flags: int = 0) -> RawBlock:
    return RawBlock(
        number=number,
        type="text",
        bbox=bbox,
        lines=[
            RawLine(
                bbox=(bbox[0], bbox[1] + i * 14, bbox[2], bbox[1] + (i + 1) * 14),
                spans=[RawSpan(text=text, font="Helv", size=size, flags=flags,
                               bbox=(bbox[0], bbox[1] + i * 14, bbox[2],
                                     bbox[1] + (i + 1) * 14))],
            )
            for i, text in enumerate(lines)
        ],
    )


# --- Dehyphenation (M2-03) ----------------------------------------------------


def test_latin_dehyphenation_with_provenance() -> None:
    block = make_block(1, (60, 100, 535, 130), ["pembe-", "lajaran merupakan proses."])
    runs = block_runs(block)
    text = "".join(r.text for r in runs)
    assert text == "pembelajaran merupakan proses."
    dehyphenated = [r for r in runs if "dehyphenation" in r.transformations]
    assert len(dehyphenated) == 1
    # Run-level provenance: the run's full original form, line break included.
    assert dehyphenated[0].source_text == "pembe-\nlajaran merupakan proses."


def test_hyphen_kept_when_continuation_is_uppercase() -> None:
    block = make_block(1, (60, 100, 535, 130), ["MIN-", "MAX value."])
    text = "".join(r.text for r in block_runs(block))
    assert "MIN-MAX" in text  # compound kept, confidence not high enough


def test_arabic_is_never_dehyphenated() -> None:
    block = make_block(1, (60, 100, 535, 130), ["الك-", "تاب موجود."])
    text = "".join(r.text for r in block_runs(block))
    assert "-" in text  # no dehyphenation for Arabic


# --- Paragraph merging (M2-02) -------------------------------------------------


def test_lines_within_block_join_into_one_paragraph() -> None:
    block = make_block(
        1, (60, 100, 535, 160),
        ["Para ulama sepakat bahwa niat merupakan", "syarat sahnya berbagai amal ibadah."],
    )
    drafts = build_paragraphs(1, [block])
    assert len(drafts) == 1
    assert drafts[0].text == "Para ulama sepakat bahwa niat merupakan syarat sahnya berbagai amal ibadah."
    assert drafts[0].confidence == 0.95


def test_full_width_non_terminal_block_continues_paragraph() -> None:
    first = make_block(
        1, (60, 100, 535, 130),
        ["Para ulama sepakat bahwa niat merupakan syarat sahnya berbagai amal dan"],
    )
    second = make_block(2, (60, 140, 535, 160), ["ibadah dalam Islam."])
    drafts = build_paragraphs(1, [first, second])
    assert len(drafts) == 1
    assert drafts[0].text.endswith("amal dan ibadah dalam Islam.")
    assert drafts[0].merged_block_count == 2
    assert drafts[0].confidence == 0.75


def test_short_last_line_does_not_merge() -> None:
    first = make_block(1, (60, 100, 300, 130), ["Kalimat ini belum selesai tapi"])
    second = make_block(2, (60, 140, 535, 160), ["baris berikutnya tetap terpisah."])
    drafts = build_paragraphs(1, [first, second])
    assert len(drafts) == 2


def test_terminal_punctuation_blocks_do_not_merge() -> None:
    first = make_block(1, (60, 100, 535, 130), ["Kalimat pertama selesai."])
    second = make_block(2, (60, 140, 535, 160), ["Kalimat kedua dimulai."])
    drafts = build_paragraphs(1, [first, second])
    assert len(drafts) == 2


def test_stray_punctuation_fragment_attaches() -> None:
    first = make_block(1, (60, 100, 535, 130), ["أما بعد"])
    colon = make_block(2, (520, 140, 535, 160), [":"])
    drafts = build_paragraphs(1, [first, colon])
    assert len(drafts) == 1
    assert drafts[0].text == "أما بعد:"


def test_blocks_in_different_columns_never_merge() -> None:
    # Geometry isolates the column guard: the left block's last line IS
    # full-width relative to the reference, so only the column rule blocks it.
    left = make_block(1, (50, 100, 250, 130), ["Teks kolom kiri berlanjut tanpa tanda akhir"])
    right = make_block(2, (275, 140, 400, 160), ["dan blok kolom kanan terpisah."])
    drafts = build_paragraphs(1, [left, right])
    assert len(drafts) == 2


# --- Headings (M2-04) ----------------------------------------------------------


def test_font_size_detects_heading() -> None:
    blocks = [
        make_block(1, (60, 60, 535, 100), ["Pendahuluan"], size=18, flags=16),
        make_block(2, (60, 110, 535, 240), ["Kitab ini mengumpulkan hadits-hadits pilihan "
                                            "dari Shahih Bukhari dan Shahih Muslim yang "
                                            "disusun sesuai bab-bab fikih."]),
    ]
    body = 11.0
    headings = detect_headings(blocks, body)
    assert 1 in headings
    assert headings[1].level == 1
    assert 2 not in headings


def test_bab_numbering_detects_level_one() -> None:
    blocks = [
        make_block(1, (60, 60, 535, 100), ["Bab Pertama: Niat"], size=11),
        make_block(2, (60, 110, 535, 240), ["Kitab ini mengumpulkan hadits-hadits pilihan "
                                            "dari Shahih Bukhari dan Shahih Muslim yang "
                                            "disusun sesuai bab-bab fikih."]),
    ]
    headings = detect_headings(blocks, 11.0)
    assert 1 in headings
    assert headings[1].level == 1


def test_terminal_block_is_never_heading() -> None:
    blocks = [
        make_block(1, (60, 60, 535, 100), ["Ini kalimat besar di halaman."], size=18),
        make_block(2, (60, 110, 535, 240), ["Kitab ini mengumpulkan hadits-hadits pilihan "
                                            "dari Shahih Bukhari dan Shahih Muslim yang "
                                            "disusun sesuai bab-bab fikih."]),
    ]
    assert detect_headings(blocks, 11.0) == {}


# --- Fixtures -------------------------------------------------------------------


def _fixture_paragraphs(fixtures_dir, name: str):
    from engine.reconstruction.headings import body_font_size

    raw = extract(fixtures_dir / name)
    raw, _ = detect_layout(raw)
    raw, _ = reconstruct_reading_order(raw)
    blocks = [b for b in raw.pages[0].blocks if b.type == "text" and b.text.strip()]
    headings = detect_headings(blocks, body_font_size(blocks))
    return blocks, build_paragraphs(1, blocks, headings)


def test_fixture_arabic_paragraphs_merge_and_preserve_text(fixtures_dir) -> None:
    """Blocks-per-line Arabic paragraphs must merge back, text verbatim."""
    blocks, drafts = _fixture_paragraphs(fixtures_dir, "arabic-native.pdf")
    texts = [d.text for d in drafts]
    merged = next(t for t in texts if "اﻟﺤﻤﺪ" in t)
    assert "اﻟﺪﻳﻦ، أﻣﺎ ﺑﻌﺪ:" in merged  # continuation and colon fragment attached
    assert "ﺑﺴﻢ ﷲ اﻟﺮﺣﻤﻦ اﻟﺮﺣﻴﻢ" in texts  # bismillah stays its own paragraph
    # no character loss: combining marks survive reconstruction untouched
    raw_text = "\n".join(b.text for b in blocks)
    assert count_harakat("".join(texts)) == count_harakat(raw_text)


def test_fixture_vocalized_harakat_survive_reconstruction(fixtures_dir) -> None:
    _, drafts = _fixture_paragraphs(fixtures_dir, "arabic-vocalized.pdf")
    total_harakat = sum(count_harakat(d.text) for d in drafts)
    assert total_harakat >= 60
    # bismillah and the two hadith paragraphs stay separate
    texts = [d.text for d in drafts]
    bismillah = next(t for t in texts if "ﺑِﺴْﻢِ" in t)
    assert "اﻷَْﻋْﻤَﺎلُ" not in bismillah
    assert len(drafts) == 3
