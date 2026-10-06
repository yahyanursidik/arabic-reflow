"""Semantic reconstruction into ReflowDoc (backlog M2/M6 wiring; ARCHITECTURE 3.9).

Consumes the ordered, script-annotated raw document plus the layout and
reading-order reports, and produces the canonical ReflowDocument: paragraphs,
headings, footnote candidates (M6-03), images with caption links and binary
resources (M6-05). All blocks live in a single ungrouped chapter until chapter
detection lands.
"""

from __future__ import annotations

import re

from engine.analyzer.models import DocumentProfile
from engine.arabic.detector import ScriptClass, classify_block, infer_direction
from engine.extraction.models import RawDocument, RawImage
from engine.language.detect import detect_language
from engine.layout.captions import find_captions
from engine.layout.footnotes import detect_footnote_candidates
from engine.layout.models import LayoutReport, OrderReport
from engine.layout.tables import SEMANTIC_CONFIDENCE, TableRegion, detect_tables
from engine.reflowdoc.models import (
    Chapter,
    Direction,
    FootnoteBlock,
    HeadingBlock,
    ImageBlock,
    ListItem,
    ListBlock,
    ParagraphBlock,
    QuoteBlock,
    ReflowDocument,
    ReflowWarning,
    Resource,
    SourceRef,
    SpanNode,
    TableBlock,
    TableCell,
    TextNode,
    new_block_id,
    new_document,
)
from engine.reconstruction.headings import body_font_size, detect_headings
from engine.reconstruction.lists import LIST_CONFIDENCE, ListRun, _marker_of, _strip_marker, detect_lists
from engine.reconstruction.paragraphs import ParagraphDraft, build_paragraphs, reference_width
from engine.reconstruction.quotes import QUOTE_CONFIDENCE, is_quote_draft

WARN_READING_ORDER_UNCERTAIN = "READING_ORDER_UNCERTAIN"
WARN_PARAGRAPH_MERGE_UNCERTAIN = "PARAGRAPH_MERGE_UNCERTAIN"
WARN_FURNITURE_REMOVED = "FURNITURE_REMOVED"
WARN_PAGE_NUMBERS_REMOVED = "PAGE_NUMBERS_REMOVED"
WARN_FOOTNOTE_UNCERTAIN = "FOOTNOTE_UNCERTAIN"
WARN_TABLE_FALLBACK_IMAGE = "TABLE_FALLBACK_IMAGE"
WARN_TABLE_DETECTED = "TABLE_DETECTED"

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


def _merge_list_items(run: ListRun) -> list[list[ParagraphDraft]]:
    """Group a run's drafts into item drafts, folding continuations in.

    detect_lists guarantees the run starts with a marker draft; a
    marker-less draft continues the item before it.
    """
    items: list[list[ParagraphDraft]] = []
    for draft in run.drafts:
        if _marker_of(draft.text) is None and items:
            items[-1].append(draft)
        else:
            items.append([draft])
    return items


def _table_page_renderer(source: str | bytes):
    """Render a page region to PNG for low-confidence table fallback (PRD 8.14)."""
    import pymupdf

    if isinstance(source, bytes):
        doc = pymupdf.open(stream=source, filetype="pdf")
    else:
        doc = pymupdf.open(source)

    def render(page_number: int, bbox: tuple[float, float, float, float]) -> bytes:
        page = doc[page_number - 1]
        pix = page.get_pixmap(clip=pymupdf.Rect(*bbox), dpi=150)
        return pix.tobytes("png")

    return render


