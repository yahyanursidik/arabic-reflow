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

from xml.sax.saxutils import escape

from engine.reflowdoc.models import (
    Chapter,
    Direction,
    FootnoteBlock,
    HeadingBlock,
    ImageBlock,
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
    return f"<bdi{_attrs(node.lang, node.dir)}>{escape(node.text)}</bdi>"


def _paragraph(p: ParagraphBlock) -> str:
    classes = [ARABIC_CLASS] if p.dir is Direction.RTL else []
    body = "".join(
        _span_node(node) if isinstance(node, SpanNode) else _text_node(node)
        for node in p.content
    )
    return f"<p{_attrs(p.lang, p.dir, classes)}>{body}</p>"


def _heading(h: HeadingBlock) -> str:
    level = min(max(h.level, 1), 6)
    return f"<h{level}{_attrs(h.lang, h.dir)}>{escape(h.text)}</h{level}>"


def _quote(q: QuoteBlock) -> str:
    classes = [ARABIC_CLASS] if q.subtype == "arabic" or q.dir is Direction.RTL else []
    return f"<blockquote{_attrs(q.lang, q.dir, classes)}>{escape(q.text)}</blockquote>"


def _list(lb: ListBlock) -> str:
    tag = "ol" if lb.ordered else "ul"
    items = []
    for item in lb.items:
        inner = "".join(_render_block(child) for child in item.blocks)
        items.append(f"<li>{inner}</li>")
    return f"<{tag}{_attrs(lb.lang, lb.dir)}>{''.join(items)}</{tag}>"


def _image(img: ImageBlock, document: ReflowDocument) -> str:
    src = img.resource_id
    for resource in document.resources:
        if resource.id == img.resource_id:
            src = f"resources/{resource.filename or resource.id}"
            break
    alt = escape(img.alt) if img.alt else ""
    caption = ""
    if img.caption_block_id:
        caption = f"<figcaption>see {escape(img.caption_block_id)}</figcaption>"
    return f"<figure><img src=\"{escape(src)}\" alt=\"{alt}\"/>{caption}</figure>"


def _footnote(fn: FootnoteBlock) -> str:
    inner = "".join(_render_block(child) for child in fn.blocks)
    return f"<aside epub:type=\"footnote\"{_attrs(fn.lang, fn.dir)} id=\"{escape(fn.id or 'fn')}\">{inner}</aside>"


def _table(t: TableBlock) -> str:
    rows = []
    for row in t.rows:
        cells = "".join(
            f"<td{_attrs(cell.lang, cell.dir)}>{escape(cell.text)}</td>" for cell in row
        )
        rows.append(f"<tr>{cells}</tr>")
    return f"<table{_attrs(None, t.dir)}>{''.join(rows)}</table>"


def _render_block(block, document: ReflowDocument | None = None) -> str:
    if isinstance(block, HeadingBlock):
        return _heading(block)
    if isinstance(block, ParagraphBlock):
        return _paragraph(block)
    if isinstance(block, QuoteBlock):
        return _quote(block)
    if isinstance(block, ListBlock):
        return _list(block)
    if isinstance(block, ImageBlock) and document is not None:
        return _image(block, document)
    if isinstance(block, FootnoteBlock):
        return _footnote(block)
    if isinstance(block, TableBlock):
        return _table(block)
    return ""


def primary_language(document: ReflowDocument) -> str:
    langs = [l for l in document.metadata.languages if l != "unknown"]
    return langs[0] if langs else "en"


def primary_direction(document: ReflowDocument) -> str:
    return "rtl" if primary_language(document) == "ar" else "ltr"


def chapter_xhtml(document: ReflowDocument, chapter: Chapter) -> str:
    """Render one ReflowDoc chapter as a complete EPUB 3 XHTML document."""
    lang = primary_language(document)
    dir_ = primary_direction(document)
    title = escape(chapter.title or document.metadata.title or "Untitled")
    body = "\n".join(_render_block(b, document) for b in chapter.blocks).strip()
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
