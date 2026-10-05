"""Arabic integrity reporting (backlog M3-06): block, page, and document health.

`attach_integrity` is the pipeline hook: it annotates ReflowDoc blocks that
carry Arabic with `arabic_integrity` metadata and surfaces low-confidence
blocks as explicit warnings. Source text is never modified.
"""

from __future__ import annotations

from engine.arabic.detector import ScriptClass
from engine.arabic.integrity import LEVEL_PROBLEM, inspect_text, level_of
from engine.arabic.unicode import is_arabic_letter
from engine.reflowdoc.models import (
    Chapter,
    ParagraphBlock,
    ReflowDocument,
    ReflowWarning,
    SpanNode,
)

WARN_LOW_ARABIC_CONFIDENCE = "LOW_ARABIC_CONFIDENCE"


def _block_text(block) -> str:
    if isinstance(block, ParagraphBlock):
        return block.text
    text = getattr(block, "text", None)
    return text if isinstance(text, str) else ""


def _mixed_isolated(block: ParagraphBlock) -> bool | None:
    """Whether a mixed block's minority script is span-isolated."""
    has_arabic = any(
        isinstance(node, SpanNode) and node.script is ScriptClass.ARABIC
        for node in block.content
    )
    text = block.text
    has_arabic_chars = any(is_arabic_letter(ch) for ch in text)
    has_latin = any(
        not isinstance(node, SpanNode)
        and any(ch.isascii() and ch.isalpha() for ch in node.text)
        for node in block.content
    )
    if has_arabic_chars and not has_latin:
        return None
    return has_arabic or not (has_arabic_chars and has_latin)


def inspect_block(block) -> tuple[object | None, list[str]]:
    """Integrity metadata + issue codes for one block, or (None, []) when the
    block carries no Arabic letters."""
    text = _block_text(block)
    if not any(is_arabic_letter(ch) for ch in text):
        return None, []
    isolated = (
        _mixed_isolated(block) if isinstance(block, ParagraphBlock) else None
    )
    return inspect_text(text, mixed_isolated=isolated)


def attach_integrity(document: ReflowDocument) -> ReflowDocument:
    """Annotate blocks and collect document-level warnings (in place)."""
    low_confidence_blocks: list[str] = []

    for chapter in document.chapters:
        for block in chapter.blocks:
            integrity, issues = inspect_block(block)
            if integrity is None:
                continue
            block.arabic_integrity = integrity
            if level_of(integrity.score) == LEVEL_PROBLEM:
                block.warnings.append(WARN_LOW_ARABIC_CONFIDENCE)
                low_confidence_blocks.append(block.id)

    if low_confidence_blocks:
        document.warnings.append(
            ReflowWarning(
                code=WARN_LOW_ARABIC_CONFIDENCE,
                severity="warning",
                message=(
                    "Arabic integrity is low on "
                    f"{len(low_confidence_blocks)} block(s); review recommended."
                ),
                block_ids=low_confidence_blocks,
            )
        )
    return document


def document_report(document: ReflowDocument) -> dict:
    """Aggregated health summary: document score, per-page rollup, issues."""
    blocks: list[tuple[str, int | None, float, list[str]]] = []
    for chapter in document.chapters:
        for block in chapter.blocks:
            integrity, issues = inspect_block(block)
            if integrity is None:
                continue
            page = block.source.page if block.source else None
            blocks.append((block.id, page, integrity.score, issues))

    score = (
        round(sum(b[2] for b in blocks) / len(blocks), 3) if blocks else None
    )
    pages: dict[int, list[float]] = {}
    for _, page, block_score, _ in blocks:
        if page is not None:
            pages.setdefault(page, []).append(block_score)
    return {
        "score": score,
        "level": level_of(score) if score is not None else None,
        "block_count": len(blocks),
        "page_scores": {
            page: round(sum(scores) / len(scores), 3)
            for page, scores in sorted(pages.items())
        },
        "low_confidence_block_ids": [
            b[0] for b in blocks if level_of(b[2]) == LEVEL_PROBLEM
        ],
        "issues": sorted({issue for b in blocks for issue in b[3]}),
    }