def reconstruct_semantics(
    profile: DocumentProfile,
    raw: RawDocument,
    layout: LayoutReport,
    order: OrderReport,
    page_renderer=None,
) -> ReflowDocument:
    """Build the ReflowDocument from ordered raw pages.

    `page_renderer(page_number, bbox) -> png bytes` enables the PRD 8.14
    low-confidence table fallback (region rendered as image).
    """
    doc = new_document(raw.source_filename)
    # Book metadata: the PDF info dictionary is the honest source when present.
    if raw.pdf_title:
        doc.metadata.title = raw.pdf_title
    if raw.pdf_author:
        doc.metadata.author = [
            part.strip()
            for part in re.split(r"[,&]|\band\b", raw.pdf_author)
            if part.strip()
        ][:5]
    chapter = Chapter(id="chapter-001", title=None, level=1, blocks=[])
    sequence = 1
    footnote_pages: list[int] = []
    table_pages: list[int] = []
    fallback_tables: list[tuple[TableRegion, str]] = []

    def make_paragraph(
        draft: ParagraphDraft, dominant: ScriptClass, decision, lang: str,
        direction: Direction, confidence: float, warnings: list[str],
    ) -> ParagraphBlock:
        return ParagraphBlock(
            id=new_block_id(sequence),
            source=SourceRef(page=draft.page, bbox=list(draft.bbox)),
            lang=lang,
            script=decision.script,
            dir=direction,
            confidence=round(confidence, 3),
            warnings=warnings,
            content=_content_nodes(draft.runs, dominant, direction),
        )

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

        # Table detection (M6-06): cell-like blocks leave the text flow.
        table_regions = detect_tables(page.page, text_blocks, page.rule_segments)
        table_block_numbers: set[int] = {
            cell.block_number for region in table_regions for _, _, cell in region.cells
        }

        drafts = build_paragraphs(
            page.page, text_blocks, headings, gutter=layout.gutters.get(page.page),
            footnotes=footnotes,
        )
        if table_block_numbers:
            drafts = [
                d for d in drafts
                if not (d.block_numbers and set(d.block_numbers) <= table_block_numbers)
            ]

        # Quote geometry needs page-wide references (PRD 8.5: indentation).
        if text_blocks:
            page_x0 = min(b.bbox[0] for b in text_blocks)
            page_x1 = max(b.bbox[2] for b in text_blocks)
            ref_width = reference_width(text_blocks)
        else:
            page_x0 = page_x1 = ref_width = 0.0
        single_column = (
            layout.gutters.get(page.page) is None
            and page.page not in order.uncertain_pages
        )

        list_starts: dict[int, ListRun] = {start: run for start, run in detect_lists(drafts)}

        page_blocks: list[object] = []
        caption_block_ids: dict[int, str] = {}
        image_resources: list[Resource] = []

        draft_index = 0
        while draft_index < len(drafts):
            if draft_index in list_starts:
                run = list_starts[draft_index]
                run_warnings: list[str] = []
                items: list[ListItem] = []
                for item_drafts in _merge_list_items(run):
                    first = item_drafts[0]
                    marker = _marker_of(first.text) or ""
                    for extra in item_drafts[1:]:
                        first.runs.extend(extra.runs)
                        first.merged_block_count += 1
                    content_runs = _strip_marker(first, marker) if marker else first.runs
                    decision = classify_block(first.text)
                    dominant = _dominant_script(decision.script, decision.profile)
                    lang = detect_language(first.text).label
                    direction = decision.dir
                    item_block = ParagraphBlock(
                        id=new_block_id(sequence),
                        source=SourceRef(page=first.page, bbox=list(first.bbox)),
                        lang=lang,
                        script=decision.script,
                        dir=direction,
                        confidence=round(min(first.confidence, order.confidence.get(first.page, 1.0)), 3),
                        content=_content_nodes(content_runs, dominant, direction),
                    )
                    sequence += 1
                    items.append(ListItem(blocks=[item_block]))
                page_blocks.append(
                    ListBlock(
                        id=new_block_id(sequence),
                        lang=items[0].blocks[0].lang if items else None,
                        dir=items[0].blocks[0].dir if items else None,
                        confidence=LIST_CONFIDENCE,
                        warnings=run_warnings,
                        ordered=run.ordered,
                        items=items,
                    )
                )
                sequence += 1
                draft_index += len(run.drafts)
                continue

            draft = drafts[draft_index]
            draft_index += 1
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
                inner = make_paragraph(draft, dominant, decision, lang, direction, confidence, [])
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
            elif is_quote_draft(
                draft,
                page_x0=page_x0,
                page_x1=page_x1,
                ref_width=ref_width,
                single_column=single_column,
                is_caption=any(n in caption_numbers for n in draft.block_numbers),
            ):
                page_blocks.append(
                    QuoteBlock(
                        id=new_block_id(sequence),
                        source=source,
                        lang=lang,
                        script=decision.script,
                        dir=direction,
                        confidence=QUOTE_CONFIDENCE,
                        warnings=block_warnings,
                        subtype="arabic" if dominant is ScriptClass.ARABIC else None,
                        text=draft.text,
                    )
                )
            elif draft.runs:
                block = make_paragraph(draft, dominant, decision, lang, direction, confidence, block_warnings)
                for number in draft.block_numbers:
                    if number in caption_numbers:
                        caption_block_ids[number] = block.id
                page_blocks.append(block)
            else:
                continue
            sequence += 1

        for region in table_regions:
            table_pages.append(page.page)
            table_id = new_block_id(sequence)
            sequence += 1
            if region.confidence >= SEMANTIC_CONFIDENCE:
                rows: list[list[TableCell]] = []
                current_row: list[TableCell] = []
                current_row_index = 0
                for row, _col, cell_block in region.cells:
                    cell_decision = classify_block(cell_block.text)
                    if row != current_row_index and current_row:
                        rows.append(current_row)
                        current_row = []
                        current_row_index = row
                    current_row.append(
                        TableCell(
                            text=cell_block.text,
                            lang=detect_language(cell_block.text).label,
                            dir=cell_decision.dir,
                        )
                    )
                if current_row:
                    rows.append(current_row)
                page_blocks.append(
                    TableBlock(
                        id=table_id,
                        source=SourceRef(page=page.page, bbox=list(region.bbox)),
                        confidence=region.confidence,
                        rows=rows,
                    )
                )
            elif page_renderer is not None:
                content = page_renderer(page.page, region.bbox)
                resource = Resource(
                    id=f"table-p{page.page}-{len(fallback_tables) + 1}",
                    kind="image",
                    media_type="image/png",
                    filename=f"table-p{page.page}-{len(fallback_tables) + 1}.png",
                    source_page=page.page,
                    content=content,
                )
                image_resources.append(resource)
                fallback_tables.append((region, resource.id))
                page_blocks.append(
                    TableBlock(
                        id=table_id,
                        source=SourceRef(page=page.page, bbox=list(region.bbox)),
                        confidence=region.confidence,
                        rows=[],
                        fallback_resource_id=resource.id,
                    )
                )

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

    if table_pages:
        doc.warnings.append(
            ReflowWarning(
                code=WARN_TABLE_DETECTED,
                severity="info",
                message=f"Table grids detected on pages {sorted(set(table_pages))}.",
            )
        )
    for region, resource_id in fallback_tables:
        doc.warnings.append(
            ReflowWarning(
                code=WARN_TABLE_FALLBACK_IMAGE,
                severity="warning",
                message=(
                    f"Table on page {region.page} has low grid confidence "
                    f"({region.confidence}); rendered as image instead of "
                    "semantic markup."
                ),
                source_page=region.page,
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
