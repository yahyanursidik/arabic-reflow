"""List detection (PRD 8.10 structural reconstruction).

Groups consecutive marker-initial drafts into one ListBlock. Conservative:
at least two marker items must appear in a run, headings/footnotes never
join, and a marker-less draft only continues the previous item when it
starts lowercase and the item has no terminal punctuation yet.

The marker itself is removed from the item text (EPUB <ol>/<ul> numbering
would otherwise double it) with provenance: the affected run keeps its
source_text and gains the "list_marker_removed" transformation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from engine.reconstruction.paragraphs import ContentRun

if TYPE_CHECKING:  # pragma: no cover
    from engine.reconstruction.paragraphs import ParagraphDraft

LIST_CONFIDENCE = 0.8
MIN_ITEMS = 2
MARKER_REMOVED = "list_marker_removed"

# Bullet glyphs, dash bullets, then "1." / "1)" style markers (ASCII and
# Arabic-Indic digits). The marker must be followed by whitespace.
_LIST_MARKER = re.compile(
    r"^(?:[•‣▪◦●○*·]|[-–—]|[0-9]{1,2}|[٠-٩]{1,2})[.)]?\s+"
)
_ORDERED = re.compile(r"^(?:[0-9]{1,2}|[٠-٩]{1,2})[.)]\s+")


@dataclass
class ListRun:
    """A consecutive run of drafts forming one list."""

    drafts: list["ParagraphDraft"] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)

    @property
    def ordered(self) -> bool:
        numeric = sum(1 for marker in self.markers if _ORDERED.match(marker))
        return numeric * 2 > len(self.markers)


def _marker_of(text: str) -> str | None:
    match = _LIST_MARKER.match(text)
    if match is None:
        return None
    marker = match.group(0)
    # A dash only counts when it is a bullet-looking short marker: real prose
    # dashes are attached to surrounding words, ours is followed by a space
    # and the marker regex already requires that.
    return marker


def _strip_marker(draft: "ParagraphDraft", marker: str) -> list[ContentRun]:
    """Copy the draft runs minus the leading marker, keeping provenance.

    Runs fully covered by the marker are dropped (the list structure itself
    documents the marker); a partially covered run keeps the pre-transform
    text as its source_text and gains the list_marker_removed transformation.
    """
    remaining = len(marker)
    runs: list[ContentRun] = []
    for run in draft.runs:
        if remaining <= 0:
            runs.append(run)
            continue
        take = min(len(run.text), remaining)
        rest = run.text[take:]
        remaining -= take
        if not rest:
            continue
        runs.append(
            ContentRun(
                script=run.script,
                text=rest,
                source_text=run.source_text if run.source_text else run.text,
                transformations=[*run.transformations, MARKER_REMOVED],
            )
        )
    return [run for run in runs if run.text]


def detect_lists(drafts: list["ParagraphDraft"]) -> list[tuple[int, ListRun]]:
    """Return [(start_index, ListRun)] for marker runs of >= MIN_ITEMS.

    Headings and footnotes break a run; a run ends at the first draft that
    neither carries a marker nor qualifies as a lowercase continuation.
    """
    results: list[tuple[int, ListRun]] = []
    index = 0
    while index < len(drafts):
        draft = drafts[index]
        marker = (
            _marker_of(draft.text)
            if not draft.is_heading and draft.footnote_marker is None
            else None
        )
        if marker is None:
            index += 1
            continue
        run = ListRun(drafts=[draft], markers=[marker])
        end = index + 1
        while end < len(drafts):
            candidate = drafts[end]
            if candidate.is_heading or candidate.footnote_marker is not None:
                break
            candidate_marker = _marker_of(candidate.text)
            if candidate_marker is not None:
                run.drafts.append(candidate)
                run.markers.append(candidate_marker)
                end += 1
                continue
            # Marker-less continuation: lowercase start, item still open.
            prev = run.drafts[-1]
            if (
                candidate.text
                and candidate.text[0].islower()
                and not _ends_terminal(prev.text)
            ):
                run.drafts.append(candidate)
                run.markers.append("")
                end += 1
                continue
            break
        if len(run.drafts) >= MIN_ITEMS:
            results.append((index, run))
            index = end
        else:
            index += 1
    return results


def _ends_terminal(text: str) -> bool:
    stripped = text.rstrip()
    return bool(stripped) and stripped[-1] in ".?!…:;،؛؟۔"
