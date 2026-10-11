"""Link explicitly verified note markers without guessing from superscripts."""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import quote

from engine.epub.xml import escape, quoteattr
from engine.reflowdoc.models import FootnoteBlock, ImageBlock

SUPERSCRIPTS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
TO_DIGITS = str.maketrans(SUPERSCRIPTS, "0123456789")
MARKERS = re.compile(f"[{SUPERSCRIPTS}]+")


def chapter_blocks(chapter):
    def walk(blocks):
        for block in blocks:
            yield block
            if not isinstance(block, FootnoteBlock):
                yield from walk(getattr(block, "blocks", []))
                for item in getattr(block, "items", []):
                    yield from walk(item.blocks)
    return list(walk(chapter.blocks))


class FootnoteContext:
    def __init__(self, chapter):
        blocks = chapter_blocks(chapter)
        notes = [b for b in blocks if isinstance(b, FootnoteBlock)]
        counts = Counter(b.marker for b in notes)
        referenced = set()
        for block in blocks:
            if isinstance(block, FootnoteBlock):
                continue
            explicit = set(block.footnote_refs)
            if isinstance(block, ImageBlock) and not block.decorative:
                referenced.update(explicit)
            else:
                referenced.update(m.group().translate(TO_DIGITS)
                                  for m in MARKERS.finditer(getattr(block, "text", ""))
                                  if m.group().translate(TO_DIGITS) in explicit)
        self.notes = {n.marker: n for n in notes if counts[n.marker] == 1 and n.marker in referenced}
        self.backlinks = {n.id: [] for n in self.notes.values()}
        def all_ids(group):
            for b in group:
                yield b.id
                yield from all_ids(getattr(b, "blocks", []))
                for item in getattr(b, "items", []):
                    yield from all_ids(item.blocks)
        self.reserved = set(all_ids(chapter.blocks))
        self.section_id = self.unique_id("footnotes")

    def unique_id(self, base):
        candidate, counter = base, 2
        while candidate in self.reserved:
            candidate = f"{base}-{counter}"
            counter += 1
        self.reserved.add(candidate)
        return candidate

    def link(self, marker, block, label):
        note = self.notes.get(marker)
        if note is None or marker not in block.footnote_refs:
            return escape(label)
        anchor = self.unique_id(f"ref-{block.id}-{len(self.backlinks[note.id]) + 1}")
        self.backlinks[note.id].append(anchor)
        return (f'<a class="noteref" epub:type="noteref" role="doc-noteref" '
                f'id={quoteattr(anchor)} href={quoteattr("#" + quote(note.id, safe="-._~"))}'
                f' aria-label={quoteattr("Catatan kaki " + marker)}>{escape(label)}</a>')

    def text(self, text, block):
        parts, start = [], 0
        for match in MARKERS.finditer(text):
            parts.append(escape(text[start:match.start()]))
            parts.append(self.link(match.group().translate(TO_DIGITS), block, match.group()))
            start = match.end()
        parts.append(escape(text[start:]))
        return "".join(parts)
