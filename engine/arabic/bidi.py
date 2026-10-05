"""BiDi diagnostics (ARABIC-ENGINE.md section 8; backlog M3-05).

Reports extraction/rendering risks around bidirectional text. Diagnostics
only: nothing is rewritten, and no bidi controls are added or removed here.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.arabic.detector import ScriptClass, script_profile
from engine.arabic.unicode import (
    is_arabic_char,
    is_bidi_control,
    is_presentation_form,
)

# Issue codes surfaced through ArabicIntegrity / ReflowDoc warnings.
BIDI_CONTROL_PRESENT = "BIDI_CONTROL_PRESENT"
PUNCTUATION_JUMP = "PUNCTUATION_JUMP"
UNISOLATED_MIXTURE = "UNISOLATED_MIXTURE"
DIGIT_ARABIC_PUNCT = "DIGIT_ARABIC_PUNCTUATION"

ARABIC_PUNCTUATION = "،؛؟۔"

SEVERE = "warning"
INFO = "info"


@dataclass
class BidiIssue:
    code: str
    severity: str
    detail: str


def _leading_punctuation_jumps(text: str) -> list[int]:
    """Lines whose first non-space character is sentence punctuation.

    The ':' extracted as its own line after an RTL paragraph is the canonical
    artifact: the punctuation jumped across the script boundary.
    """
    jumps: list[int] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped and stripped[0] in ".،؛؟۔:!?" and script_profile(stripped).letters == 0:
            jumps.append(line_number)
    return jumps


def analyze_bidi(text: str, mixed_isolated: bool | None = None) -> list[BidiIssue]:
    """Analyze a text run for bidi anomalies.

    mixed_isolated: whether Arabic/Latin mixtures in this content are carried
    by isolated spans (ReflowDoc SpanNodes). None means "unknown" and skips
    that check.
    """
    issues: list[BidiIssue] = []
    profile = script_profile(text)

    controls = sum(1 for ch in text if is_bidi_control(ch))
    if controls:
        issues.append(
            BidiIssue(
                code=BIDI_CONTROL_PRESENT,
                severity=INFO,
                detail=f"{controls} bidi control character(s) present",
            )
        )

    jumps = _leading_punctuation_jumps(text)
    if jumps:
        issues.append(
            BidiIssue(
                code=PUNCTUATION_JUMP,
                severity=SEVERE,
                detail=f"punctuation at line start on lines {jumps[:5]}",
            )
        )

    if (
        mixed_isolated is False
        and profile.arabic_letters > 0
        and profile.latin_letters > 0
    ):
        issues.append(
            BidiIssue(
                code=UNISOLATED_MIXTURE,
                severity=SEVERE,
                detail="mixed Arabic/Latin content without span isolation",
            )
        )

    digit_punct = sum(
        1
        for a, b in zip(text, text[1:])
        if (a.isdigit() and b in ARABIC_PUNCTUATION)
        or (a in ARABIC_PUNCTUATION and b.isdigit())
    )
    if digit_punct:
        issues.append(
            BidiIssue(
                code=DIGIT_ARABIC_PUNCT,
                severity=INFO,
                detail=f"{digit_punct} digit/Arabic-punctuation adjacency(ies)",
            )
        )
    return issues


def has_presentation_forms(text: str) -> bool:
    return any(is_presentation_form(ch) for ch in text)


def has_arabic(text: str) -> bool:
    return any(is_arabic_char(ch) for ch in text)


def mixture_isolated(script: ScriptClass | None, has_spans: bool) -> bool | None:
    """Isolation flag for the bidi check: only meaningful for mixed blocks."""
    if script is not ScriptClass.MIXED:
        return None
    return has_spans
