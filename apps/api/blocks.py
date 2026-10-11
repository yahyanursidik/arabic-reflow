"""User-approved per-block repair actions (review workflow, PRD section 10).

Three actions live here:

- **render as image** — crop the block's source region into a PNG and swap the
  block for an ImageBlock. Pixel-perfect fallback for Arabic the user judges
  too damaged to keep as text (same pattern as the PRD 8.14 table fallback,
  but opt-in per block and always reversible). Never a default.
- **restore text** — put the pre-render block back.
- **normalize Arabic (NFKC)** — fold presentation forms to core letters while
  preserving harakat, with the original kept in source_text.

Every action marks the block modified_by_user and records provenance.
"""

from __future__ import annotations

import pymupdf
from pydantic import BaseModel

from engine.arabic.normalization import normalize_source_text
from engine.reflowdoc.traversal import block_locations
from engine.reflowdoc.models import (
    Block,
    HeadingBlock,
    ImageBlock,
    InlineImageNode,
    ParagraphBlock,
    QuoteBlock,
    ReflowDocument,
    Resource,
    SourceRef,
)

WARN_RENDERED_AS_IMAGE = "ARABIC_RENDERED_AS_IMAGE"
NORMALIZATION_TRANSFORM = "arabic_nfkc_normalization"
RENDER_DPI = 200


class BlockNotFound(Exception):
    pass


class NoOriginalStored(Exception):
    pass


def _iter_block_locations(document: ReflowDocument):
    yield from block_locations(document)


def find_block(document: ReflowDocument, block_id: str) -> Block | None:
    for block_list, index in _iter_block_locations(document):
        if block_list[index].id == block_id:
            return block_list[index]
    return None


def _replace_block(document: ReflowDocument, block_id: str, replacement: Block) -> None:
    for block_list, index in _iter_block_locations(document):
        if block_list[index].id == block_id:
            block_list[index] = replacement
            return
    raise BlockNotFound(block_id)


def _editable_text_block(block: Block) -> bool:
    return isinstance(block, (ParagraphBlock, QuoteBlock)) or (
        hasattr(block, "text") and hasattr(block, "level")
    )


def render_block_as_image(
    storage, document_id: str, block_id: str, dpi: int = RENDER_DPI,
    *, block_ids: list[str] | None = None,
) -> ImageBlock:
    """Crop the block's source region and swap the block to an ImageBlock."""
    if block_ids is not None:
        return _render_group_as_image(storage, document_id, block_id, block_ids, dpi)
    document = ReflowDocument.model_validate(storage.read_reflow(document_id))
    block = find_block(document, block_id)
    if block is None:
        raise BlockNotFound(block_id)
    if block.source is None or block.source.bbox is None:
        raise ValueError(f"block {block_id} has no source geometry to render")
    if not _editable_text_block(block):
        raise ValueError(f"block type {block.type} cannot be rendered as an image")

    from engine.ocr.base import render_region_png

    source = pymupdf.open(storage.source_path(document_id))
    try:
        page = source.load_page(block.source.page - 1)
        # Padding expands until the edges are ink-free: real-world PDFs often
        # report bboxes tighter than the glyph ink, which clipped harakat.
        png = render_region_png(page, block.source.bbox, dpi=dpi)
    finally:
        source.close()

    resource = Resource(
        id=f"img-block-{block_id}",
        kind="image",
        media_type="image/png",
        filename=f"{block_id}.png",
        source_page=block.source.page,
        content=png,
    )
    document.resources.append(resource)

    original = storage.read_original_block(document_id, block_id)
    storage.write_original_block(
        document_id,
        block_id,
        {
            "block": original["block"] if original else block.model_dump(mode="json"),
            "resource_id": resource.id,
        },
    )

    image_block = ImageBlock(
        id=block.id,
        source=block.source,
        lang=block.lang,
        dir=block.dir,
        confidence=block.confidence,
        warnings=[*block.warnings, WARN_RENDERED_AS_IMAGE],
        modified_by_user=True,
        resource_id=resource.id,
        alt=block.text if isinstance(block, HeadingBlock) else None,
        caption_block_id=None,
        heading_level=block.level if isinstance(block, HeadingBlock) else None,
    )
    _replace_block(document, block_id, image_block)
    from engine.arabic.report import attach_integrity

    document = attach_integrity(document)
    storage.write_reflow(document_id, document)
    return image_block


