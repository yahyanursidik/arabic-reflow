"""Extraction and script-annotation tests (backlog M1-02, M1-03, M1-04)."""

from __future__ import annotations

import pytest

from engine.arabic.detector import classify_script
from engine.extraction.extractor import extract
from engine.pipeline import detect_scripts
from engine.reflowdoc.models import Direction, ScriptClass


def test_extraction_preserves_page_and_block_structure(fixtures_dir) -> None:
    raw = extract(fixtures_dir / "indonesian-native.pdf")
    assert raw.page_count == 1
    page = raw.pages[0]
    assert page.page == 1
    assert page.width == pytest.approx(595, abs=1)
    assert page.height == pytest.approx(842, abs=1)
    assert len(page.blocks) >= 5  # heading, three paragraphs, page number

    for block in page.blocks:
        x0, y0, x1, y1 = block.bbox
        assert 0 <= x0 < x1 <= page.width + 1
        assert 0 <= y0 < y1 <= page.height + 1
        for line in block.lines:
            for span in line.spans:
                assert span.font
                assert span.size > 0


def test_span_text_joins_to_line_and_block(fixtures_dir) -> None:
    raw = extract(fixtures_dir / "indonesian-native.pdf")
    for page in raw.pages:
        for block in page.blocks:
            for line in block.lines:
                assert line.text == "".join(s.text for s in line.spans)
            assert block.text == "\n".join(l.text for l in block.lines)


def test_extractor_does_not_annotate_scripts(fixtures_dir) -> None:
    """The extractor observes; script detection annotates (separation of stages)."""
    raw = extract(fixtures_dir / "mixed-id-ar.pdf")
    for page in raw.pages:
        for block in page.blocks:
            assert block.script is None
            assert block.dir is None


def test_extracted_latin_matches_source_text(fixtures_dir) -> None:
    raw = extract(fixtures_dir / "indonesian-native.pdf")
    all_text = "\n".join(block.text for block in raw.pages[0].blocks)
    assert "Pendahuluan" in all_text
    assert "Shahih Bukhari" in all_text


def test_detect_scripts_annotates_mixed_block(fixtures_dir) -> None:
    raw = detect_scripts(extract(fixtures_dir / "mixed-id-ar.pdf"))
    page = raw.pages[0]
    mixed_blocks = [b for b in page.blocks if b.script is ScriptClass.MIXED]
    assert mixed_blocks, "the inline-Arabic sentence block must be Mixed"
    for block in mixed_blocks:
        assert block.dir in (Direction.LTR, Direction.RTL)
        assert block.lines  # evidence exists


def test_detect_scripts_annotates_rtl_blocks(fixtures_dir) -> None:
    raw = detect_scripts(extract(fixtures_dir / "arabic-native.pdf"))
    text_blocks = [b for b in raw.pages[0].blocks if b.lines]
    assert text_blocks
    for block in text_blocks:
        assert block.script is ScriptClass.ARABIC
        assert block.dir is Direction.RTL


def test_detect_scripts_span_level(fixtures_dir) -> None:
    raw = detect_scripts(extract(fixtures_dir / "mixed-id-ar.pdf"))
    span_scripts = [
        classify_script(span.text)
        for page in raw.pages
        for block in page.blocks
        for line in block.lines
        for span in line.spans
        if span.text.strip()
    ]
    assert ScriptClass.MIXED in span_scripts or ScriptClass.ARABIC in span_scripts
    # nothing was modified by annotation
    all_text = "\n".join(
        block.text for page in raw.pages for block in page.blocks
    )
    assert "Hadits ini diriwayatkan dari" in all_text


def test_scanned_page_has_no_text_blocks_but_images(fixtures_dir) -> None:
    raw = extract(fixtures_dir / "scanned.pdf")
    page = raw.pages[0]
    assert page.blocks == []
    assert len(page.images) >= 1
    image = page.images[0]
    x0, y0, x1, y1 = image.bbox
    assert (x1 - x0) > page.width * 0.9  # full-page scan


def test_pdf_metadata_captured(fixtures_dir) -> None:
    raw = extract(fixtures_dir / "mixed-id-ar.pdf")
    assert raw.pdf_title == "Riyadhus Shalihin Terjemah"
    assert raw.pdf_author == "Imam Muslim, Yahya ibn Syaraf an-Nawawi"


def test_encrypted_pdf_refuses_extraction(tmp_path) -> None:
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "rahasia")
    target = tmp_path / "encrypted.pdf"
    doc.save(
        target,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="user-secret",
    )
    doc.close()
    with pytest.raises(ValueError, match="encrypted"):
        extract(target)
