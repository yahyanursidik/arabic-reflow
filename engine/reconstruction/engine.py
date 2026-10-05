"""Semantic reconstruction into ReflowDoc (backlog M2 wiring; ARCHITECTURE 3.9).

Consumes the ordered, script-annotated raw document plus the layout and
reading-order reports, and produces the canonical ReflowDocument. All blocks
live in a single ungrouped chapter until chapter detection lands.
"""

from __future__ import annotations

from engine.analyzer.models import DocumentProfile
from engine.arabic.detector import ScriptClass, classify_block, infer_direction
from engine.extraction.models import RawDocument
from engine.language.detect import detect_language
from engine.layout.models import LayoutReport, OrderReport
from engine.reflowdoc.models import (
    Chapter,
    Direction,
    HeadingBlock,
    PageBreakBlock,
    ParagraphBlock,
    ReflowDocument,
    ReflowWarning,
    SourceRef,
    SpanNode,
    TextNode,
    new_block_id,
    new_document,
)
from engine.reconstruction.headings import body_font_size, detect_headings
from engine.reconstruction.paragraphs import build_paragraphs

WARN_READING_ORDER_UNCERTAIN = "READING_ORDER_UNCERTAIN"
WARN_PARAGRAPH_MERGE_UNCERTAIN = "PARAGRAPH_MERGE_UNCERTAIN"
WARN_FURNITURE_REMOVED = "FURNITURE_REMOVED"
WARN_PAGE_NUMBERS_REMOVED = "PAGE_NUMBERS_REMOVED"


def _dominant_script(script: ScriptClass, profile) -> ScriptClass:
    """For Mixed paragraphs, decide which script carries the primary text."""
    if script is ScriptClass.MIXED and profile is not None:
        if profile.arabic_letters > profile.latin_letters:
            return ScriptClass.ARABIC
        return ScriptClass.LATIN
    return script


def _content_nodes(draft_runs, dominant: ScriptClass, block_dir: Direction | None):
    """Map content runs to TextNode/SpanNode per the block's dominant script."""
    nodes: list[TextNode | SpanNode] = []
    for run in draft_runs:
        is_minority_script = run.script in (ScriptClass.ARABIC, ScriptClass.LATIN) and (
            run.script != dominant
        )
        if is_minority_script:
            decision = detect_language(run.text)
            nodes.append(
                SpanNode(
                    text=run.text,
                    lang=decision.label,
                    script=run.script,
                    dir=infer_direction(run.text) or block_dir,
                    source_text=run.source_text,
                    transformations=list(run.transformations),
                )
            )
        else:
            nodes.append(
                TextNode(
                    text=run.text,
                    source_text=run.source_text,
                    transformations=list(run.transformations),
                )
            )
    # Merge adjacent text nodes (numeric/neutral runs split them).
    merged: list[TextNode | SpanNode] = []
    for node in nodes:
        if (
            merged
            and isinstance(merged[-1], TextNode)
            and isinstance(node, TextNode)
        ):
            merged[-1].text += node.text
        else:
            merged.append(node)
    return merged


def reconstruct_semantics(
    profile: DocumentProfile,
    raw: RawDocument,
    layout: LayoutReport,
    order: OrderReport,
) -> ReflowDocument:
    """Build the ReflowDocument from ordered raw pages."""
    doc = new_document(raw.source_filename)
    chapter = Chapter(id="chapter-001", title=None, level=1, blocks=[])
    sequence = 1

    for page in raw.pages:
        text_blocks = [
            b for b in page.blocks if b.type == "text" and b.text.strip()
        ]
        if not text_blocks:
            continue

        body_size = body_font_size(text_blocks)
        headings = detect_headings(text_blocks, body_size)
        drafts = build_paragraphs(
            page.page, text_blocks, headings, gutter=layout.gutters.get(page.page)
        )

        for draft in drafts:
            decision = classify_block(draft.text)
            dominant = _dominant_script(decision.script, decision.profile)
            lang = detect_language(draft.text).label
            direction = decision.dir

            source = SourceRef(page=draft.page, bbox=list(draft.bbox))
            block_warnings: list[str] = []
            if not draft.is_heading and draft.merged_block_count > 1 and draft.confidence < 0.8:
                block_warnings.append(WARN_PARAGRAPH_MERGE_UNCERTAIN)
            confidence = min(draft.confidence, order.confidence.get(draft.page, 1.0))

            if draft.is_heading:
                chapter.blocks.append(
                    HeadingBlock(
                        id=new_block_id(sequence),
                        source=source,
                        lang=lang,
                        script=decision.script,
                        dir=direction,
                        confidence=round(confidence, 3),
                        warnings=block_warnings,
                        level=draft.heading_level or 1,
                        text=draft.text,
                    )
                )
            else:
                if not draft.runs:
                    continue
                chapter.blocks.append(
                    ParagraphBlock(
                        id=new_block_id(sequence),
                        source=source,
                        lang=lang,
                        script=decision.script,
                        dir=direction,
                        confidence=round(confidence, 3),
                        warnings=block_warnings,
                        content=_content_nodes(draft.runs, dominant, direction),
                    )
                )
            sequence += 1

    doc.chapters = [chapter]

    langs: list[str] = []
    for block in chapter.blocks:
        if block.lang not in langs:
            langs.append(block.lang)
        if isinstance(block, ParagraphBlock):
            for node in block.content:
                if isinstance(node, SpanNode) and node.lang not in langs:
                    langs.append(node.lang)
    doc.metadata.languages = [lang for lang in langs if lang != "unknown"]

    furniture_kinds = {item.kind for item in layout.removed_furniture}
    if "header" in furniture_kinds or "footer" in furniture_kinds:
        pages = sorted(
            {item.page for item in layout.removed_furniture
             if item.kind in ("header", "footer")}
        )
        doc.warnings.append(
            ReflowWarning(
                code=WARN_FURNITURE_REMOVED,
                severity="info",
                message=f"Repeated headers/footers removed on pages {pages}.",
            )
        )
    if layout.page_number_map:
        doc.warnings.append(
            ReflowWarning(
                code=WARN_PAGE_NUMBERS_REMOVED,
                severity="info",
                message=(
                    "Printed page numbers removed; provenance kept "
                    f"({len(layout.page_number_map)} pages mapped)."
                ),
            )
        )
    for page in order.uncertain_pages:
        doc.warnings.append(
            ReflowWarning(
                code=WARN_READING_ORDER_UNCERTAIN,
                severity="warning",
                message=(
                    "Page looks multi-column but no column structure could be "
                    "established; reading order may be wrong."
                ),
                source_page=page,
            )
        )
    return doc
