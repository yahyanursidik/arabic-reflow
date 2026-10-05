"""Combining-mark checks (ARABIC-ENGINE.md section 6; backlog M3-04).

Harakat preservation is tracked, never altered: counts, orphan marks (marks
without a base letter), and shadda / Qur'anic annotation presence.
"""

from __future__ import annotations

from engine.arabic.unicode import (
    count_combining_marks,
    count_harakat,
    is_combining_mark,
    is_quranic_annotation,
)

SHADDA = "\u0651"


def analyze_combining_marks(text: str) -> dict:
    """Return {combining_marks, harakat, shadda, quranic_annotations, orphans}.

    Orphan marks are combining marks at the very start of the text or directly
    after whitespace — evidence of a detached base letter in extraction.
    """
    orphans = 0
    for index, ch in enumerate(text):
        if not is_combining_mark(ch):
            continue
        if index == 0 or text[index - 1].isspace():
            orphans += 1
    return {
        "combining_marks": count_combining_marks(text),
        "harakat": count_harakat(text),
        "shadda": text.count(SHADDA),
        "quranic_annotations": sum(1 for ch in text if is_quranic_annotation(ch)),
        "orphans": orphans,
    }