def _render_group_as_image(storage, document_id, block_id, block_ids, dpi):
    """Preserve a fragmented source quotation as one reversible image.

    Require consecutive siblings on one PDF page. Separate crops of touching
    fragments can repeat glyphs or clip harakat at their shared boundaries.
    """
    requested = list(dict.fromkeys(block_ids))
    if not requested or requested[0] != block_id:
        raise ValueError("the image anchor must be the first requested block")
    document = ReflowDocument.model_validate(storage.read_reflow(document_id))
    locations = {blocks[index].id: (blocks, index) for blocks, index in _iter_block_locations(document)}
    if any(key not in locations for key in requested):
        raise BlockNotFound("requested block not found")
    siblings, start = locations[block_id]
    if [block.id for block in siblings[start:start + len(requested)]] != requested:
        raise ValueError("source image fragments must be consecutive siblings in reading order")
    selected = siblings[start:start + len(requested)]
    page_number = selected[0].source.page if selected[0].source else None
    if any(not _editable_text_block(block) or not block.source or not block.source.bbox
           or block.source.page != page_number for block in selected):
        raise ValueError("source image fragments must be editable text with geometry on the same page")
    bbox = [min(block.source.bbox[0] for block in selected),
            min(block.source.bbox[1] for block in selected),
            max(block.source.bbox[2] for block in selected),
            max(block.source.bbox[3] for block in selected)]
    from engine.ocr.base import render_region_png

    with pymupdf.open(storage.source_path(document_id)) as source:
        png = render_region_png(source.load_page(page_number - 1), bbox, dpi=dpi)
    resource = Resource(id=f"img-block-{block_id}", kind="image", media_type="image/png",
                        filename=f"{block_id}.png", source_page=page_number, content=png)
    originals = storage.read_originals(document_id)
    original_blocks = [originals.get(block.id, {}).get("block", block.model_dump(mode="json"))
                       for block in selected]
    # Fold previous per-fragment backups into the group so the earliest text,
    # including edits made before image conversion, remains recoverable.
    for key in requested:
        originals.pop(key, None)
    originals[block_id] = {"block": original_blocks[0], "blocks": original_blocks,
                          "resource_id": resource.id}
    heading_level = (selected[0].level if all(isinstance(block, HeadingBlock)
                    and block.level == selected[0].level for block in selected) else None)
    image_block = ImageBlock(
        id=block_id, source=SourceRef(page=page_number, bbox=bbox),
        lang=selected[0].lang, dir=selected[0].dir,
        confidence=None, warnings=[WARN_RENDERED_AS_IMAGE], modified_by_user=True,
        resource_id=resource.id,
        alt=(" ".join(block.text for block in selected) if heading_level is not None else
             f"Kutipan halaman PDF {page_number}; teks dan harakat dipertahankan sebagai gambar sumber."),
        heading_level=heading_level,
    )
    siblings[start:start + len(selected)] = [image_block]
    document.resources.append(resource)
    from engine.arabic.report import attach_integrity

    attach_integrity(document)
    storage._write_json(document_id, "originals.json", originals)
    storage.write_reflow(document_id, document)
    return image_block


def restore_block_text(storage, document_id: str, block_id: str) -> Block:
    """Put the pre-render block back and drop the render resource."""
    document = ReflowDocument.model_validate(storage.read_reflow(document_id))
    block = find_block(document, block_id)
    if block is None:
        raise BlockNotFound(block_id)

    original = storage.read_original_block(document_id, block_id)
    if original is None:
        raise NoOriginalStored(block_id)

    # Validate the stored block through a minimal document wrapper so the
    # discriminated block union resolves it back into the right model.
    wrapper = ReflowDocument.model_validate({
        "document_id": document.document_id,
        "chapters": [{"id": "restore-tmp", "blocks": original.get("blocks", [original["block"]])}],
    })
    restored_blocks = wrapper.chapters[0].blocks
    restored_ids = {items[index].id for items, index in _iter_block_locations(wrapper)}
    # A restored container replaces its current children as well. Their IDs
    # are not collisions; IDs elsewhere in the document still are.
    current_wrapper = ReflowDocument(chapters=[{"id": "current", "blocks": [block]}])
    replaced_ids = {items[index].id for items, index in _iter_block_locations(current_wrapper)}
    if any(block_list[index].id in restored_ids - replaced_ids
           for block_list, index in _iter_block_locations(document)):
        raise ValueError("cannot restore source fragments: a block id is already in use")
    for restored in restored_blocks:
        restored.modified_by_user = True

    for block_list, index in _iter_block_locations(document):
        if block_list[index].id == block_id:
            block_list[index:index + 1] = restored_blocks
            break
    render_resource_id = original.get("resource_id")
    document.resources = [
        r for r in document.resources if r.id != render_resource_id
    ]
    from engine.arabic.report import attach_integrity

    document = attach_integrity(document)
    storage.write_reflow(document_id, document)
    storage.delete_original_block(document_id, block_id)
    return restored_blocks[0]


