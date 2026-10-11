"""Semantic XHTML rendering (backlog M4-01, M4-02).

Renders ReflowDoc chapters to reflowable, semantic XHTML 1.1 (EPUB 3 content
documents):

- `lang` and `dir` are carried onto elements (REFLOWDOC-SPEC section 18);
- Arabic blocks render as `<p lang="ar" dir="rtl" class="arabic">`;
- minority-script inline spans render inside `<bdi>` for safe bidi isolation;
- text is escaped but never altered — what extraction preserved, the reader
  sees.

The renderer is pure: it consumes ReflowDoc and returns strings. It never
mutates the document.
"""

from __future__ import annotations

from hashlib import sha256

from engine.epub.xml import escape, quoteattr
from engine.epub.footnotes import FootnoteContext

from engine.reflowdoc.models import (
    Chapter,
    Direction,
    FootnoteBlock,
    HeadingBlock,
    ImageBlock,
    InlineImageNode,
    ListBlock,
    ParagraphBlock,
    QuoteBlock,
    ReflowDocument,
    SpanNode,
    TableBlock,
    TextNode,
)

ARABIC_CLASS = "arabic"

XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"


def _attrs(lang: str | None, dir_: str | None, classes: list[str] | None = None) -> str:
    parts: list[str] = []
    if classes:
        parts.append(f' class="{" ".join(classes)}"')
    if lang and lang != "unknown":
        parts.append(f' lang="{escape(lang)}"')
    if dir_:
        parts.append(f' dir="{dir_.value if isinstance(dir_, Direction) else dir_}"')
    return "".join(parts)


def _text_node(node: TextNode) -> str:
    return escape(node.text)


def _span_node(node: SpanNode) -> str:
    """Minority-script spans render with bidi isolation (`<bdi>`)."""
    # Boundary whitespace belongs to the paragraph's direction. If a leading
    # space is isolated inside RTL, it appears at the opposite edge and joins
    # the Arabic word to the preceding Latin word. Move only the isolation
    # boundary, preserving every source character and its logical order.
    start = len(node.text) - len(node.text.lstrip())
    end = max(start, len(node.text.rstrip()))
    before, content, after = node.text[:start], node.text[start:end], node.text[end:]
    return f"{escape(before)}<bdi{_attrs(node.lang, node.dir)}>{escape(content)}</bdi>{escape(after)}"


def _resource_src(resource_id, document):
    if document is not None:
        for resource in document.resources:
            if resource.id == resource_id:
                return f"resources/{resource.filename or resource.id}"
    return resource_id


def _paragraph(p: ParagraphBlock, document=None, notes=None) -> str:
    classes = [ARABIC_CLASS] if p.dir is Direction.RTL else []
    parts = []
    for node in p.content:
        if isinstance(node, InlineImageNode):
            parts.append(f'<img class="inline-source" src={quoteattr(_resource_src(node.resource_id, document))}'
                         f' alt={quoteattr(node.alt)}/>')
        elif isinstance(node, SpanNode):
            rendered = _span_node(node)
            # Reference glyphs keep the containing paragraph's direction.
            if notes and p.footnote_refs:
                rendered = _span_node(node) if not node.text.strip() else _linked_span(node, p, notes)
            parts.append(rendered)
        else:
            parts.append(notes.text(node.text, p) if notes else _text_node(node))
    body = "".join(parts)
    return f"<p{_attrs(p.lang, p.dir, classes)}>{body}</p>"


def _linked_span(node, block, notes):
    start = len(node.text) - len(node.text.lstrip())
    end = max(start, len(node.text.rstrip()))
    return (notes.text(node.text[:start], block)
            + f'<bdi{_attrs(node.lang, node.dir)}>{notes.text(node.text[start:end], block)}</bdi>'
            + notes.text(node.text[end:], block))


def _heading(h: HeadingBlock, notes=None) -> str:
    level = min(max(h.level, 1), 6)
    return f"<h{level}{_attrs(h.lang, h.dir)} id={quoteattr(h.id)}>{_mixed_text(h.text, h, notes)}</h{level}>"


