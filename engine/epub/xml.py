"""XML 1.0 output safety, without changing canonical/source document text."""

from __future__ import annotations

from collections import Counter
from xml.sax.saxutils import escape as _escape, quoteattr as _quoteattr

from engine.reflowdoc.models import ReflowDocument
from engine.reflowdoc.traversal import iter_blocks

WARN_XML_CHARACTERS = "XML_INVALID_CHARACTERS"


def valid_xml_character(char: str) -> bool:
    return (
        char in "\t\n\r"
        or "\x20" <= char <= "\ud7ff"
        or "\ue000" <= char <= "\ufffd"
        or "\U00010000" <= char <= "\U0010ffff"
    )


def xml_text(text: str) -> str:
    """Exclude unrepresentable codepoints only at the XML output boundary.

    Arabic letters, harakat, whitespace and all other valid XML characters
    retain their exact order. Callers surface exclusions via output_diagnostics.
    """
    return "".join(char for char in text if valid_xml_character(char))


def escape(text: str) -> str:
    return _escape(xml_text(text))


def quoteattr(text: str) -> str:
    return _quoteattr(xml_text(text))


def output_diagnostics(document: ReflowDocument) -> dict:
    """Report rendered fields containing illegal XML characters; no mutations."""
    counts: Counter[str] = Counter()
    affected = []
    metadata_fields = []

    def inspect(text):
        found = Counter(f"U+{ord(char):04X}" for char in text if not valid_xml_character(char))
        counts.update(found)
        return bool(found)

    if inspect(document.metadata.title):
        metadata_fields.append("title")
    for index, author in enumerate(document.metadata.author):
        if inspect(author):
            metadata_fields.append(f"author[{index}]")
    for index, chapter in enumerate(document.chapters):
        if inspect(chapter.title or ""):
            metadata_fields.append(f"chapters[{index}].title")
    for block in iter_blocks(document):
        texts = [getattr(block, "text", ""), getattr(block, "alt", None) or ""]
        texts.extend(cell.text for row in getattr(block, "rows", []) for cell in row)
        # Paragraph.text already joins its nodes; do not count them twice.
        invalid = False
        for text in texts:
            invalid = inspect(text) or invalid
        if invalid:
            affected.append(block.id)
    return {
        "count": sum(counts.values()),
        "codepoints": dict(sorted(counts.items())),
        "block_ids": affected,
        "metadata_fields": metadata_fields,
    }
