"""Windows write-failure and illegal-XML-codepoint regression tests."""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree

import pytest
from ebooklib import epub

from engine.epub.renderer import render_epub
from engine.epub.xml import output_diagnostics, xml_text
from engine.reflowdoc.models import ReflowDocument
from engine.validation.epub import assert_valid
from engine.validation.reflow import quality_report


def sample_document():
    return ReflowDocument.model_validate({
        "metadata": {"title": "Buku\x00 uji", "author": ["Penulis\x1b"], "languages": ["id", "ar"]},
        "chapters": [{"id": "c", "title": "Bab\x01", "blocks": [
            {"id": "heading", "type": "heading", "level": 1, "text": "Judul\x1b Arab إِنَّمَا"},
            {"id": "paragraph", "type": "paragraph", "content": [{"type": "text", "text": "Teks\x00 tetap \t\n\r"}, {"type": "span", "text": "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ", "lang": "ar", "dir": "rtl", "script": "Arabic"}]},
        ]}],
    })


def test_xml_filter_preserves_valid_characters_including_harakat():
    text = "Arab إِنَّمَا\t\n\r 123، 🙂\x00\x01\x0b\x0c\x1b\ud800\ufffe\uffff"
    assert xml_text(text) == "Arab إِنَّمَا\t\n\r 123، 🙂"


def test_control_characters_are_reported_and_only_excluded_from_epub():
    document = sample_document()
    original = document.model_dump_json()
    diagnostics = output_diagnostics(document)
    assert diagnostics["count"] == 5
    assert diagnostics["block_ids"] == ["heading", "paragraph"]
    report = quality_report(document)
    assert report["can_export"]
    assert report["review_block_ids"] == ["heading", "paragraph"]
    assert any(issue["code"] == "XML_INVALID_CHARACTERS" for issue in report["issues"])

    data = render_epub(document)
    assert_valid(data)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if name.endswith((".xhtml", ".opf", ".ncx")):
                ElementTree.fromstring(archive.read(name))
        chapter = archive.read("EPUB/chapter-001.xhtml").decode("utf-8")
        assert "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ" in chapter
        assert "\x1b" not in chapter and "\x00" not in chapter
    assert document.model_dump_json() == original


@pytest.mark.parametrize("failure", [ValueError("serialization failed"), OSError("write failed")])
def test_zip_is_closed_and_original_failure_is_not_masked(monkeypatch, failure):
    writers = []

    def fail(writer):
        writers.append(writer)
        # EbookLib has already opened its archive before writing the items.
        assert writer.out.fp is not None
        raise failure

    monkeypatch.setattr(epub.EpubWriter, "_write_items", fail)
    with pytest.raises(type(failure)) as caught:
        render_epub(sample_document())
    assert caught.value is failure
    assert writers[0].out.fp is None
    assert isinstance(writers[0].file_name, io.BytesIO)
    assert writers[0].file_name.closed


def test_renderer_writes_to_memory_not_a_temporary_path(monkeypatch):
    original_write = epub.EpubWriter.write
    writers = []

    def record(writer):
        assert isinstance(writer.file_name, io.BytesIO)
        writers.append(writer)
        return original_write(writer)

    monkeypatch.setattr(epub.EpubWriter, "write", record)
    assert_valid(render_epub(sample_document()))
    assert writers[0].out.fp is None
    assert writers[0].file_name.closed


def test_inline_pdf_images_without_xrefs_have_embedded_payloads():
    import pymupdf
    from engine.extraction.extractor import extract

    # Valid inline RGB image, deliberately without an indirect object/xref.
    document = pymupdf.open()
    page = document.new_page(width=200, height=200)
    stream = document.get_new_xref()
    document.update_object(stream, "<<>>")
    document.update_stream(stream, b"q 20 0 0 20 40 40 cm BI /W 1 /H 1 /CS /RGB /BPC 8 ID \xff\x00\x00 EI Q")
    page.set_contents(stream)
    data = document.tobytes()
    document.close()
    raw = extract(data)
    assert len(raw.pages[0].images) == 1
    image = raw.pages[0].images[0]
    assert image.xref == 0
    assert image.content
    assert image.media_type == "image/png"
    assert image.content.startswith(b"\x89PNG")


def test_inline_image_survives_epub_reconstruction_and_packaging():
    import pymupdf
    from engine.pipeline import build_epub

    document = pymupdf.open()
    page = document.new_page(width=200, height=200)
    page.insert_text((20, 20), "Dokumen dengan gambar inline.")
    previous = b"\n".join(document.xref_stream(xref) for xref in page.get_contents())
    stream = document.get_new_xref()
    document.update_object(stream, "<<>>")
    document.update_stream(stream, previous + b"\nq 20 0 0 20 40 40 cm BI /W 1 /H 1 /CS /RGB /BPC 8 ID \xff\x00\x00 EI Q")
    page.set_contents(stream)
    source = document.tobytes()
    document.close()
    result, data, _ = build_epub(source)
    assert quality_report(result.document)["can_export"]
    images = [resource for resource in result.document.resources if resource.kind == "image"]
    assert images and images[0].content
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert f"EPUB/resources/{images[0].filename}" in archive.namelist()


def test_inline_image_matching_tolerates_outward_rounded_geometry():
    import math
    import pymupdf
    from engine.extraction.extractor import extract_page

    document = pymupdf.open()
    page = document.new_page(width=200, height=200)
    stream = document.get_new_xref()
    document.update_object(stream, "<<>>")
    document.update_stream(stream, b"q 19.7 0 0 19.7 40.3 40.3 cm BI /W 1 /H 1 /CS /RGB /BPC 8 ID \xff\x00\x00 EI Q")
    page.set_contents(stream)

    class RoundedInfoPage:
        def __getattr__(self, name):
            return getattr(page, name)

        def get_image_info(self, **kwargs):
            images = page.get_image_info(**kwargs)
            for image in images:
                x0, y0, x1, y1 = image["bbox"]
                image["bbox"] = (math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1))
            return images

    raw = extract_page(RoundedInfoPage(), 1)
    document.close()
    assert raw.images[0].xref == 0
    assert raw.images[0].content
