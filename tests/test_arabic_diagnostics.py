"""Suspicious spacing, combining-mark, and BiDi diagnostics (M3-03/04/05)."""

from __future__ import annotations

from engine.arabic.bidi import analyze_bidi
from engine.arabic.combining_marks import analyze_combining_marks
from engine.arabic.spacing import analyze_spacing

# --- Spacing (M3-03) -----------------------------------------------------------


def test_isolated_letter_run_detected() -> None:
    analysis = analyze_spacing("ا ل س ل ا م عليكم")
    assert analysis["suspicious"] is True
    assert analysis["longest_run"] == 6
    assert analysis["isolated_tokens"] == 6


def test_normal_arabic_not_flagged() -> None:
    analysis = analyze_spacing("بسم الله الرحمن الرحيم")
    assert analysis["suspicious"] is False
    assert analysis["longest_run"] < 3


def test_short_runs_not_suspicious() -> None:
    # two isolated letters in a row is not enough evidence
    assert analyze_spacing("ا ل bismillah")["suspicious"] is False


def test_vocalized_isolated_letters() -> None:
    # letter + haraka tokens still count as isolated letters
    analysis = analyze_spacing("بِ سْ مِ اللَّهِ")
    assert analysis["suspicious"] is True


# --- Combining marks (M3-04) ---------------------------------------------------


def test_harakat_and_shadda_counted() -> None:
    analysis = analyze_combining_marks("إِنَّمَا الْأَعْمَالُ")
    assert analysis["harakat"] > 0
    assert analysis["shadda"] >= 1
    assert analysis["orphans"] == 0


def test_quranic_annotation_counted() -> None:
    analysis = analyze_combining_marks("الرَّحْمَٰنِ")
    assert analysis["quranic_annotations"] >= 1


def test_orphan_marks_detected() -> None:
    # mark directly after a space: base letter is missing
    analysis = analyze_combining_marks("السلام َعليكم")
    assert analysis["orphans"] == 1
    assert analyze_combining_marks("بسم الله")["orphans"] == 0


# --- BiDi (M3-05) ----------------------------------------------------------------


def test_punctuation_jump_detected() -> None:
    # the ':' extracted as its own line after an RTL paragraph
    issues = analyze_bidi("اﻟﺪﻳﻦ، أﻣﺎ ﺑﻌﺪ\n:")
    codes = [i.code for i in issues]
    assert "PUNCTUATION_JUMP" in codes
    assert any(i.severity == "warning" for i in issues)


def test_unisolated_mixture_detected() -> None:
    issues = analyze_bidi("Hadits ini diriwayatkan dari أبي هريرة dalam Muslim",
                          mixed_isolated=False)
    assert "UNISOLATED_MIXTURE" in [i.code for i in issues]


def test_isolated_mixture_clean() -> None:
    issues = analyze_bidi("Hadits ini diriwayatkan dari أبي هريرة dalam Muslim",
                          mixed_isolated=True)
    assert "UNISOLATED_MIXTURE" not in [i.code for i in issues]


def test_bidi_controls_reported_as_info() -> None:
    issues = analyze_bidi("\u200fبسم الله")
    control = next(i for i in issues if i.code == "BIDI_CONTROL_PRESENT")
    assert control.severity == "info"


def test_clean_arabic_has_no_severe_issues() -> None:
    issues = analyze_bidi("بسم الله الرحمن الرحيم", mixed_isolated=None)
    assert all(i.severity == "info" for i in issues)