def _mixed_text(text: str, block=None, notes=None) -> str:
    from engine.reflowdoc.editing import edited_content

    return "".join(
        (_linked_span(node, block, notes) if notes else _span_node(node))
        if isinstance(node, SpanNode) else (notes.text(node.text, block) if notes else _text_node(node))
        for node in edited_content(text)
    )


def _quote(q: QuoteBlock, notes=None) -> str:
    classes = [ARABIC_CLASS] if q.subtype == "arabic" or q.dir is Direction.RTL else []
    return f"<blockquote{_attrs(q.lang, q.dir, classes)}>{_mixed_text(q.text, q, notes)}</blockquote>"


def _list(lb: ListBlock, document: ReflowDocument | None = None, notes=None) -> str:
    tag = "ol" if lb.ordered else "ul"
    items = []
    for item in lb.items:
        inner = "".join(_render_block(child, document, notes) for child in item.blocks)
        items.append(f"<li>{inner}</li>")
    return f"<{tag}{_attrs(lb.lang, lb.dir)}>{''.join(items)}</{tag}>"


def _image(img: ImageBlock, document: ReflowDocument, notes=None) -> str:
    if img.decorative:
        return ""
    src = _resource_src(img.resource_id, document)
    alt = quoteattr(img.alt or "")
    source_image = "ARABIC_RENDERED_AS_IMAGE" in img.warnings
    actions = []
    if source_image:
        actions.append(f'<a class="image-zoom" href={quoteattr(image_view_filename(img.id))}>Perbesar gambar</a>')
    if notes:
        actions.extend(notes.link(marker, img, "Catatan " + marker) for marker in img.footnote_refs)
    action_html = f'<p class="image-actions">{" · ".join(actions)}</p>' if actions else ""
    if img.heading_level is not None:
        level = img.heading_level
        image_class = "image-heading source-image-heading" if source_image else "image-heading"
        return (f'<h{level} class="{image_class}" id={quoteattr(img.id)}>'
                f'<img src={quoteattr(src)} alt={alt}/></h{level}>{action_html}')
    caption = ""
    if img.caption_block_id:
        caption = f"<figcaption>see {escape(img.caption_block_id)}</figcaption>"
    picture = f'<img src={quoteattr(src)} alt={alt}/>'
    if source_image:
        picture = f'<a class="source-image-link" href={quoteattr(image_view_filename(img.id))}>{picture}</a>'
    image_class = ' class="source-image"' if source_image else ""
    return f"<figure{image_class} id={quoteattr(img.id)}>{picture}{caption}{action_html}</figure>"


def _footnote(fn: FootnoteBlock, document: ReflowDocument | None = None, notes=None) -> str:
    inner = "".join(_render_block(child, document) for child in fn.blocks)
    actions = []
    if fn.source_image_resource_id:
        actions.append(f'<a class="image-zoom" href={quoteattr(image_view_filename(fn.id))}>Gambar sumber</a>')
    if notes:
        for index, target in enumerate(notes.backlinks.get(fn.id, [])):
            label = "Kembali ke bacaan" if index == 0 else f"Kembali ke rujukan {index + 1}"
            actions.append(f'<a role="doc-backlink" href={quoteattr("#" + target)}>{escape(label)}</a>')
    footer = f'<p class="note-actions">{" · ".join(actions)}</p>' if actions else ""
    label = "Catatan kaki " + fn.marker
    heading = f'<h3 class="footnote-label" dir="ltr">{escape(label)}</h3>'
    return (f'<aside epub:type="footnote"{_attrs(fn.lang, fn.dir)} '
            f'id={quoteattr(fn.id or "fn")} aria-label={quoteattr(label)}>{heading}{inner}{footer}</aside>')


def _table(t: TableBlock, document: ReflowDocument | None = None) -> str:
    if not t.rows and t.fallback_resource_id and document is not None:
        # Low-confidence grid: PRD 8.14 fallback — the region ships as an image.
        src = t.fallback_resource_id
        for resource in document.resources:
            if resource.id == t.fallback_resource_id:
                src = f"resources/{resource.filename or resource.id}"
                break
        return f"<figure><img src=\"{escape(src)}\" alt=\"\"/></figure>"
    rows = []
    for row in t.rows:
        cells = "".join(
            f"<td{_attrs(cell.lang, cell.dir)}>{escape(cell.text)}</td>" for cell in row
        )
        rows.append(f"<tr>{cells}</tr>")
    return f"<table{_attrs(None, t.dir)}>{''.join(rows)}</table>"


