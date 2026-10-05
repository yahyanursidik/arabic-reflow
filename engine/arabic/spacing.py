"""Suspicious spacing detection (ARABIC-ENGINE.md section 7; backlog M3-03).

Flags extraction artifacts like "ا ل س ل ا م" — isolated Arabic letters
separated by spaces. Detection only: text is never auto-merged (merging
requires extremely high confidence and is not implemented in this milestone).
"""

from __future__ import annotations

from engine.arabic.unicode import is_arabic_letter, is_combining_mark

MIN_SUSPICIOUS_RUN = 3


def isolated_letter_runs(text: str) -> list[int]:
    """Lengths of consecutive whitespace-separated single-Arabic-letter tokens.

    A token counts as isolated when it holds exactly one Arabic letter and at
    most one combining mark (letter + optional haraka).
    """
    runs: list[int] = []
    current = 0
    for token in text.split():
        letters = [ch for ch in token if is_arabic_letter(ch)]
        marks = [ch for ch in token if is_combining_mark(ch)]
        if len(letters) == 1 and len(token) <= len(letters) + len(marks):
            current += 1
        else:
            if current:
                runs.append(current)
            current = 0
    if current:
        runs.append(current)
    return runs


def analyze_spacing(text: str) -> dict:
    """Return {suspicious, runs, longest_run, isolated_tokens}."""
    runs = isolated_letter_runs(text)
    longest = max(runs, default=0)
    return {
        "suspicious": longest >= MIN_SUSPICIOUS_RUN,
        "runs": len(runs),
        "longest_run": longest,
        "isolated_tokens": sum(runs),
    }
