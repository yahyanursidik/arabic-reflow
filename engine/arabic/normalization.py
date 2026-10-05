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
