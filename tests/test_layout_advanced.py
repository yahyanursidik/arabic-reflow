"""Complex layout tests (backlog M6): N-column reading order, footnotes,
images with captions."""

from __future__ import annotations

import zipfile
from xml.etree import ElementTree

from engine.extraction.models import RawBlock, RawImage, RawLine, RawSpan
from engine.layout.columns import find_gutters
from engine.layout.footnotes import detect_footnote_candidates
from engine.layout.reading_order import _column_order
from engine.pipeline import build_epub, build_reflowdoc
from engine.reflowdoc.models import FootnoteBlock, ImageBlock, ParagraphBlock

XHTML_NS = "http://www.w3.org/1999/xhtml"


def _block(number: int, x0: float, y0: float, x1: float, y1: float,
           text: str, size: float = 11.0) -> RawBlock:
    return RawBlock(
        number=number, type="text", bbox=(x0, y0, x1, y1),
        lines=[RawLine(bbox=(x0, y0, x1, y1),
                       spans=[RawSpan(text=text, font="H", size=size,
                                      bbox=(x0, y0, x1, y1))])],
    )


# --- Multi-column (M6-01, M6-02) -----------------------------------------------------


def _three_column_blocks() -> list[RawBlock]:
    blocks = []
    number = 1
    for column, (x0, x1) in enumerate(((50, 200), (230, 380), (410, 560)), start=1):
        for row in range(3):
            y0 = 100 + row * 120
            blocks.append(_block(number, x0, y0, x1, y0 + 100,
                                 f"kolom{column} baris{row + 1}"))
            number += 1
    return blocks


def test_three_gutters_detected() -> None:
    blocks = _three_column_blocks()
    gutters = find_gutters([b.bbox for b in blocks], 0.0, 595.0)
    assert len(gutters) == 2
    assert 200 < gutters[0] < 230
    assert 380 < gutters[1] < 410


def test_three_column_reading_order() -> None:
    blocks = _three_column_blocks()
    gutters = find_gutters([b.bbox for b in blocks], 0.0, 595.0)
    ordered = _column_order(blocks, gutters, 595.0)
    texts = [b.text for b in ordered]
    assert texts == [f"kolom{c} baris{r}"
                     for c in (1, 2, 3) for r in (1, 2, 3)]


def test_full_width_block_stays_in_place_in_three_columns() -> None:
    blocks = _three_column_blocks()
    heading = _block(99, 50, 40, 560, 70, "Judul Lintas Kolom", size=16)
    ordered = _column_order([heading] + blocks, find_gutters(
        [b.bbox for b in [heading] + blocks], 0.0, 595.0), 595.0)
    assert ordered[0] is heading
    assert ordered[1].text == "kolom1 baris1"


# --- Footnotes (M6-03, M6-04) ----------------------------------------------------------


def test_footnote_candidates_detected() -> None:
    blocks = [
        _block(1, 60, 100, 535, 600, "Body text berada jauh di atas.", size=11),
        _block(2, 60, 650, 535, 670,
               "1. Muhammad ibn Ismail al-Bukhari, Shahih al-Bukhari.", size=9),
    ]
    found = detect_footnote_candidates(blocks, 842.0, 11.0)
    assert found == {2: "1"}


def test_body_blocks_are_not_footnote_candidates() -> None:
    blocks = [_block(1, 60, 700, 535, 730,
                     "Paragraf normal tanpa nomor di bagian bawah halaman.")]
    assert detect_footnote_candidates(blocks, 842.0, 11.0) == {}


def test_fixture_footnotes_become_semantic_blocks(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "footnote-heavy.pdf")
    blocks = [b for c in result.document.chapters for b in c.blocks]
    footnotes = [b for b in blocks if isinstance(b, FootnoteBlock)]
    assert [f.marker for f in footnotes] == ["1", "2"]
    assert footnotes[0].blocks[0].text.startswith("1. Muhammad ibn Ismail")
    assert any(w.code == "FOOTNOTE_UNCERTAIN" for w in result.document.warnings)
    # footnotes come after the body text
    body_indexes = [i for i, b in enumerate(blocks) if isinstance(b, ParagraphBlock)]
    footnote_indexes = [i for i, b in enumerate(blocks) if isinstance(b, FootnoteBlock)]
    assert max(body_indexes) < min(footnote_indexes)


def test_fixture_footnotes_render_as_epub_asides(fixtures_dir) -> None:
    _, data, _ = build_epub(fixtures_dir / "footnote-heavy.pdf")
    archive = zipfile.ZipFile(__import__("io").BytesIO(data))
    xhtml = next(n for n in archive.namelist() if n.endswith(".xhtml")
                 and "chapter" in n)
    root = ElementTree.fromstring(archive.read(xhtml))
    asides = [e for e in root.iter(f"{{{XHTML_NS}}}aside")
              if e.get(f"{{http://www.idpf.org/2007/ops}}type") == "footnote"]
    assert len(asides) == 2


# --- Images and captions (M6-05) ---------------------------------------------------------


def test_fixture_image_becomes_block_with_caption_link(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "image-caption.pdf")
    doc = result.document
    blocks = [b for c in doc.chapters for b in c.blocks]
    images = [b for b in blocks if isinstance(b, ImageBlock)]
    assert len(images) == 1
    image = images[0]
    assert image.caption_block_id is not None
    captions = [b for b in blocks if b.id == image.caption_block_id]
    assert captions and "Gambar 1" in captions[0].text
    assert doc.resources, "image payload carried as a resource"
    resource = next(r for r in doc.resources if r.id == image.resource_id)
    assert resource.content and len(resource.content) > 100
    assert resource.media_type == "image/png"


def test_full_page_scan_is_not_treated_as_figure(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "hybrid.pdf")
    blocks = [b for c in result.document.chapters for b in c.blocks]
    assert not any(isinstance(b, ImageBlock) for b in blocks)
    assert {b.source.page for b in blocks} == {1}


def test_fixture_image_embedded_in_epub(fixtures_dir) -> None:
    _, data, _ = build_epub(fixtures_dir / "image-caption.pdf")
    archive = zipfile.ZipFile(__import__("io").BytesIO(data))
    images = [n for n in archive.namelist() if "resources/" in n]
    assert images, "image resource written into the EPUB"
    xhtml = next(n for n in archive.namelist() if n.endswith(".xhtml")
                 and "chapter" in n)
    html = archive.read(xhtml).decode("utf-8")
    assert "<figure>" in html and "<img" in html
    image_ref = images[0].split("resources/", 1)[1]
    assert f"resources/{image_ref}" in html
