"""EPUB 3 packaging (backlog M4-03, M4-04).

Consumes ReflowDoc and produces an EPUB 3 package via EbookLib: semantic
XHTML per chapter, reflowable CSS, navigation, OPF metadata, and (when
Arabic content is present) an embedded redistributable Arabic font — FiraGO,
SIL Open Font License.

The renderer never mutates its input document (REFLOWDOC-SPEC section 18).
"""

from __future__ import annotations

import io
from contextlib import suppress
from urllib.parse import quote

from ebooklib import epub

from engine.arabic.unicode import is_arabic_letter
from engine.epub.css import (
    FONT_FACE_CSS,
    FONT_ID,
    STYLESHEET,
)
from engine.epub.xhtml import chapter_xhtml, primary_language, image_view_filename, image_view_xhtml
from engine.epub.footnotes import FootnoteContext
from engine.epub.xml import xml_text
from engine.reflowdoc.models import HeadingBlock, ImageBlock, ReflowDocument
from engine.reflowdoc.traversal import iter_blocks

_CSS_FONT_URL = "fonts/FiraGO-Regular.ttf"


def _font_naming(data: bytes) -> tuple[str, str]:
    """(file name, media type) matched to the actual font binary.

    pymupdf-fonts ships FiraGO as OpenType/CFF ("OTTO" magic); naming it .ttf
    with a vnd.ms-opentype media type trips epubcheck's font sniffing
    (RSC-007). EPUB 3.3 core media types: font/otf, font/ttf.
    """
    if data[:4] == b"OTTO":
        return "fonts/FiraGO-Regular.otf", "font/otf"
    return "fonts/FiraGO-Regular.ttf", "font/ttf"


def _document_has_arabic(document: ReflowDocument) -> bool:
    for block in iter_blocks(document):
        texts = [getattr(block, "text", "")]
        texts.extend(cell.text for row in getattr(block, "rows", []) for cell in row)
        if any(any(is_arabic_letter(ch) for ch in text) for text in texts if isinstance(text, str)):
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
    title = xml_text(document.metadata.title or document.metadata.source_filename or "Untitled") or "Untitled"
    book.set_title(title)
    # Unique dc:creator ids: ebooklib's add_author stamps every creator with
    # id="creator", which epubcheck rejects as a duplicate id (RSC-005).
    for index, author in enumerate(document.metadata.author or ["Unknown"], start=1):
        book.add_metadata("DC", "creator", xml_text(author), {"id": f"creator-{index}"})

    language = primary_language(document)
    book.set_language(language)
    for extra in document.metadata.languages:
        if extra != language and extra != "unknown":
            book.add_metadata("DC", "language", extra)

    if embed_arabic_font is None:
        embed_arabic_font = _document_has_arabic(document)
    css_text = STYLESHEET
    if embed_arabic_font:
        data = font_bytes if font_bytes is not None else default_arabic_font_bytes()
        if data:
            font_filename, font_media_type = _font_naming(data)
            book.add_item(
                epub.EpubItem(
                    uid=FONT_ID,
                    file_name=font_filename,
                    media_type=font_media_type,
                    content=data,
                )
            )
            css_text += FONT_FACE_CSS.replace(_CSS_FONT_URL, font_filename)

    stylesheet = epub.EpubItem(
        uid="style", file_name="style.css", media_type="text/css",
        content=css_text.encode("utf-8"),
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

    chapters = []
    image_views = []
    navigation = []
    for index, chapter in enumerate(document.chapters, start=1):
        file_name = f"chapter-{index:03d}.xhtml"
        content = chapter_xhtml(document, chapter)
        item = epub.EpubHtml(
            title=xml_text(chapter.title or title) or title,
            file_name=file_name,
            lang=language,
            content=content.encode("utf-8"),
        )
        item.add_item(stylesheet)
        book.add_item(item)
        chapters.append(item)
        # Source-image inspection pages stay outside the linear reading order.
        for block in iter_blocks(ReflowDocument(chapters=[chapter])):
            resource_id = getattr(block, "source_image_resource_id", None)
            if isinstance(block, ImageBlock) and not block.decorative and "ARABIC_RENDERED_AS_IMAGE" in block.warnings:
                resource_id = block.resource_id
            if not resource_id:
                continue
            view = epub.EpubHtml(
                uid="view-" + image_view_filename(block.id).removesuffix(".xhtml"),
                title="Gambar sumber", file_name=image_view_filename(block.id), lang=language,
                content=image_view_xhtml(document, resource_id,
                    f"{file_name}#{quote(block.id, safe='-._~')}", getattr(block, "alt", None) or "Gambar dari PDF sumber",
                    rtl=block.lang == "ar" or block.dir == "rtl").encode("utf-8"),
            )
            view.add_item(stylesheet)
            book.add_item(view)
            image_views.append((view, "no"))
        nodes = []
        stack = []
        for block in chapter.blocks:
            if isinstance(block, HeadingBlock):
                label, level = xml_text(block.text), block.level
            elif isinstance(block, ImageBlock) and block.heading_level is not None:
                label, level = xml_text(block.alt or ""), block.heading_level
            else:
                continue
            if not label.strip():
                continue
            while stack and stack[-1][0] >= level:
                stack.pop()
            children = []
            entry = (epub.Link(f"{file_name}#{quote(block.id, safe='-._~')}", label, block.id), children)
            (stack[-1][1] if stack else nodes).append(entry)
            stack.append((level, children))

        def finalize(entries):
            return [(link, finalize(children)) if children else link for link, children in entries]

        notes = FootnoteContext(chapter)
        if notes.notes:
            note_links = [epub.Link(f"{file_name}#{quote(fn.id, safe='-._~')}", f"Catatan {marker}", f"note-{index}-{marker}")
                          for marker, fn in notes.notes.items()]
            nodes.append((epub.Link(f"{file_name}#{notes.section_id}", "Catatan kaki", f"notes-{index}"),
                          [(link, []) for link in note_links]))
        navigation.append((item, finalize(nodes)) if nodes else item)

    book.toc = navigation
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    spine: list[object] = ["nav"]
    if cover is not None:
        cover_page = next(
            (item for item in book.get_items() if isinstance(item, epub.EpubCoverHtml)),
            None,
        )
        if cover_page is not None:
            # ebooklib defaults the cover page to is_linear=False; epubcheck
            # then fails the package because nothing hyperlinks to it (OPF-096).
            cover_page.is_linear = True
            spine.append(cover_page)
    book.spine = spine + chapters + image_views

    return _write_book_bytes(book)


def _write_book_bytes(book: epub.EpubBook) -> bytes:
    """Write in memory and close ZIP handles even if EbookLib raises.

    EbookLib's public write_epub helper can swallow OSError and leaves its
    ZIP open on other failures. On Windows a temporary-file cleanup then
    masks the real error with WinError 32. Avoid the filesystem entirely.
    """
    with io.BytesIO() as output:
        writer = epub.EpubWriter(output, book, options={"raise_exceptions": True, "epub3_pages": False})
        try:
            writer.process()
            writer.write()
        except BaseException:
            archive = getattr(writer, "out", None)
            if archive is not None:
                with suppress(Exception):
                    archive.close()
            raise
        archive = getattr(writer, "out", None)
        if archive is not None:
            archive.close()
        return output.getvalue()
