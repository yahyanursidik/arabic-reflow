"""Paragraph reconstruction (backlog M2-02) and Latin dehyphenation (M2-03).

Merging is deliberately conservative (PRD 8.8: avoid unsafe merging):

- lines inside one block are joined (extraction blocks are paragraph-like);
- a separate block continues the paragraph only when the accumulated
  paragraph's last line is full-width and lacks terminal punctuation, or
  when the candidate is a stray punctuation fragment;
- blocks in different columns never merge;
- Latin dehyphenation applies only with high confidence and preserves
  source_text provenance; Arabic is never dehyphenated.

Whitespace runs collapse to single spaces at line boundaries. Within a line,
span text is preserved verbatim — no character is altered. Presentation
forms, harakat, and extraction artifacts pass through untouched (M3 owns
explicit, provenance-preserving normalization).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from engine.arabic.detector import ScriptClass, script_profile
from engine.arabic.unicode import is_arabic_letter, is_latin_letter
from engine.extraction.models import RawBlock, RawLine

if TYPE_CHECKING:  # pragma: no cover
    from engine.reconstruction.headings import HeadingInfo

TERMINAL_PUNCTUATION = set(".?!…:;،؛؟۔")
# Punctuation that attaches to the preceding word without a space. Ambiguous
# quote characters are deliberately excluded: whether they need a preceding
# space depends on whether they open or close a quotation.
NO_SPACE_PUNCTUATION = set(".,;:!?…،؛؟)]}»›٪")
HYPHENS = "-\u00ad"  # hyphen-minus and soft hyphen
CONTINUATION_WIDTH = 0.55  # last line must span >= 55% of the reference width
SIZE_TOLERANCE = 1.0  # pt
COLUMN_GAP = 20.0  # pt; disjoint x-ranges mean different columns
_LATIN_CONTINUATION = re.compile(r"^[a-z\u00e0-\u024f]")


@dataclass
class ContentRun:
    """A same-script run of paragraph text, ready to become a content node."""

    script: ScriptClass
    text: str
    source_text: str | None = None
    transformations: list[str] = field(default_factory=list)


@dataclass
class ParagraphDraft:
    page: int
    bbox: tuple[float, float, float, float]
    runs: list[ContentRun]
    confidence: float
    merged_block_count: int = 1
    is_heading: bool = False
    heading_level: int | None = None
    footnote_marker: str | None = None
    block_numbers: list[int] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)


def _collapse(text: str) -> str:
    """Collapse whitespace runs to single spaces and strip the ends."""
    return " ".join(text.split())


def _starts_with_no_space_punct(text: str) -> bool:
    return bool(text) and text[0] in NO_SPACE_PUNCTUATION


def _ends_terminal(text: str) -> bool:
    stripped = text.rstrip()
    return bool(stripped) and stripped[-1] in TERMINAL_PUNCTUATION


def _split_mixed_run(text: str) -> list[tuple[ScriptClass, str]]:
    """Split a mixed-script run into per-script sub-runs.

    PyMuPDF can emit one span covering both scripts when the font is shared
    (e.g. 'Hadits ini dari أﺑﻲ ﻫ'). The Arabic/Latin letter runs must be
    separated so rendering can isolate them; digits and neutral characters
    attach to the letter run they follow (or the last one, at the end).
    """
    parts: list[tuple[ScriptClass, list[str]]] = []
    pending: list[str] = []
    for ch in text:
        if is_arabic_letter(ch):
            cls: ScriptClass | None = ScriptClass.ARABIC
        elif is_latin_letter(ch):
            cls = ScriptClass.LATIN
        else:
            pending.append(ch)
            continue
        if parts and parts[-1][0] == cls:
            parts[-1][1].extend(pending)
            parts[-1][1].append(ch)
        else:
            parts.append((cls, [*pending, ch]))
        pending = []
    if pending:
        if parts:
            parts[-1][1].extend(pending)
        else:
            parts.append((ScriptClass.NEUTRAL, pending))
    return [(cls, "".join(chars)) for cls, chars in parts]


def _line_runs(line: RawLine) -> list[tuple[ScriptClass, str]]:
    """Group a line's spans into same-script runs, splitting mixed spans."""
    grouped: list[tuple[ScriptClass, str]] = []
    for span in line.spans:
        if not span.text:
            continue
        cls = script_profile(span.text).classify()
        if cls is ScriptClass.MIXED:
            for sub_cls, sub_text in _split_mixed_run(span.text):
                if grouped and grouped[-1][0] == sub_cls:
                    grouped[-1] = (sub_cls, grouped[-1][1] + sub_text)
                else:
                    grouped.append((sub_cls, sub_text))
            continue
        if grouped and grouped[-1][0] == cls:
            grouped[-1] = (cls, grouped[-1][1] + span.text)
        else:
            grouped.append((cls, span.text))
    return grouped


def max_font_size(block: RawBlock) -> float:
    sizes = [span.size for line in block.lines for span in line.spans]
    return max(sizes) if sizes else 0.0


def block_runs(block: RawBlock) -> list[ContentRun]:
    """Flatten a block's lines into content runs, joining lines safely.

    Line boundaries are word boundaries, except when a Latin line ends with a
    hyphen: that triggers dehyphenation (kept only when confidence is high)
    with source_text provenance.
    """
    runs: list[ContentRun] = []
    lines = [line for line in block.lines if line.text.strip()]

    for line_index, line in enumerate(lines):
        continuing = line_index > 0
        appended_for_line = False
        for cls, raw_text in _line_runs(line):
            # The first content span of a line is its start, even when a
            # whitespace-only span precedes it (PyMuPDF emits those).
            at_line_start = not appended_for_line

            if not runs:
                first = _collapse(raw_text)
                if first:
                    runs.append(ContentRun(script=cls, text=first))
                    appended_for_line = True
                continue

            if at_line_start and continuing:
                text = _collapse(raw_text)
                if not text:
                    continue
                previous = runs[-1]
                if previous.text.endswith(tuple(HYPHENS)):
                    if (
                        cls is ScriptClass.LATIN
                        and _LATIN_CONTINUATION.match(text)
                        and re.search(r"[A-Za-z\u00c0-\u024f]-$", previous.text)
                    ):
                        # High-confidence Latin dehyphenation; keep provenance.
                        if previous.source_text is None:
                            previous.source_text = previous.text
                        previous.source_text += "\n" + text
                        previous.text = previous.text[:-1] + text
                        if "dehyphenation" not in previous.transformations:
                            previous.transformations.append("dehyphenation")
                        appended_for_line = True
                        continue
                    # Hyphen kept (compound word or low confidence): join
                    # directly without adding a space.
                elif not _starts_with_no_space_punct(text) and not previous.text.endswith(" "):
                    text = " " + text
            else:
                # Within one line: preserve span text verbatim.
                text = raw_text
                if not text:
                    continue

            previous = runs[-1]
            if previous.script == cls:
                previous.text += text
            else:
                runs.append(ContentRun(script=cls, text=text))
            appended_for_line = True
    return runs


def reference_width(blocks: list[RawBlock]) -> float:
    """Typical full text width on the page, from the extreme line edges."""
    xs0 = [line.bbox[0] for b in blocks for line in b.lines if line.text.strip()]
    xs1 = [line.bbox[2] for b in blocks for line in b.lines if line.text.strip()]
    if not xs0:
        return 0.0
    return max(xs1) - min(xs0)


def _last_line_width(block: RawBlock) -> float:
    lines = [line for line in block.lines if line.text.strip()]
    if not lines:
        return 0.0
    last = lines[-1]
    return max(0.0, last.bbox[2] - last.bbox[0])


class _Accumulator:
    def __init__(self, block: RawBlock, runs: list[ContentRun],
                 ref_width: float) -> None:
        self.bbox = block.bbox
        self.runs = runs
        self.ref_width = ref_width
        self.last_line_width = _last_line_width(block)
        self.last_size = max_font_size(block)
        self.merged = 1
        self.cross_block_merges = 0
        self.block_numbers = [block.number]

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)

    def absorb(self, block: RawBlock, runs: list[ContentRun], direct: bool) -> None:
        """Append another block's runs to this paragraph."""
        for offset, run in enumerate(runs):
            text = run.text
            if offset == 0 and not direct:
                joins_word = self.runs and self.runs[-1].text.endswith(tuple(HYPHENS))
                if (
                    not joins_word
                    and not _starts_with_no_space_punct(text)
                    and not (self.runs and self.runs[-1].text.endswith(" "))
                ):
                    text = " " + text
            if self.runs and self.runs[-1].script == run.script:
                target = self.runs[-1]
                target.text += text
                if run.source_text is not None:
                    target.source_text = (
                        (target.source_text + "\n" + run.source_text)
                        if target.source_text is not None
                        else run.source_text
                    )
                target.transformations = list(
                    dict.fromkeys(target.transformations + run.transformations)
                )
            else:
                if offset == 0 and text is not run.text and text.startswith(" "):
                    # Keep the join space on the dominant run, not the span.
                    self.runs[-1].text += " "
                    text = text[1:]
                self.runs.append(
                    ContentRun(
                        script=run.script,
                        text=text,
                        source_text=run.source_text,
                        transformations=list(run.transformations),
                    )
                )
        self.last_line_width = _last_line_width(block)
        self.last_size = max_font_size(block)
        self.merged += 1
        self.block_numbers.append(block.number)

    def absorb_fragment(self, block: RawBlock, runs: list[ContentRun]) -> None:
        self.absorb(block, runs, direct=True)


def build_paragraphs(
    page: int,
    blocks: list[RawBlock],
    headings: dict[int, "HeadingInfo"] | None = None,
    ref_width: float | None = None,
    gutter: float | None = None,
    footnotes: dict[int, str] | None = None,
) -> list[ParagraphDraft]:
    """Walk ordered blocks and produce paragraph/heading/footnote drafts.

    When a column gutter is supplied, continuation width is judged against the
    block's own column width (lines in a 220pt column must not be held to a
    480pt page standard), falling back to the page-wide reference for
    full-width blocks.
    """
    heading_map = headings or {}
    footnote_map = footnotes or {}
    if ref_width is None:
        ref_width = reference_width(blocks)

    def width_for(block: RawBlock) -> float:
        if gutter is None:
            return ref_width
        if block.bbox[2] < gutter:
            return _column_reference(blocks, lambda b: b.bbox[2] < gutter) or ref_width
        if block.bbox[0] > gutter:
            return _column_reference(blocks, lambda b: b.bbox[0] > gutter) or ref_width
        return ref_width

    drafts: list[ParagraphDraft] = []
    acc: _Accumulator | None = None
    previous_block: RawBlock | None = None

    def flush() -> None:
        nonlocal acc
        if acc is None:
            return
        confidence = 0.95 if not acc.cross_block_merges else 0.75
        drafts.append(
            ParagraphDraft(
                page=page,
                bbox=acc.bbox,
                runs=acc.runs,
                confidence=confidence,
                merged_block_count=acc.merged,
                block_numbers=list(acc.block_numbers),
            )
        )
        acc = None

    for block in blocks:
        runs = block_runs(block)
        text = "".join(run.text for run in runs).strip()
        if not text:
            previous_block = block
            continue

        if block.number in heading_map:
            flush()
            info = heading_map[block.number]
            drafts.append(
                ParagraphDraft(
                    page=page,
                    bbox=block.bbox,
                    runs=runs,
                    confidence=info.confidence,
                    is_heading=True,
                    heading_level=info.level,
                    block_numbers=[block.number],
                )
            )
            previous_block = block
            continue

        if block.number in footnote_map:
            flush()
            drafts.append(
                ParagraphDraft(
                    page=page,
                    bbox=block.bbox,
                    runs=runs,
                    confidence=0.7,
                    footnote_marker=footnote_map[block.number],
                    block_numbers=[block.number],
                )
            )
            previous_block = block
            continue

        if acc is None:
            acc = _Accumulator(block, runs, width_for(block))
            previous_block = block
            continue

        assert previous_block is not None
        same_column = not (
            block.bbox[0] > previous_block.bbox[2] + COLUMN_GAP
            or previous_block.bbox[0] > block.bbox[2] + COLUMN_GAP
        )
        letters = script_profile(text).letters
        size_compatible = abs(max_font_size(block) - acc.last_size) <= SIZE_TOLERANCE
        full_width_line = acc.last_line_width >= CONTINUATION_WIDTH * acc.ref_width
        non_terminal = not _ends_terminal(acc.text)

        if letters == 0:
            # Stray punctuation fragment attaches to the current paragraph.
            acc.absorb_fragment(block, runs)
        elif same_column and size_compatible and non_terminal and full_width_line:
            acc.absorb(block, runs, direct=False)
            acc.bbox = (
                min(acc.bbox[0], block.bbox[0]),
                acc.bbox[1],
                max(acc.bbox[2], block.bbox[2]),
                block.bbox[3],
            )
            acc.cross_block_merges += 1
        else:
            flush()
            acc = _Accumulator(block, runs, width_for(block))
        previous_block = block

    flush()
    return drafts


def _column_reference(
    blocks: list[RawBlock], belongs: "callable"
) -> float:
    """Reference width of one column's blocks (max x1 - min x0)."""
    xs0 = [
        line.bbox[0]
        for b in blocks
        if belongs(b)
        for line in b.lines
        if line.text.strip()
    ]
    xs1 = [
        line.bbox[2]
        for b in blocks
        if belongs(b)
        for line in b.lines
        if line.text.strip()
    ]
    if not xs0:
        return 0.0
    return max(xs1) - min(xs0)
