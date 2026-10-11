"""Regression tests for semantic editing, RTL layout, nested quality and OCR modes."""

from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest

from engine.arabic.report import attach_integrity, document_report
from engine.epub.renderer import _document_has_arabic, render_epub
from engine.layout.reading_order import _column_order, _page_is_rtl
from engine.ocr.decision import apply_ocr, decide_pages
from engine.ocr.runtime import language_codes, tesseract_status
from engine.reflowdoc.editing import edited_content, move_block, update_semantic_block
from engine.reflowdoc.models import ParagraphBlock, ReflowDocument
from engine.validation.reflow import quality_report
from tests.test_layout_advanced import _block, _three_column_blocks
from tests.test_ocr import CORRUPTED_ARABIC, FakeEngine, _native_page


def test_rtl_columns_read_right_to_left_without_reversing_text():
    blocks = _three_column_blocks()
    result = _column_order(blocks, [215, 395], 595, rtl=True)
    assert [block.text for block in result] == [f"kolom{column} baris{row}" for column in (3, 2, 1) for row in (1, 2, 3)]
    assert len(result) == len(blocks)


def test_column_blocks_overlapping_spanning_headings_are_never_lost():
    blocks = [_block(1, 50, 90, 200, 150, "Left overlap"), _block(2, 350, 100, 550, 160, "Right overlap"), _block(3, 50, 100, 550, 120, "Spanning heading")]
    ordered = _column_order(blocks, [275], 595)
    assert sorted(block.number for block in ordered) == [1, 2, 3]


def test_arabic_page_direction_is_not_overridden_by_a_latin_header():
    assert _page_is_rtl([_block(1, 0, 0, 100, 10, "Title"), _block(2, 0, 20, 100, 100, "بسم الله الرحمن الرحيم السلام عليكم")])


def nested_document():
    return ReflowDocument.model_validate({"chapters": [{"id": "c", "blocks": [{"id": "list", "type": "list", "items": [{"blocks": [{"id": "inner", "type": "paragraph", "source": {"page": 2}, "content": [{"type": "text", "text": CORRUPTED_ARABIC}]}]}]}]}]})


def test_nested_arabic_is_inspected_and_included_in_quality_and_font_selection():
    document = nested_document()
    attach_integrity(document)
    assert document_report(document)["low_confidence_block_ids"] == ["inner"]
    assert quality_report(document)["review_block_ids"] == ["inner"]
    assert _document_has_arabic(document)
    assert len(quality_report(document)["pages"]) == 1


def test_structural_edit_preserves_text_and_does_not_mutate_original():
    text = "Hadits dari أَبِي هُرَيْرَةَ dalam kitab."
    original = ParagraphBlock(id="p", content=edited_content(text), lang="id", dir="ltr")
    heading = update_semantic_block(original, type="heading", level=2)
    assert heading.text == original.text == text
    assert original.type == "paragraph" and not original.modified_by_user
    back = update_semantic_block(heading, type="paragraph")
    assert back.text == text
    assert any(getattr(node, "dir", None) == "rtl" for node in back.content)


def test_invalid_heading_level_is_rejected_on_paragraph():
    block = ParagraphBlock(id="p", content=edited_content("Teks."))
    with pytest.raises(ValueError, match="heading"):
        update_semantic_block(block, level=2)


def test_move_block_preserves_group_and_all_content():
    document = ReflowDocument.model_validate({"chapters": [{"id": "c", "blocks": [{"id": "one", "type": "paragraph", "content": [{"type": "text", "text": "Satu"}]}, {"id": "two", "type": "paragraph", "content": [{"type": "text", "text": "Dua"}]}]}]})
    move_block(document, "two", "up")
    assert [block.id for block in document.chapters[0].blocks] == ["two", "one"]
    with pytest.raises(ValueError, match="boundary"):
        move_block(document, "two", "up")


def test_quality_rejects_missing_resources_duplicate_ids_and_empty_content():
    document = ReflowDocument.model_validate({"chapters": [{"id": "c", "blocks": [{"id": "same", "type": "image", "resource_id": "missing"}, {"id": "same", "type": "page_break"}]}]})
    quality = quality_report(document)
    assert not quality["can_export"]
    assert {issue["code"] for issue in quality["issues"]} == {"MISSING_RESOURCE", "DUPLICATE_BLOCK_IDS"}
    assert not quality_report(ReflowDocument())["can_export"]


