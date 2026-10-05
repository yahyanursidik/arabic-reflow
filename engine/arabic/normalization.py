"""Search normalization (ARABIC-ENGINE.md section 11).

Two concepts stay strictly separate:

- **source text** — used for the EPUB and the preview, never modified;
- **search-normalized text** — harakat stripped and presentation forms folded
  to core letters, for search/indexing ONLY.

Never replace the source with the search-normalized form.
"""

from __future__ import annotations

import unicodedata

from engine.arabic.unicode import is_combining_mark

TATWEEL = "\u0640"

# "normalize selected characters for search/indexing only" (section 11):
# alef variants fold to plain alef so words match regardless of hamza placement.
_ALEF_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})


def search_normalized(text: str) -> str:
    """Return a form for search/indexing only.

    NFKC folds presentation forms and ligatures to core letters, alef variants
    fold to plain alef, and combining marks plus tatweel are removed. Ordering
    matters: NFKC first, then folding and mark stripping.
    """
    folded = unicodedata.normalize("NFKC", text).translate(_ALEF_FOLD)
    return "".join(
        ch for ch in folded if not is_combining_mark(ch) and ch != TATWEEL
    )


def normalize_source_text(text: str) -> str:
    """NFKC-fold extraction artifacts while preserving every phonetic mark.

    This is the EXPLICIT user-approved normalization (never silent, never a
    default): presentation forms fold to core letters (ﻟ -> ل, ﷲ -> الله) and
    combining marks survive untouched, so harakat stay exactly as extracted.
    Callers must keep the original in source_text and record the
    'arabic_nfkc_normalization' transformation.
    """
    return unicodedata.normalize("NFKC", text)


def contains_arabic(text: str) -> bool:
    """Whether the text carries Arabic-block or presentation-form letters."""
    return any(
        0x0600 <= ord(ch) <= 0x06FF or 0xFB50 <= ord(ch) <= 0xFEFF for ch in text
    )
