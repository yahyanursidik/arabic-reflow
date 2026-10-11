"""Shared recursive traversal for semantic blocks, lists, and footnotes."""

from __future__ import annotations

from collections.abc import Iterator

from engine.reflowdoc.models import Block, ReflowDocument


def block_locations(document: ReflowDocument) -> Iterator[tuple[list[Block], int]]:
    def walk(blocks):
        for index, block in enumerate(blocks):
            yield blocks, index
            yield from walk(getattr(block, "blocks", []))
            for item in getattr(block, "items", []):
                yield from walk(item.blocks)

    for chapter in document.chapters:
        yield from walk(chapter.blocks)


def iter_blocks(document: ReflowDocument) -> Iterator[Block]:
    for blocks, index in block_locations(document):
        yield blocks[index]