def test_ocr_decisions_include_corrupted_arabic_and_explicit_force():
    from engine.extraction.models import RawDocument
    raw = RawDocument(page_count=1, pages=[_native_page(f"{CORRUPTED_ARABIC} {CORRUPTED_ARABIC}")])
    profile = SimpleNamespace(pages=[])
    assert decide_pages(profile, raw)[0].reason == "low_arabic_confidence"
    assert decide_pages(profile, raw, force=True)[0].reason == "user_forced"


def test_forced_ocr_replaces_native_only_when_explicitly_requested(fixtures_dir):
    from engine.analyzer.analyzer import analyze
    from engine.extraction.extractor import extract
    source = fixtures_dir / "indonesian-native.pdf"
    raw = extract(source)
    engine = FakeEngine("Explicit OCR candidate")
    automatic, auto_report = apply_ocr(source, analyze(source), raw, engine)
    assert engine.calls == 0
    forced, forced_report = apply_ocr(source, analyze(source), raw, engine, force=True)
    assert engine.calls == 1
    assert forced.pages[0].text == "Explicit OCR candidate"
    assert forced_report.selected_pages == [1]
    assert automatic.pages[0].text == raw.pages[0].text


def test_tesseract_maps_language_labels_and_checks_actual_language_data(monkeypatch):
    import engine.ocr.runtime as runtime
    assert language_codes(["ar", "id", "en", "ara"]) == ["ara", "ind", "eng"]
    monkeypatch.setattr(runtime.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(runtime, "tesseract_command", lambda: "tesseract")
    monkeypatch.setattr(runtime.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout="List of available languages:\neng\n"))
    assert not tesseract_status()["available"]
    assert tesseract_status(["en"])["available"]
    assert tesseract_status()["languages"] == ["en"]


def test_epub_navigation_links_to_user_heading_levels():
    document = ReflowDocument.model_validate({"metadata": {"title": "Buku", "languages": ["id"]}, "chapters": [{"id": "c", "blocks": [{"id": "h1", "type": "heading", "level": 1, "text": "Bab"}, {"id": "h2", "type": "heading", "level": 2, "text": "Subbab"}]}]})
    package = zipfile.ZipFile(io.BytesIO(render_epub(document)))
    nav = ElementTree.fromstring(package.read("EPUB/nav.xhtml"))
    hrefs = [item.get("href") for item in nav.iter() if item.tag.endswith("a")]
    assert "chapter-001.xhtml#h1" in hrefs and "chapter-001.xhtml#h2" in hrefs
    chapter = ElementTree.fromstring(package.read("EPUB/chapter-001.xhtml"))
    assert {item.get("id") for item in chapter.iter() if item.get("id")} >= {"h1", "h2"}


@pytest.mark.parametrize("major", [2, 3])
def test_paddle_adapter_supports_old_and_new_api_without_model_downloads(monkeypatch, major):
    import sys
    import types
    import importlib.metadata
    import pymupdf
    from engine.ocr.engines import PaddleOcrEngine

    text = "إِنَّمَا الْأَعْمَالُ"
    polygon = [[1, 1], [25, 1], [25, 10], [1, 10]]
    class Array:
        def reshape(self, *args): return self
        def __getitem__(self, key): return self
        def copy(self): return self
    numpy = types.ModuleType("numpy")
    numpy.uint8 = "uint8"
    numpy.frombuffer = lambda *args, **kwargs: Array()
    paddle = types.ModuleType("paddleocr")
    class Adapter:
        def __init__(self, **kwargs): self.options = kwargs
        def predict(self, pixels): return [{"res": {"rec_texts": [text], "rec_scores": [0.95], "rec_polys": [polygon]}}]
        def ocr(self, pixels, cls=True): return [[[polygon, (text, 0.95)]]]
    paddle.PaddleOCR = Adapter
    monkeypatch.setitem(sys.modules, "numpy", numpy)
    monkeypatch.setitem(sys.modules, "paddleocr", paddle)
    monkeypatch.setattr(importlib.metadata, "version", lambda name: f"{major}.0.0")
    engine = PaddleOcrEngine()
    pdf = pymupdf.open()
    page = pdf.new_page(width=30, height=30)
    recognized = engine.recognize(page.get_pixmap().tobytes("png"))
    pdf.close()
    assert recognized.text == text
    assert recognized.mean_confidence == 0.95
