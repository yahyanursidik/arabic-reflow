"""EPUB renderer tests: XHTML semantics, packaging, font, validation (M4)."""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree

import pytest

from engine.epub.renderer import render_epub
from engine.epub.xhtml import chapter_xhtml
from engine.pipeline import build_epub, build_reflowdoc
from engine.reflowdoc.models import (
    Chapter,
    DocumentMetadata,
    FootnoteBlock,
    ListBlock,
    ListItem,
    QuoteBlock,
    ReflowDocument,
    ReflowWarning,
    TableBlock,
)
from engine.validation.epub import (
    EPUBValidationError,
    assert_valid,
    validate_epub,
)

XHTML_NS = "http://www.w3.org/1999/xhtml"


def _parse(html: str) -> ElementTree.Element:
    return ElementTree.fromstring(html)


def _mixed_document() -> ReflowDocument:
    doc = ReflowDocument(
        metadata=DocumentMetadata(
            title="Kitab Uji",
            author=["Imam Uji"],
            languages=["id", "ar"],
        ),
    )
    doc.chapters = [
        Chapter(
            id="chapter-001",
            title="Pendahuluan",
            blocks=[
                {
                    "id": "block-001",
                    "type": "heading",
                    "level": 1,
                    "text": "Bab Pertama",
                    "lang": "id",
                    "dir": "ltr",
                },
                {
                    "id": "block-002",
                    "type": "paragraph",
                    "lang": "id",
                    "dir": "ltr",
                    "content": [
                        {"type": "text", "text": "Hadits ini dari "},
                        {"type": "span", "text": "أبي هريرة", "lang": "ar",
                         "script": "Arabic", "dir": "rtl"},
                        {"type": "text", "text": " & <teman> dia."},
                    ],
                },
                {
                    "id": "block-003",
                    "type": "paragraph",
                    "lang": "ar",
                    "dir": "rtl",
                    "content": [
                        {"type": "span", "text": "بسم الله الرحمن الرحيم",
                         "lang": "ar", "script": "Arabic", "dir": "rtl"},
                    ],
                },
                {
                    "id": "block-004",
                    "type": "quote",
                    "subtype": "arabic",
                    "lang": "ar",
                    "dir": "rtl",
                    "text": "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ",
                },
                {
                    "id": "block-005",
                    "type": "list",
                    "ordered": True,
                    "lang": "id",
                    "items": [
                        {"blocks": [{"id": "block-006", "type": "paragraph",
                                     "content": [{"type": "text", "text": "Item satu."}]}]},
                    ],
                },
                {
                    "id": "block-007",
                    "type": "table",
                    "rows": [[{"text": "A"}, {"text": "B"}]],
                    "confidence": 0.9,
                },
                {
                    "id": "fn-1",
                    "type": "footnote",
                    "marker": "1",
                    "blocks": [{"id": "block-008", "type": "paragraph",
                                "content": [{"type": "text", "text": "Catatan kaki."}]}],
                },
            ],
        )
    ]
    return doc


# --- XHTML semantics (M4-01, M4-02) ------------------------------------------------


def test_heading_and_paragraph_render_semantically() -> None:
    html = chapter_xhtml(_mixed_document(), _mixed_document().chapters[0])
    assert '<h1 lang="id" dir="ltr">Bab Pertama</h1>' in html
    assert '<p lang="id" dir="ltr">' in html
    assert '<blockquote class="arabic" lang="ar" dir="rtl">' in html
    assert "<ol" in html and "<li>" in html and "Item satu." in html
    assert "<table>" in html and "<td>A</td>" in html
    assert 'epub:type="footnote"' in html and "Catatan kaki." in html


def test_arabic_block_gets_lang_dir_and_class() -> None:
    html = chapter_xhtml(_mixed_document(), _mixed_document().chapters[0])
    assert '<p class="arabic" lang="ar" dir="rtl">' in html


def test_inline_arabic_renders_inside_bdi() -> None:
    html = chapter_xhtml(_mixed_document(), _mixed_document().chapters[0])
    assert '<bdi lang="ar" dir="rtl">أبي هريرة</bdi>' in html


