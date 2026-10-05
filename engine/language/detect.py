"""Lightweight language labeling from extracted text.

Heuristic word-list matching, honest about uncertainty: it returns the label
plus the evidence it found so callers can keep confidence explicit.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.arabic.detector import ScriptClass, classify_script
from engine.arabic.unicode import is_arabic_char

# Small, high-precision function-word lists. Recall matters less than not
# mislabeling; anything inconclusive stays "unknown".
INDONESIAN_MARKERS = (
    "yang", "dan", "dari", "dengan", "untuk", "adalah", "ini", "itu",
    "tidak", "dalam", "pada", "akan", "dengan", "kita", "mereka", "saya",
    "para", "oleh", "juga", "atau", "bahwa", "sebagai",
)
ENGLISH_MARKERS = (
    "the", "and", "of", "in", "to", "is", "that", "with", "for", "as",
    "on", "was", "are", "this", "be", "from", "have", "has",
)


@dataclass
class LanguageDecision:
    label: str  # one of: id, ar, en, unknown
    marker_hits: int
    script: ScriptClass


def detect_language(text: str) -> LanguageDecision:
    stripped = text.strip()
    script = classify_script(stripped)

    if script is ScriptClass.ARABIC or (
        stripped and sum(1 for ch in stripped if is_arabic_char(ch)) > len(stripped) // 2
    ):
        return LanguageDecision(label="ar", marker_hits=0, script=script)

    tokens = [t.strip(".,;:!?()[]\"'\u2018\u2019\u201c\u201d").lower() for t in stripped.split()]
    tokens = [t for t in tokens if t]
    id_hits = sum(1 for t in tokens if t in INDONESIAN_MARKERS)
    en_hits = sum(1 for t in tokens if t in ENGLISH_MARKERS)

    if script is ScriptClass.MIXED:
        # Mixed runs are labeled by their Latin side; the Arabic part carries
        # its own span-level label in ReflowDoc.
        label = "id" if id_hits >= en_hits else "en"
        return LanguageDecision(label=label, marker_hits=max(id_hits, en_hits), script=script)
    if id_hits > en_hits:
        return LanguageDecision(label="id", marker_hits=id_hits, script=script)
    if en_hits > id_hits:
        return LanguageDecision(label="en", marker_hits=en_hits, script=script)
    return LanguageDecision(label="unknown", marker_hits=0, script=script)
