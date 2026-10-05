"""Analyzer tests against the fixture corpus (backlog M1-01)."""

from __future__ import annotations

import pymupdf
import pytest

from engine.analyzer.analyzer import analyze
from engine.analyzer.models import Classification


def test_indonesian_native_is_native_without_arabic(fixtures_dir) -> None:
    profile = analyze(fixtures_dir / "indonesian-native.pdf")
    assert profile.page_count == 1
    assert profile.classification is Classification.NATIVE
    assert profile.text_layer is True
    assert profile.image_dominant is False
    assert profile.arabic_detected is False
    assert profile.pages[0].has_text is True
    assert profile.encrypted is False


def test_arabic_native_detection(fixtures_dir) -> None:
    for name in ("arabic-native.pdf", "arabic-vocalized.pdf", "mixed-id-ar.pdf",
                 "arabic-numbers.pdf"):
        profile = analyze(fixtures_dir / name)
        assert profile.arabic_detected is True, name
        assert profile.classification is Classification.NATIVE, name


def test_scanned_pdf_has_no_text_layer(fixtures_dir) -> None:
    profile = analyze(fixtures_dir / "scanned.pdf")
    assert profile.classification is Classification.SCANNED
    assert profile.text_layer is False
    assert profile.image_dominant is True
    assert profile.pages[0].text_chars == 0
    assert profile.pages[0].image_count >= 1
    assert profile.scanned_pages == [1]


def test_hybrid_pdf_classified_hybrid(fixtures_dir) -> None:
    profile = analyze(fixtures_dir / "hybrid.pdf")
    assert profile.classification is Classification.HYBRID
    assert profile.text_layer is True  # half the pages carry a text layer
    assert profile.scanned_pages == [2]
    assert profile.pages[0].has_text is True
    assert profile.pages[1].has_text is False


def test_two_column_page_is_flagged(fixtures_dir) -> None:
    profile = analyze(fixtures_dir / "two-column.pdf")
    assert profile.likely_multicolumn_pages == [1]
    # single-column fixtures must not be flagged
    for name in ("indonesian-native.pdf", "mixed-id-ar.pdf"):
        other = analyze(fixtures_dir / name)
        assert other.likely_multicolumn_pages == [], name


def test_classification_confidence_present(fixtures_dir) -> None:
    profile = analyze(fixtures_dir / "hybrid.pdf")
    assert 0.0 < profile.classification_confidence < 1.0
    native = analyze(fixtures_dir / "indonesian-native.pdf")
    assert native.classification_confidence == 1.0


def test_problem_pages_include_scanned_and_multicolumn(fixtures_dir) -> None:
    hybrid = analyze(fixtures_dir / "hybrid.pdf")
    assert 2 in hybrid.candidate_problem_pages
    two_column = analyze(fixtures_dir / "two-column.pdf")
    assert 1 in two_column.candidate_problem_pages


def test_encrypted_pdf_is_reported_not_processed(tmp_path) -> None:
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

    profile = analyze(target)
    assert profile.encrypted is True
    assert profile.warnings[0].code == "ENCRYPTED_PDF"


def test_analysis_is_deterministic(fixtures_dir) -> None:
    a = analyze(fixtures_dir / "mixed-id-ar.pdf")
    b = analyze(fixtures_dir / "mixed-id-ar.pdf")
    assert a == b
