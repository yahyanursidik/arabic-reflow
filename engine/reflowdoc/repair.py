"""Explicit, reversible repairs for known extraction/markup artifacts.

Never guess OCR words, merge spaced Arabic letters, or reverse source text.
"""
from __future__ import annotations

import unicodedata

from engine.arabic.detector import classify_script
from engine.epub.xml import xml_text
from engine.reflowdoc.editing import edited_content
from engine.reflowdoc.models import (
    Direction, HeadingBlock, InlineImageNode, ParagraphBlock, QuoteBlock, ScriptClass, SpanNode,
)

TEXT_TYPES = (ParagraphBlock, HeadingBlock, QuoteBlock)


def repair_text(text: str) -> tuple[str, list[str]]:
    # Fold compatibility letter forms independently so existing harakat are
    # not recomposed/reordered by whole-string Unicode normalization.
    letters = []
    for char in text:
        point = ord(char)
        folded = unicodedata.normalize("NFKC", char)
        presentation = 0xFB50 <= point <= 0xFDFF or 0xFE70 <= point <= 0xFEFF
        ligature = 0xFB00 <= point <= 0xFB06
        if ligature or (presentation and any(unicodedata.category(c).startswith("L") for c in folded)):
            letters.append(folded)
        else:
            letters.append(char)
    normalized = "".join(letters)
    clean = xml_text(normalized)
    changes = []
    if normalized != text:
        changes.append("compatibility_letter_forms")
    if clean != normalized:
        changes.append("invalid_xml_characters_removed")
    return clean, changes


def repair_block(block):
    """Return a repaired copy and whether it changed; keep provenance intact."""
    if not isinstance(block, TEXT_TYPES):
        raise ValueError("only paragraph, heading, and quote blocks support text repair")
    changed = block.model_copy(deep=True)
    if isinstance(changed, ParagraphBlock):
        nodes = []
        for node in changed.content:
            if isinstance(node, InlineImageNode):
                nodes.append(node)
                continue
            original = node.text
            node.text, changes = repair_text(original)
            if changes:
                node.source_text = node.source_text if node.source_text is not None else original
                node.transformations = list(dict.fromkeys([*node.transformations, *changes]))
            script = classify_script(node.text)
            if script is ScriptClass.MIXED:
                parts = edited_content(node.text)
                # Skip already-isolated mixed nodes only when no splitting is needed.
                for index, part in enumerate(parts):
                    part.transformations = list(dict.fromkeys([*node.transformations, "inline_bidi_isolation"]))
                    if index == 0:
                        part.source_text = node.source_text if node.source_text is not None else original
                nodes.extend(parts)
            else:
                if isinstance(node, SpanNode) and script is ScriptClass.ARABIC:
                    node.script, node.dir, node.lang = script, Direction.RTL, "ar"
                nodes.append(node)
        changed.content = nodes
    else:
        original = changed.text
        changed.text, changes = repair_text(original)
        if changes:
            changed.source_text = changed.source_text if changed.source_text is not None else original
            changed.transformations = list(dict.fromkeys([*changed.transformations, *changes]))
    # Never replace a source block with unreadable/empty output.
    if not changed.text.strip():
        return block.model_copy(deep=True), False
    script = classify_script(changed.text)
    if script is ScriptClass.ARABIC:
        changed.script, changed.dir, changed.lang = script, Direction.RTL, "ar"
    if changed.model_dump() == block.model_dump():
        return changed, False
    changed.modified_by_user = True
    changed.warnings = [code for code in changed.warnings if code != "SOURCE_VERIFIED"]
    if "AUTO_TEXT_REPAIRED" not in changed.warnings:
        changed.warnings.append("AUTO_TEXT_REPAIRED")
    return changed, True
