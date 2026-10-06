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

import unicodedata

import pymupdf
from pydantic import BaseModel

from engine.arabic.normalization import normalize_source_text
from engine.reflowdoc.models import (
    Block,
    ImageBlock,
    ParagraphBlock,
    QuoteBlock,
    ReflowDocument,
    Resource,
)

WARN_RENDERED_AS_IMAGE = "ARABIC_RENDERED_AS_IMAGE"
NORMALIZATION_TRANSFORM = "arabic_nfkc_normalization"
RENDER_DPI = 200


class BlockNotFound(Exception):
    pass


class NoOriginalStored(Exception):
    pass


def _iter_block_locations(document: ReflowDocument):
    """Yield (list, index) for every block, including footnote inner blocks."""
    for chapter in document.chapters:
        for index in range(len(chapter.blocks)):
            yield chapter.blocks, index
        for block in chapter.blocks:
            inner = getattr(block, "blocks", None)
            if inner:
                for inner_index in range(len(inner)):
                    yield inner, inner_index


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
    storage, document_id: str, block_id: str, dpi: int = RENDER_DPI
) -> ImageBlock:
    """Crop the block's source region and swap the block to an ImageBlock."""
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

    storage.write_original_block(
        document_id,
        block_id,
        {
            "block": block.model_dump(mode="json"),
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
        alt=None,
        caption_block_id=None,
    )
    _replace_block(document, block_id, image_block)
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
        "chapters": [{"id": "restore-tmp", "blocks": [original["block"]]}],
    })
    restored = wrapper.chapters[0].blocks[0]
    restored.modified_by_user = True

    _replace_block(document, block_id, restored)
    render_resource_id = original.get("resource_id")
    document.resources = [
        r for r in document.resources if r.id != render_resource_id
    ]
    storage.delete_original_block(document_id, block_id)
    storage.write_reflow(document_id, document)
    return restored


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

    if isinstance(block, ParagraphBlock):
        for node in block.content:
            normalized = unicodedata.normalize("NFKC", node.text)
            if normalized != node.text:
                if node.source_text is None:
                    node.source_text = node.text
                node.text = normalized
                if NORMALIZATION_TRANSFORM not in node.transformations:
                    node.transformations.append(NORMALIZATION_TRANSFORM)
    else:
        normalized = unicodedata.normalize("NFKC", block.text)
        if normalized != block.text:
            if getattr(block, "source_text", None) is None:
                block.source_text = block.text
            block.text = normalized
            if NORMALIZATION_TRANSFORM not in block.transformations:
                block.transformations.append(NORMALIZATION_TRANSFORM)

    block.modified_by_user = True

    from engine.arabic.report import attach_integrity

    document = attach_integrity(document)
    storage.write_reflow(document_id, document)
    return find_block(document, block_id)  # type: ignore[return-value]