def test_text_is_escaped_not_altered() -> None:
    html = chapter_xhtml(_mixed_document(), _mixed_document().chapters[0])
    assert " &amp; &lt;teman&gt; dia." in html
    # source text survives verbatim after unescaping
    root = _parse(html)
    paragraphs = ["".join(p.itertext()) for p in root.iter(f"{{{XHTML_NS}}}p")]
    assert any("Hadits ini dari  & <teman> dia." in t for t in paragraphs) or any(
        "Hadits ini dari" in t and "<teman>" in t for t in paragraphs
    )


def test_root_language_and_direction() -> None:
    html = chapter_xhtml(_mixed_document(), _mixed_document().chapters[0])
    assert 'lang="id"' in html and 'dir="ltr"' in html


def test_arabic_primary_document_root_is_rtl() -> None:
    doc = _mixed_document()
    doc.metadata.languages = ["ar"]
    html = chapter_xhtml(doc, doc.chapters[0])
    assert 'dir="rtl"' in html.split("<body", 1)[0]


def test_renderer_does_not_mutate_document() -> None:
    doc = _mixed_document()
    before = doc.model_dump_json()
    chapter_xhtml(doc, doc.chapters[0])
    render_epub(doc)
    assert doc.model_dump_json() == before


# --- Packaging, font, validation (M4-03/04/05) --------------------------------------


def test_fixture_epub_builds_and_validates(fixtures_dir) -> None:
    result, data, report = build_epub(fixtures_dir / "mixed-id-ar.pdf")
    assert data[:2] == b"PK"
    assert report.ok
    assert not report.severe
    assert result.document.chapters


def test_epub_structure_and_lang_dir_preserved(fixtures_dir) -> None:
    _, data, _ = build_epub(fixtures_dir / "mixed-id-ar.pdf")
    archive = zipfile.ZipFile(io.BytesIO(data))
    names = archive.namelist()
    assert names[0] == "mimetype"
    assert archive.read("mimetype") == b"application/epub+zip"
    assert "META-INF/container.xml" in names
    assert any(n.endswith("nav.xhtml") for n in names)

    xhtml = next(n for n in names if n.endswith(".xhtml") and "chapter" in n)
    root = ElementTree.fromstring(archive.read(xhtml))
    assert root.get("lang") == "id"
    bdis = list(root.iter(f"{{{XHTML_NS}}}bdi"))
    assert bdis, "inline Arabic must render inside bdi"
    assert any(b.get("dir") == "rtl" and b.get("lang") == "ar" for b in bdis), (
        "bdi elements must carry lang=ar dir=rtl"
    )


def test_arabic_fixture_embeds_firago_font(fixtures_dir) -> None:
    from engine.epub.css import FONT_FILENAME

    _, data, _ = build_epub(fixtures_dir / "arabic-native.pdf")
    archive = zipfile.ZipFile(io.BytesIO(data))
    assert any(n.endswith(FONT_FILENAME) for n in archive.namelist())


def test_latin_only_fixture_skips_font(fixtures_dir) -> None:
    from engine.epub.css import FONT_FILENAME

    _, data, _ = build_epub(fixtures_dir / "indonesian-native.pdf")
    archive = zipfile.ZipFile(io.BytesIO(data))
    assert FONT_FILENAME not in archive.namelist()


def test_validator_flags_broken_package() -> None:
    broken = io.BytesIO()
    with zipfile.ZipFile(broken, "w") as zf:
        zf.writestr("META-INF/container.xml", "<broken")
    report = validate_epub(broken.getvalue())
    assert not report.ok
    assert report.severe
    with pytest.raises(EPUBValidationError):
        assert_valid(broken.getvalue())


def test_validator_accepts_generated_epub(fixtures_dir) -> None:
    _, data, _ = build_epub(fixtures_dir / "footnote-heavy.pdf")
    report = validate_epub(data)
    assert report.ok
    codes = [i.code for i in report.issues]
    assert "XHTML_MALFORMED" not in codes
