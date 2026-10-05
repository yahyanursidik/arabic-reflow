"""Natural-language label tests (PRD 8.6: id, ar, en, unknown)."""

from __future__ import annotations

from engine.language.detect import detect_language


def test_indonesian_detected() -> None:
    decision = detect_language(
        "Para ulama sepakat bahwa niat adalah syarat sahnya ibadah dan harus dilakukan"
    )
    assert decision.label == "id"
    assert decision.marker_hits >= 3


def test_english_detected() -> None:
    decision = detect_language("The quick brown fox and the dog are here with that fox")
    assert decision.label == "en"


def test_arabic_detected_by_script() -> None:
    decision = detect_language("بسم الله الرحمن الرحيم")
    assert decision.label == "ar"
    assert decision.script.value == "Arabic"


def test_mixed_run_labeled_by_latin_side() -> None:
    decision = detect_language(
        "Hadits ini diriwayatkan dari أبي هريرة رضي الله عنه dalam Shahih Muslim."
    )
    assert decision.label == "id"


def test_empty_and_unknown_text() -> None:
    assert detect_language("").label == "unknown"
    assert detect_language("12345").label == "unknown"
    assert detect_language("xyzzy quux").label == "unknown"
