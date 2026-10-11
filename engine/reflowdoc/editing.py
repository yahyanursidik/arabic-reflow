"""Preserve user text exactly while retaining mixed-script inline isolation."""

from __future__ import annotations

import unicodedata

from engine.arabic.detector import classify_script
from engine.arabic.unicode import is_arabic_letter, is_latin_letter
from engine.language.detect import detect_language
from engine.reflowdoc.models import (
    BlockBase, Direction, HeadingBlock, ImageBlock, InlineImageNode, ParagraphBlock, QuoteBlock,
    ReflowDocument, ScriptClass, SpanNode, TextNode,
)
from engine.reflowdoc.traversal import block_locations


def edited_content(text: str) -> list[TextNode | SpanNode]:
    if classify_script(text) is not ScriptClass.MIXED:
        return [TextNode(text=text)]
    runs: list[tuple[ScriptClass, str]] = []
    pending = ""
    for char in text:
        script = (
            ScriptClass.ARABIC if is_arabic_letter(char)
            else ScriptClass.LATIN if is_latin_letter(char) else None
        )
        if script is None:
            # Combining marks belong to the preceding letter, never to the
            # next script. Other neutral characters retain their source order.
            if runs and unicodedata.category(char).startswith("M"):
                kind, run = runs[-1]
                runs[-1] = (kind, run + pending + char)
                pending = ""
            else:
                pending += char
            continue
        if runs and runs[-1][0] is script:
            kind, run = runs[-1]
            runs[-1] = (kind, run + pending + char)
        else:
            runs.append((script, pending + char))
        pending = ""
    if pending:
        kind, run = runs[-1]
        runs[-1] = (kind, run + pending)
    return [
        SpanNode(
            text=run, script=script, lang=detect_language(run).label,
            dir=Direction.RTL if script is ScriptClass.ARABIC else Direction.LTR,
        )
        for script, run in runs
    ]


def update_semantic_block(block, *, text=None, lang=None, dir=None, type=None, level=None, alt=None):
    """Apply explicit user edits to a copy; never synthesize source content."""
    changed = block.model_copy(deep=True)
    if isinstance(block, ParagraphBlock) and any(isinstance(n, InlineImageNode) for n in block.content):
        if text is not None or (type is not None and type != "paragraph"):
            raise ValueError("Restore the original text before editing a paragraph containing source images")
    text_types = (ParagraphBlock, HeadingBlock, QuoteBlock)
    if type is not None:
        if type not in ("paragraph", "heading", "quote") or not isinstance(block, text_types):
            raise ValueError("only paragraph, heading, and quote blocks can change type")
        if type != block.type:
            common = block.model_dump(include=set(BlockBase.model_fields))
            if type == "paragraph":
                changed = ParagraphBlock(**common, content=edited_content(block.text))
            elif type == "heading":
                changed = HeadingBlock(**common, text=block.text, level=level or 2)
            else:
                changed = QuoteBlock(**common, text=block.text)
    if text is not None:
        if isinstance(changed, ParagraphBlock):
            changed.content = edited_content(text)
        elif isinstance(changed, (HeadingBlock, QuoteBlock)):
            changed.text = text
        else:
            raise ValueError(f"block type {changed.type} does not support text edits")
    if level is not None:
        if not isinstance(changed, HeadingBlock):
            raise ValueError("heading level is only valid for a heading")
        if not 1 <= level <= 6:
            raise ValueError("heading level must be between 1 and 6")
        changed.level = level
    if alt is not None:
        if not isinstance(changed, ImageBlock):
            raise ValueError("alternative text is only valid for an image")
        changed.alt = alt
    if lang is not None:
        changed.lang = lang
    if dir is not None:
        changed.dir = Direction(dir)
    changed.modified_by_user = True
    # Source review describes the previous content. Subsequent edits need a
    # fresh comparison; retain the original extraction confidence throughout.
    changed.warnings = [code for code in changed.warnings if code != "SOURCE_VERIFIED"]
    return changed


def move_block(document: ReflowDocument, block_id: str, direction: str):
    """Move within its own sibling group, without dropping/crossing content."""
    if direction not in ("up", "down"):
        raise ValueError("direction must be up or down")
    for blocks, index in block_locations(document):
        if blocks[index].id != block_id:
            continue
        destination = index - 1 if direction == "up" else index + 1
        if not 0 <= destination < len(blocks):
            raise ValueError("block is already at the boundary of this group")
        blocks[index], blocks[destination] = blocks[destination], blocks[index]
        blocks[destination].modified_by_user = True
        return blocks[destination]
    raise KeyError(block_id)
