"""Arabic Unicode range knowledge (ARABIC-ENGINE.md section 5).

Pure predicates over single characters. No normalization is performed here.
"""

from __future__ import annotations

import unicodedata

# Core blocks
ARABIC_BLOCK = (0x0600, 0x06FF)
ARABIC_SUPPLEMENT = (0x0750, 0x077F)
ARABIC_EXTENDED_B = (0x0870, 0x089F)
ARABIC_EXTENDED_A = (0x08A0, 0x08FF)
ARABIC_PRESENTATION_A = (0xFB50, 0xFDFF)
ARABIC_PRESENTATION_B = (0xFE70, 0xFEFF)

ARABIC_BLOCKS = (
    ARABIC_BLOCK,
    ARABIC_SUPPLEMENT,
    ARABIC_EXTENDED_B,
    ARABIC_EXTENDED_A,
    ARABIC_PRESENTATION_A,
    ARABIC_PRESENTATION_B,
)

# Harakat and Qur'anic annotation ranges within/around the core block
HARAKAT = (0x064B, 0x065F)  # fathatan ... sukun (incl. shadda 0x0651)
SUPERSCRIPT_ALEF = 0x0670
QURANIC_ANNOTATION = (0x06D6, 0x06ED)
SMALL_VOWEL_SIGNS = (0x06E5, 0x06E6)

BIDI_CONTROLS = {0x200E, 0x200F, 0x061C, 0x202A, 0x202B, 0x202C, 0x2066, 0x2067, 0x2068, 0x2069}

# Latin letter ranges (basic + Latin-1 letters + Extended-A/B)
LATIN_RANGES = ((0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x00FF), (0x0100, 0x024F))


def _in_ranges(code: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= code <= end for start, end in ranges)


def is_arabic_char(ch: str) -> bool:
    """Any Arabic-block character, including marks and presentation forms."""
    return len(ch) == 1 and _in_ranges(ord(ch), ARABIC_BLOCKS)


def is_arabic_letter(ch: str) -> bool:
    """Arabic character that is a letter (not a combining mark or punctuation)."""
    return is_arabic_char(ch) and unicodedata.category(ch).startswith("L")


def is_latin_letter(ch: str) -> bool:
    return len(ch) == 1 and _in_ranges(ord(ch), LATIN_RANGES)


def is_haraka(ch: str) -> bool:
    """Vowel-sign combining marks, including shadda."""
    start, end = HARAKAT
    return len(ch) == 1 and start <= ord(ch) <= end


def is_quranic_annotation(ch: str) -> bool:
    start, end = QURANIC_ANNOTATION
    return (
        len(ch) == 1
        and (start <= ord(ch) <= end or ord(ch) == SUPERSCRIPT_ALEF or ord(ch) in SMALL_VOWEL_SIGNS)
    )


def is_presentation_form(ch: str) -> bool:
    """Presentation Forms A/B. Not an error by itself, but a common extraction
    artifact that must be surfaced (ARABIC-ENGINE.md section 5)."""
    return len(ch) == 1 and _in_ranges(ord(ch), (ARABIC_PRESENTATION_A, ARABIC_PRESENTATION_B))


def is_bidi_control(ch: str) -> bool:
    return len(ch) == 1 and ord(ch) in BIDI_CONTROLS


def is_digit(ch: str) -> bool:
    return len(ch) == 1 and unicodedata.category(ch) == "Nd"


def is_combining_mark(ch: str) -> bool:
    return len(ch) == 1 and unicodedata.category(ch).startswith("M")


def count_combining_marks(text: str) -> int:
    return sum(1 for ch in text if is_combining_mark(ch))


def count_harakat(text: str) -> int:
    return sum(1 for ch in text if is_haraka(ch))
