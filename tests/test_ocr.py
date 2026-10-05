"""OCR layer tests (backlog M5): registry, decisions, comparison, warnings.

Real PaddleOCR/Tesseract are not installed in the test environment; the
decision and comparison logic runs against a deterministic fake engine.
"""

from __future__ import annotations

import pytest

from engine.analyzer.analyzer import analyze
from engine.extraction.extractor import extract
from engine.extraction.models import RawBlock, RawLine, RawPage, RawSpan
from engine.ocr.base import OcrEngineUnavailable, OcrLine, OcrBox, OcrPage
from engine.ocr.decision import (
    apply_ocr,
    decide_pages,
    ocr_raw_page,
    prefer_candidate,
)
from engine.ocr.engines import available_engines, get_engine
from engine.pipeline import build_reflowdoc

CLEAN_ARABIC = "بسم الله الرحمن الرحيم"
CORRUPTED_ARABIC = "ا ل س ل ا م სტ სტ"


class FakeEngine:
    name = "fake"

    def __init__(self, text: str = CLEAN_ARABIC, confidence: float = 0.95) -> None:
        self.text = text
        self.confidence = confidence
        self.calls = 0

    def recognize(self, image: bytes, languages: list[str]) -> OcrPage:
        self.calls += 1
        width, height = 1240.0, 1754.0  # 150dpi A4
        words = [
            OcrBox(text=word, bbox=(60.0 + i * 100, 100, 150.0 + i * 100, 130),
                   confidence=self.confidence)
            for i, word in enumerate(self.text.split())
        ]
        line = OcrLine(bbox=(60.0, 100, 60.0 + 100 * len(words), 130), words=words)
        return OcrPage(page=0, width=width, height=height, lines=[line],
                       engine=self.name, mean_confidence=self.confidence)


# --- Registry (M5-02/03 adapters) --------------------------------------------------


def test_unknown_engine_rejected() -> None:
    with pytest.raises(OcrEngineUnavailable, match="unknown OCR engine"):
        get_engine("nonexistent")


def test_paddle_adapter_reports_missing_dependency() -> None:
    # paddle is intentionally not installed in the test environment
    if "paddle" in available_engines():
        pytest.skip("paddle unexpectedly available")
    with pytest.raises(OcrEngineUnavailable, match="ocr-paddle"):
        get_engine("paddle")


def test_tesseract_adapter_reports_missing_dependency() -> None:
    if "tesseract" in available_engines():
        pytest.skip("tesseract unexpectedly available")
    with pytest.raises(OcrEngineUnavailable, match="ocr-tesseract"):
        get_engine("tesseract")


# --- Decisions (M5-04) ---------------------------------------------------------------


def test_scanned_pages_go_to_ocr_native_pages_do_not(fixtures_dir) -> None:
    scanned_profile = analyze(fixtures_dir / "scanned.pdf")
    scanned_raw = extract(fixtures_dir / "scanned.pdf")
    decisions = decide_pages(scanned_profile, scanned_raw)
    assert [(d.use_ocr, d.reason) for d in decisions] == [(True, "no_text_layer")]

    native_profile = analyze(fixtures_dir / "indonesian-native.pdf")
    native_raw = extract(fixtures_dir / "indonesian-native.pdf")
    assert all(not d.use_ocr for d in decide_pages(native_profile, native_raw))


def test_hybrid_only_scanned_page_flagged(fixtures_dir) -> None:
    profile = analyze(fixtures_dir / "hybrid.pdf")
    raw = extract(fixtures_dir / "hybrid.pdf")
    decisions = decide_pages(profile, raw)
    assert [d.use_ocr for d in decisions] == [False, True]


# --- Synthesis and comparison (M5-06) -------------------------------------------------


def test_ocr_raw_page_synthesizes_raw_model(fixtures_dir) -> None:
    engine = FakeEngine()
    ocr_page, raw_page = ocr_raw_page(fixtures_dir / "scanned.pdf", 1, engine)
    assert engine.calls == 1
    assert raw_page.page == 1
    assert raw_page.blocks, "fake engine text becomes raw blocks"
    assert raw_page.blocks[0].lines[0].spans[0].font == "OcrSynthesized"
    assert CLEAN_ARABIC in raw_page.text
    # coordinates scaled back into PDF points
    assert raw_page.width == pytest.approx(595, abs=1)
    for block in raw_page.blocks:
        assert block.bbox[2] <= raw_page.width + 1


def _native_page(text: str) -> RawPage:
    bbox = (60, 100, 500, 130)
    return RawPage(
        page=1, width=595, height=842,
        blocks=[RawBlock(number=1, type="text", bbox=bbox,
                         lines=[RawLine(bbox=bbox,
                                        spans=[RawSpan(text=text, font="F", size=11,
                                                       bbox=bbox)])])],
    )


def test_corrupted_native_arabic_loses_to_clean_ocr() -> None:
    native = _native_page(CORRUPTED_ARABIC)
    engine = FakeEngine(CLEAN_ARABIC)
    ocr_page = engine.recognize(b"", [])
    ocr_raw = _native_page(CLEAN_ARABIC)
    chosen, reason = prefer_candidate(native, ocr_page, ocr_raw)
    assert chosen is ocr_raw
    assert reason == "ocr_higher_integrity"


def test_healthy_native_arabic_beats_ocr() -> None:
    native = _native_page(CLEAN_ARABIC)
    engine = FakeEngine(CORRUPTED_ARABIC)
    ocr_page = engine.recognize(b"", [])
    ocr_raw = _native_page(CORRUPTED_ARABIC)
    chosen, reason = prefer_candidate(native, ocr_page, ocr_raw)
    assert chosen is native
    assert reason == "native_kept_higher_integrity"


def test_non_arabic_page_keeps_native_extraction() -> None:
    native = _native_page("Kalimat Indonesia biasa tanpa Arab.")
    engine = FakeEngine(CLEAN_ARABIC)
    ocr_page = engine.recognize(b"", [])
    chosen, reason = prefer_candidate(native, ocr_page, _native_page(CLEAN_ARABIC))
    assert chosen is native
    assert reason == "native_kept_no_arabic_comparison"


# --- Pipeline wiring (M5-05) -----------------------------------------------------------


def test_pipeline_with_ocr_engine_recovers_scanned_page(fixtures_dir) -> None:
    result = build_reflowdoc(fixtures_dir / "scanned.pdf", ocr_engine=FakeEngine())
    blocks = [b for c in result.document.chapters for b in c.blocks]
    assert blocks, "OCR text flows into ReflowDoc"
    codes = [w.code for w in result.document.warnings]
    assert "OCR_USED" in codes

    result_no_ocr = build_reflowdoc(fixtures_dir / "scanned.pdf")
    assert [b for c in result_no_ocr.document.chapters for b in c.blocks] == []


def test_low_confidence_ocr_warns(fixtures_dir) -> None:
    result = build_reflowdoc(
        fixtures_dir / "scanned.pdf", ocr_engine=FakeEngine(confidence=0.4)
    )
    codes = [w.code for w in result.document.warnings]
    assert "OCR_LOW_CONFIDENCE" in codes


def test_ocr_input_document_unchanged(fixtures_dir) -> None:
    raw = extract(fixtures_dir / "scanned.pdf")
    before = raw.model_dump_json()
    apply_ocr(fixtures_dir / "scanned.pdf", analyze(fixtures_dir / "scanned.pdf"),
              raw, FakeEngine())
    assert raw.model_dump_json() == before