def normalize_block_arabic(storage, document_id: str, block_id: str) -> Block:
    """NFKC-fold presentation forms to core letters; harakat are preserved.

    The original text is kept in source_text and the transformation is
    recorded — explicit user action, never silent.
    """
    document = ReflowDocument.model_validate(storage.read_reflow(document_id))
    block = find_block(document, block_id)
    if block is None:
        raise BlockNotFound(block_id)
    if not _editable_text_block(block):
        raise ValueError(f"block type {block.type} does not carry editable text")

    if storage.read_original_block(document_id, block_id) is None:
        storage.write_original_block(document_id, block_id, {"block": block.model_dump(mode="json")})

    if isinstance(block, ParagraphBlock):
        for node in block.content:
            if isinstance(node, InlineImageNode):
                continue
            normalized = normalize_source_text(node.text)
            if normalized != node.text:
                if node.source_text is None:
                    node.source_text = node.text
                node.text = normalized
                if NORMALIZATION_TRANSFORM not in node.transformations:
                    node.transformations.append(NORMALIZATION_TRANSFORM)
    else:
        normalized = normalize_source_text(block.text)
        if normalized != block.text:
            if getattr(block, "source_text", None) is None:
                block.source_text = block.text
            block.text = normalized
            if NORMALIZATION_TRANSFORM not in block.transformations:
                block.transformations.append(NORMALIZATION_TRANSFORM)

    block.modified_by_user = True
    block.warnings = [code for code in block.warnings if code != "SOURCE_VERIFIED"]

    from engine.arabic.report import attach_integrity

    document = attach_integrity(document)
    storage.write_reflow(document_id, document)
    return find_block(document, block_id)  # type: ignore[return-value]


def repair_blocks(storage, document_id: str, block_ids: list[str], *, skip_edited: bool = False) -> dict:
    """Repair requested blocks once, preserving the first pre-edit backup."""
    from engine.arabic.report import attach_integrity
    from engine.reflowdoc.repair import repair_block, TEXT_TYPES
    from engine.validation.reflow import quality_report

    document = ReflowDocument.model_validate(storage.read_reflow(document_id))
    locations = {blocks[index].id: (blocks, index) for blocks, index in block_locations(document)}
    requested = list(dict.fromkeys(block_ids))
    if any(block_id not in locations for block_id in requested):
        raise BlockNotFound("requested block not found")
    result = {"changed_block_ids": [], "unchanged_block_ids": [], "skipped_block_ids": []}
    originals = storage.read_originals(document_id)
    for block_id in requested:
        blocks, index = locations[block_id]
        block = blocks[index]
        if not isinstance(block, TEXT_TYPES) or (skip_edited and block.modified_by_user):
            result["skipped_block_ids"].append(block_id)
            continue
        repaired, changed = repair_block(block)
        if not changed:
            result["unchanged_block_ids"].append(block_id)
            continue
        originals.setdefault(block_id, {"block": block.model_dump(mode="json")})
        blocks[index] = repaired
        result["changed_block_ids"].append(block_id)
    if result["changed_block_ids"]:
        # Store backups first: a failed document write still leaves originals recoverable.
        storage._write_json(document_id, "originals.json", originals)
        attach_integrity(document)
        storage.write_reflow(document_id, document)
    review = set(quality_report(document)["review_block_ids"])
    result["review_block_ids"] = [block_id for block_id in requested if block_id in review]
    return result
