"""Semantic reconstruction into ReflowDoc (backlog M2/M6 wiring; ARCHITECTURE 3.9).

Consumes the ordered, script-annotated raw document plus the layout and
reading-order reports, and produces the canonical ReflowDocument: paragraphs,
headings, footnote candidates (M6-03), images with caption links and binary
resources (M6-05). All blocks live in a single ungrouped chapter until chapter
detection lands.
"""

from __future__ import annotations

from engine.analyzer.models import DocumentProfile
from engine.arabic.detector import ScriptClass, classify_block, infer_direction
from engine.extraction.models import RawDocument, RawImage
from engine.language.detect import detect_language
from engine.layout.captions import find_captions
from engine.layout.footnotes import detect_footnote_candidates
from engine.layout.models import LayoutReport, OrderReport
from engine.reflowdoc.models import (
    Chapter,
    Direction,
    FootnoteBlock,
    HeadingBlock,
    ImageBlock,
    ParagraphBlock,
    ReflowDocument,
    ReflowWarning,
    Resource,
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
WARN_FOOTNOTE_UNCERTAIN = "FOOTNOTE_UNCERTAIN"

# Full-page rasters are scans (M5's domain), not figures worth keeping.
SCAN_IMAGE_COVERAGE = 0.85

_MEDIA_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
                     "image/bmp": "bmp", "image/webp": "webp"}


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


def _figure_images(page) -> list[RawImage]:
    """Page images that are figures, not full-page scans."""
    page_area = page.width * page.height
    figures = []
    for image in page.images:
        area = (image.bbox[2] - image.bbox[0]) * (image.bbox[3] - image.bbox[1])
        if page_area > 0 and area / page_area < SCAN_IMAGE_COVERAGE:
            figures.append(image)
    return figures


def _resource_for(image: RawImage, page_number: int, index: int) -> Resource:
    resource_id = f"img-p{page_number}-{index}"
    media_type = image.media_type or "image/png"
    extension = _MEDIA_EXTENSIONS.get(media_type, "png")
    return Resource(
        id=resource_id,
        kind="image",
        media_type=media_type,
        filename=f"{resource_id}.{extension}",
        source_page=page_number,
        content=image.content,
    )


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
    footnote_pages: list[int] = []

    for page in raw.pages:
        text_blocks = [
            b for b in page.blocks if b.type == "text" and b.text.strip()
        ]
        if not text_blocks and not page.images:
            continue

        body_size = body_font_size(text_blocks)
        headings = detect_headings(text_blocks, body_size)
        footnotes = detect_footnote_candidates(text_blocks, page.height, body_size)
        if footnotes:
            footnote_pages.append(page.page)
        images = _figure_images(page)
        captions = find_captions(images, text_blocks, body_size)
        caption_numbers = set(captions.values())

        drafts = build_paragraphs(
            page.page, text_blocks, headings, gutter=layout.gutters.get(page.page),
            footnotes=footnotes,
        )

        page_blocks: list[object] = []
        caption_block_ids: dict[int, str] = {}
        image_resources: list[Resource] = []

        for draft in drafts:
            decision = classify_block(draft.text)
            dominant = _dominant_script(decision.script, decision.profile)
            lang = detect_language(draft.text).label
            direction = decision.dir
            source = SourceRef(page=draft.page, bbox=list(draft.bbox))
            block_warnings: list[str] = []
            if (
                not draft.is_heading
                and draft.footnote_marker is None
                and draft.merged_block_count > 1
                and draft.confidence < 0.8
            ):
                block_warnings.append(WARN_PARAGRAPH_MERGE_UNCERTAIN)
            confidence = min(draft.confidence, order.confidence.get(draft.page, 1.0))

            if draft.footnote_marker is not None:
                inner = ParagraphBlock(
                    id=new_block_id(sequence),
                    source=source,
                    lang=lang,
                    script=decision.script,
                    dir=direction,
                    confidence=round(confidence, 3),
                    content=_content_nodes(draft.runs, dominant, direction),
                )
                sequence += 1
                page_blocks.append(
                    FootnoteBlock(
                        id=f"fn-p{draft.page}-{draft.footnote_marker}",
                        source=source,
                        lang=lang,
                        dir=direction,
                        confidence=round(confidence, 3),
                        marker=draft.footnote_marker,
                        blocks=[inner],
                    )
                )
                continue

            if draft.is_heading:
                page_blocks.append(
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
            elif draft.runs:
                block = ParagraphBlock(
                    id=new_block_id(sequence),
                    source=source,
                    lang=lang,
                    script=decision.script,
                    dir=direction,
                    confidence=round(confidence, 3),
                    warnings=block_warnings,
                    content=_content_nodes(draft.runs, dominant, direction),
                )
                for number in draft.block_numbers:
                    if number in caption_numbers:
                        caption_block_ids[number] = block.id
                page_blocks.append(block)
            else:
                continue
            sequence += 1

        for index, image in enumerate(images, start=1):
            resource = _resource_for(image, page.page, index)
            image_resources.append(resource)
            caption_id = caption_block_ids.get(captions.get(index - 1, -1))
            image_block = ImageBlock(
                id=new_block_id(sequence),
                source=SourceRef(page=page.page, bbox=list(image.bbox)),
                resource_id=resource.id,
                caption_block_id=caption_id,
            )
            sequence += 1
            insert_at = len(page_blocks)
            if caption_id:
                for position, block in enumerate(page_blocks):
                    if block.id == caption_id:
                        insert_at = position
                        break
            page_blocks.insert(insert_at, image_block)

        chapter.blocks.extend(page_blocks)
        doc.resources.extend(image_resources)

    doc.chapters = [chapter]

    if footnote_pages:
        doc.warnings.append(
            ReflowWarning(
                code=WARN_FOOTNOTE_UNCERTAIN,
                severity="info",
                message=(
                    "Footnote candidates detected on pages "
                    f"{sorted(set(footnote_pages))}; markers linked heuristically."
                ),
            )
        )

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

    from engine.arabic.report import attach_integrity

    return attach_integrity(doc)
