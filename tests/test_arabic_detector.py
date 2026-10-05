"""Script and direction detection tests (backlog M1-03, M1-04).

Covers the minimum Arabic-sensitive matrix from VIBE-CODING-INSTRUCTIONS.md:
Arabic without harakat, Arabic with harakat, mixed Indonesian + Arabic,
punctuation near Arabic, plus presentation forms and digits.
"""

from __future__ import annotations

import pytest

from engine.arabic.detector import classify_block, classify_script, infer_direction
from engine.arabic.unicode import (
    count_harakat,
    is_arabic_letter,
    is_haraka,
    is_presentation_form,
)
from engine.reflowdoc.models import Direction, ScriptClass

ARABIC_PLAIN = "بسم الله الرحمن الرحيم"
ARABIC_VOCALIZED = "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ"
ARABIC_PRESENTATION = "اﻟﻔﺎﺗﺤﺔ"  # what PyMuPDF extracts from shaped PDFs
MIXED_SENTENCE = "Hadits ini diriwayatkan dari أبي هريرة رضي الله عنه dalam Shahih Muslim."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (ARABIC_PLAIN, ScriptClass.ARABIC),
        (ARABIC_VOCALIZED, ScriptClass.ARABIC),
        (ARABIC_PRESENTATION, ScriptClass.ARABIC),
        ("أبي هريرة رضي الله عنه", ScriptClass.ARABIC),
        ("Hadits ini diriwayatkan", ScriptClass.LATIN),
        ("Pendahuluan", ScriptClass.LATIN),
        (MIXED_SENTENCE, ScriptClass.MIXED),
        ("Teks 123", ScriptClass.LATIN),
        ("12345", ScriptClass.NUMERIC),
        ("١٤٤٧", ScriptClass.NUMERIC),
        ("؟!.,؛«»", ScriptClass.NEUTRAL),
        ("", ScriptClass.NEUTRAL),
        ("   \n\t", ScriptClass.NEUTRAL),
    ],
)
def test_classify_script(text: str, expected: ScriptClass) -> None:
    assert classify_script(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (ARABIC_PLAIN, Direction.RTL),
        (ARABIC_VOCALIZED, Direction.RTL),
        (ARABIC_PRESENTATION, Direction.RTL),
        ("Hadits ini diriwayatkan", Direction.LTR),
        ("123 أبي هريرة", Direction.RTL),  # first strong character wins
        ("123 abc", Direction.LTR),
        ("12345", None),
        ("؛ ، ", None),
        ("", None),
    ],
)
def test_infer_direction(text: str, expected: Direction | None) -> None:
    assert infer_direction(text) is expected


def test_harakat_and_marks_are_not_letters() -> None:
    assert is_arabic_letter("ب")
    assert not is_arabic_letter("َ")  # fatha is a combining mark, not a letter
    assert is_haraka("َ")
    assert not is_haraka("ب")


def test_count_harakat_counts_each_combining_mark() -> None:
    # بِسْمِ = kasra, sukun, kasra
    assert count_harakat("بِسْمِ") == 3
    assert count_harakat(ARABIC_PLAIN) == 0


def test_presentation_forms_are_detected() -> None:
    assert is_presentation_form("ﷲ")  # Allah ligature, U+FDF2
    assert is_presentation_form("ﺑ")  # beh initial form, U+FE91
    assert not is_presentation_form("ب")


def test_block_decision_confidence_reflects_dominance() -> None:
    pure = classify_block(ARABIC_PLAIN)
    assert pure.script is ScriptClass.ARABIC
    assert pure.dir is Direction.RTL
    assert pure.confidence == 1.0

    mixed = classify_block(MIXED_SENTENCE)
    assert mixed.script is ScriptClass.MIXED
    assert mixed.dir is Direction.LTR  # Latin starts the sentence
    assert 0.0 < mixed.confidence < 1.0


def test_bidi_control_does_not_change_first_strong() -> None:
    rlm = "\u200f"
    assert infer_direction(rlm + ARABIC_PLAIN) is Direction.RTL
    assert classify_script(rlm + ARABIC_PLAIN) is ScriptClass.ARABIC