def _render_block(block, document: ReflowDocument | None = None, notes=None) -> str:
    if isinstance(block, HeadingBlock):
        return _heading(block, notes)
    if isinstance(block, ParagraphBlock):
        return _paragraph(block, document, notes)
    if isinstance(block, QuoteBlock):
        return _quote(block, notes)
    if isinstance(block, ListBlock):
        return _list(block, document, notes)
    if isinstance(block, ImageBlock) and document is not None:
        return _image(block, document, notes)
    if isinstance(block, FootnoteBlock):
        if notes and block.id in notes.backlinks:
            return ""
        return _footnote(block, document)
    if isinstance(block, TableBlock):
        return _table(block, document)
    return ""


def primary_language(document: ReflowDocument) -> str:
    langs = [l for l in document.metadata.languages if l != "unknown"]
    return langs[0] if langs else "en"


def primary_direction(document: ReflowDocument) -> str:
    return "rtl" if primary_language(document) == "ar" else "ltr"


def image_view_filename(block_id: str) -> str:
    # Arbitrary block identifiers must never become filesystem paths.
    return "image-view-" + sha256(block_id.encode("utf-8")).hexdigest() + ".xhtml"


def image_view_xhtml(document, resource_id, return_href, alt="", rtl=False):
    """A navigable EPUB content document; PNGs are not hyperlink destinations."""
    lang = primary_language(document)
    picture = f'<img src={quoteattr(_resource_src(resource_id, document))} alt={quoteattr(alt)}/>'
    original_direction = "rtl" if rtl else "ltr"
    return (f'<html xmlns="{XHTML_NS}" lang={quoteattr(lang)} xml:lang={quoteattr(lang)}>'
            '<head><title>Gambar sumber</title><link rel="stylesheet" href="style.css"/></head>'
            '<body class="image-view"><p class="note-actions">'
            f'<a href={quoteattr(return_href)}>Kembali ke bacaan</a></p>'
            '<p class="image-help">Gambar diperbesar 2×. Geser mendatar dan ke bawah '
            'untuk membaca seluruh bagian. Huruf dan harakat berasal dari gambar sumber utuh. '
            '<a href="#gambar-utuh">Lihat gambar utuh</a>.</p>'
            f'<div class="image-enlarged" dir={quoteattr(original_direction)} role="region" '
            f'tabindex="0" aria-label="Gambar diperbesar; geser untuk membaca">{picture}</div>'
            f'<figure class="image-fit" id="gambar-utuh">{picture}</figure>'
            '<details><summary>Perbesar ukuran asli (geser untuk melihat)</summary>'
            f'<div class="image-original" dir={quoteattr(original_direction)}>{picture}</div></details></body></html>')


def chapter_xhtml(document: ReflowDocument, chapter: Chapter) -> str:
    """Render one ReflowDoc chapter as a complete EPUB 3 XHTML document."""
    lang = primary_language(document)
    dir_ = primary_direction(document)
    title = escape(chapter.title or document.metadata.title or "Untitled")
    notes = FootnoteContext(chapter)
    body = "\n".join(_render_block(b, document, notes) for b in chapter.blocks).strip()
    if notes.notes:
        body += (f'<section class="endnotes" id={quoteattr(notes.section_id)}>'
                 '<h2>Catatan kaki</h2>'
                 + "".join(_footnote(fn, document, notes) for fn in notes.notes.values()) + '</section>')
    if not body:
        # ebooklib's nav generation crashes on an empty <body>; give empty
        # documents (e.g. scanned input without OCR) a harmless placeholder.
        body = '<p class="empty">\u00a0</p>'
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!DOCTYPE html>\n"
        f'<html xmlns="{XHTML_NS}" xmlns:epub="{EPUB_NS}" '
        f'lang="{lang}" xml:lang="{lang}" dir="{dir_}">\n'
        "<head>\n"
        f"<title>{title}</title>\n"
        '<link rel="stylesheet" type="text/css" href="style.css"/>\n'
        "</head>\n"
        f'<body lang="{lang}" dir="{dir_}">\n'
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )
