"""Script and direction detection (backlog M1-03, M1-04; ARABIC-ENGINE.md section 4).

Classifies text as Arabic / Latin / Mixed / Numeric / Neutral and infers
inline direction. Detection only observes; it never normalizes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.arabic.unicode import (
    is_arabic_letter,
    is_bidi_control,
    is_digit,
    is_latin_letter,
)
from engine.reflowdoc.models import Direction, ScriptClass


@dataclass
class ScriptProfile:
    """Letter-level composition of a text run."""

    arabic_letters: int = 0
    latin_letters: int = 0
    digits: int = 0
    neutral: int = 0  # punctuation, whitespace, symbols, bidi controls
    bidi_controls: int = 0

    @property
    def letters(self) -> int:
        return self.arabic_letters + self.latin_letters

    def classify(self) -> ScriptClass:
        """Dominant-script classification.

        Mixed requires at least one letter on each side; runs without letters
        but with digits are Numeric; otherwise Neutral.
        """
        if self.arabic_letters and self.latin_letters:
            return ScriptClass.MIXED
        if self.arabic_letters:
            return ScriptClass.ARABIC
        if self.latin_letters:
            return ScriptClass.LATIN
        if self.digits:
            return ScriptClass.NUMERIC
        return ScriptClass.NEUTRAL


def script_profile(text: str) -> ScriptProfile:
    profile = ScriptProfile()
    for ch in text:
        if is_arabic_letter(ch):
            profile.arabic_letters += 1
        elif is_latin_letter(ch):
            profile.latin_letters += 1
        elif is_digit(ch):
            profile.digits += 1
        else:
            profile.neutral += 1
            if is_bidi_control(ch):
                profile.bidi_controls += 1
    return profile


def classify_script(text: str) -> ScriptClass:
    """Classify a text run. Empty/whitespace-only text is Neutral."""
    return script_profile(text).classify()


def infer_direction(text: str) -> Direction | None:
    """First-strong direction (simplified UAX #9 rule P2/P3).

    Returns None for runs without a strong directional character, meaning
    direction must be inherited from the containing block.
    """
    for ch in text:
        if is_arabic_letter(ch):
            return Direction.RTL
        if is_latin_letter(ch):
            return Direction.LTR
    return None


@dataclass
class ScriptDecision:
    """Block-level classification with direction and per-part evidence."""

    script: ScriptClass
    dir: Direction | None
    profile: ScriptProfile = field(repr=False)

    @property
    def confidence(self) -> float:
        """Share of letters on the dominant side; low for genuinely mixed runs."""
        letters = self.profile.letters
        if letters == 0:
            return 0.0
        dominant = max(self.profile.arabic_letters, self.profile.latin_letters)
        return round(dominant / letters, 3)


def classify_block(text: str) -> ScriptDecision:
    """Classify a block of text and infer its base direction.

    Direction follows the first strong character of the whole block, which
    matches how the paragraph base direction is established in UAX #9.
    """
    profile = script_profile(text)
    return ScriptDecision(script=profile.classify(), dir=infer_direction(text), profile=profile)
