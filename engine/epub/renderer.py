"""EPUB 3 packaging (backlog M4-03, M4-04).

Consumes ReflowDoc and produces an EPUB 3 package via EbookLib: semantic
XHTML per chapter, reflowable CSS, navigation, OPF metadata, and (when
Arabic content is present) an embedded redistributable Arabic font — FiraGO,
SIL Open Font License.

The renderer never mutates its input document (REFLOWDOC-SPEC section 18).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ebooklib import epub

from engine.arabic.unicode import is_arabic_letter
from engine.epub.css import (
    FONT_FILENAME,
    FONT_ID,
    FONT_MEDIA_TYPE,
    STYLESHEET,
)
from engine.epub.xhtml import chapter_xhtml, primary_language
from engine.reflowdoc.models import ReflowDocument


def _document_has_arabic(document: ReflowDocument) -> bool:
    for chapter in document.chapters:
        for block in chapter.blocks:
            text = getattr(block, "text", None)
            if isinstance(text, str) and any(is_arabic_letter(ch) for ch in text):
                return True
            content = getattr(block, "content", None)
            for node in content or []:
                if any(is_arabic_letter(ch) for ch in node.text):
                    return True
    return False


def default_arabic_font_bytes() -> bytes | None:
    """FiraGO from the optional pymupdf-fonts package (SIL OFL licensed).

    Returns None when the package is unavailable; the CSS still references
    the font family and readers fall back to their own Arabic fonts.
    """
    try:
        import pymupdf
    except ImportError:  # pragma: no cover
        return None
    try:
        font = pymupdf.Font("figo")
    except Exception:  # pragma: no cover
        return None
    if font.has_glyph(ord("ب")) and font.buffer:
        return font.buffer
    return None  # pragma: no cover


def render_epub(
    document: ReflowDocument,
    *,
    embed_arabic_font: bool | None = None,
    font_bytes: bytes | None = None,
) -> bytes:
    """Package the document as EPUB 3 and return the file bytes.

    embed_arabic_font: None (default) embeds automatically when the document
    contains Arabic; True forces embedding; False disables it.
    """
    book = epub.EpubBook()
    book.set_identifier(document.document_id)
    title = document.metadata.title or document.metadata.source_filename or "Untitled"
    book.set_title(title)
    for author in document.metadata.author or ["Unknown"]:
        book.add_author(author)

    language = primary_language(document)
    book.set_language(language)
    for extra in document.metadata.languages:
        if extra != language and extra != "unknown":
            book.add_metadata("DC", "language", extra)

    stylesheet = epub.EpubItem(
        uid="style", file_name="style.css", media_type="text/css",
        content=STYLESHEET.encode("utf-8"),
    )
    book.add_item(stylesheet)

    cover = next(
        (
            resource
            for resource in document.resources
            if resource.id == document.metadata.cover_resource_id
            and resource.kind == "image"
            and resource.content
        ),
        None,
    )
    if cover is not None:
        extension = "png" if (cover.media_type or "").endswith("png") else "jpg"
        # ebooklib's set_cover registers the cover image, a cover.xhtml page,
        # and the <meta name="cover"> OPF entry readers look for.
        book.set_cover(f"cover.{extension}", cover.content)

    for resource in document.resources:
        if resource is cover:
            continue
        if resource.kind == "image" and resource.content:
            book.add_item(
                epub.EpubItem(
                    uid=resource.id,
                    file_name=f"resources/{resource.filename or resource.id}",
                    media_type=resource.media_type or "application/octet-stream",
                    content=resource.content,
                )
            )

    if embed_arabic_font is None:
        embed_arabic_font = _document_has_arabic(document)
    if embed_arabic_font:
        data = font_bytes if font_bytes is not None else default_arabic_font_bytes()
        if data:
            book.add_item(
                epub.EpubItem(
                    uid=FONT_ID,
                    file_name=FONT_FILENAME,
                    media_type=FONT_MEDIA_TYPE,
                    content=data,
                )
            )

    chapters = []
    for index, chapter in enumerate(document.chapters, start=1):
        file_name = f"chapter-{index:03d}.xhtml"
        content = chapter_xhtml(document, chapter)
        item = epub.EpubHtml(
            title=chapter.title or title,
            file_name=file_name,
            lang=language,
            content=content.encode("utf-8"),
        )
        item.add_item(stylesheet)
        book.add_item(item)
        chapters.append(item)

    book.toc = chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    spine: list[object] = ["nav"]
    if cover is not None:
        cover_page = next(
            (item for item in book.get_items() if isinstance(item, epub.EpubCoverHtml)),
            None,
        )
        if cover_page is not None:
            spine.append(cover_page)
    book.spine = spine + chapters

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "book.epub"
        epub.write_epub(str(target), book)
        return target.read_bytes()
