"""Arabic integrity scoring (ARABIC-ENGINE.md section 10; backlog M3-06).

Weighted dimensions: valid Unicode coverage, suspicious-spacing rate,
presentation-form rate, combining-mark anomalies, bidi anomalies. The score
is a heuristic for review prioritization — avoid false precision in UI.
"""

from __future__ import annotations

import unicodedata

from engine.arabic.bidi import BidiIssue, analyze_bidi
from engine.arabic.combining_marks import analyze_combining_marks
from engine.arabic.detector import script_profile
from engine.arabic.spacing import analyze_spacing
from engine.arabic.unicode import (
    is_arabic_char,
    is_haraka,
    is_latin_letter,
    is_presentation_form,
)
from engine.reflowdoc.models import ArabicIntegrity

# Issue codes
PRESENTATION_FORMS_DETECTED = "PRESENTATION_FORMS_DETECTED"
UNUSUAL_CHARACTERS = "UNUSUAL_CHARACTERS"
SUSPICIOUS_SPACING = "SUSPICIOUS_SPACING"
COMBINING_MARK_ANOMALY = "COMBINING_MARK_ANOMALY"
BIDI_ANOMALY = "BIDI_ANOMALY"
REVERSED_ORDER_SUSPECTED = "REVERSED_ORDER_SUSPECTED"

# A correct Arabic word never begins with a combining mark; at or above this
# share of word-initial harakat the run is treated as glyph-order reversed.
_REVERSAL_RATE_THRESHOLD = 0.2

# Review levels (user-facing labels live in the UI; avoid false precision)
LEVEL_GOOD = "good"
LEVEL_REVIEW = "review_recommended"
LEVEL_PROBLEM = "problem_likely"

_GOOD_THRESHOLD = 0.85
_REVIEW_THRESHOLD = 0.6


def _letters(text: str) -> int:
    return sum(1 for ch in text if unicodedata.category(ch).startswith("L"))


def _unusual_letter_count(text: str) -> int:
    """Letters outside Arabic/Latin inside a predominantly Arabic run.

    The FiraGO-style reverse-mapping artifacts (ligature glyphs mapped to
    Georgian-range codepoints) land here.
    """
    count = 0
    for ch in text:
        if not unicodedata.category(ch).startswith("L"):
            continue
        if is_arabic_char(ch) or is_latin_letter(ch):
            continue
        count += 1
    return count


def _word_initial_mark_rate(text: str) -> float:
    """Share of Arabic-bearing words that begin with a harakat-range mark.

    A correct Arabic word never begins with a combining mark — but text whose
    glyphs were drawn in reverse order (a common producer-side artifact,
    e.g. text placed left-to-right glyph by glyph) ends marked words with
    their mark, so reversed words surface mark-initial. Only harakat-range
    marks count: Qur'anic annotation signs legitimately follow whitespace in
    some encodings and must not trigger this.
    """
    words = [word for word in text.split() if any(is_arabic_char(c) for c in word)]
    if not words:
        return 0.0
    initial = sum(1 for word in words if is_haraka(word[0]))
    return initial / len(words)


def inspect_text(text: str, mixed_isolated: bool | None = None) -> tuple[ArabicIntegrity, list[str]]:
    """Score an Arabic-bearing text run; returns (integrity, issue codes).

    Only meaningful for text that contains Arabic; callers decide when to run
    it. Score starts at 1.0 and accrues documented penalties.
    """
    issues: list[str] = []
    score = 1.0

    letters = _letters(text)
    arabic_letters = script_profile(text).arabic_letters

    presentation = sum(1 for ch in text if is_presentation_form(ch))
    presentation_rate = presentation / letters if letters else 0.0
    if presentation:
        issues.append(PRESENTATION_FORMS_DETECTED)
        score -= min(0.25, presentation_rate * 0.4)

    unusual = _unusual_letter_count(text)
    if unusual:
        issues.append(UNUSUAL_CHARACTERS)
        score -= min(0.3, 0.05 * unusual)

    spacing = analyze_spacing(text)
    if spacing["suspicious"]:
        issues.append(SUSPICIOUS_SPACING)
        score -= 0.25

    marks = analyze_combining_marks(text)
    if marks["orphans"]:
        issues.append(COMBINING_MARK_ANOMALY)
        score -= min(0.2, 0.05 * marks["orphans"])

    reversal_rate = _word_initial_mark_rate(text)
    reversed_suspected = reversal_rate >= _REVERSAL_RATE_THRESHOLD
    if reversed_suspected:
        issues.append(REVERSED_ORDER_SUSPECTED)
        # Severe: the run is not readable as-is. Floor the penalty at 0.3 so
        # even a thin signal lands below the problem threshold, and cap so one
        # artifact cannot zero out the rest of the report.
        score -= min(0.45, max(0.3, reversal_rate * 0.6))

    bidi_issues: list[BidiIssue] = analyze_bidi(text, mixed_isolated)
    for issue in bidi_issues:
        if issue.severity == "warning":
            issues.append(BIDI_ANOMALY)
            score -= 0.1

    score = max(0.0, min(1.0, score))

    integrity = ArabicIntegrity(
        score=round(score, 3),
        presentation_forms_detected=bool(presentation),
        suspicious_spacing=spacing["suspicious"],
        combining_mark_warnings=marks["orphans"],
        bidi_warning=any(i.severity == "warning" for i in bidi_issues),
        reversed_order_suspected=reversed_suspected,
    )
    return integrity, issues


def level_of(score: float) -> str:
    if score >= _GOOD_THRESHOLD:
        return LEVEL_GOOD
    if score >= _REVIEW_THRESHOLD:
        return LEVEL_REVIEW
    return LEVEL_PROBLEM
