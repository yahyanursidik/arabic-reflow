# EPUB Renderer (Milestone 4)

`engine/epub/` turns ReflowDoc into EPUB 3. Boundary rule: the renderer
consumes ReflowDoc and never depends on PDF internals; it never mutates its
input (REFLOWDOC-SPEC section 18).

## Pipeline

```python
from engine.pipeline import build_epub

result, data, report = build_epub("book.pdf")   # validates, raises on severe
open("book.epub", "wb").write(data)
```

`build_epub` = `build_reflowdoc` + `engine.epub.renderer.render_epub` +
`engine.validation.epub.assert_valid`.

## XHTML (M4-01, M4-02)

`engine/epub/xhtml.py` renders each chapter as an EPUB 3 XHTML document:

- headings → `h1..h6`, paragraphs → `p`, quotes → `blockquote`, lists →
  `ol/ul`, tables → `table`, footnotes → `aside epub:type="footnote"`;
- every element carries its `lang`/`dir` from ReflowDoc;
- Arabic blocks: `<p class="arabic" lang="ar" dir="rtl">`;
- minority-script inline spans: `<bdi lang="ar" dir="rtl">…</bdi>` — safe
  bidi isolation, exactly the mixed-inline shape from ARABIC-ENGINE.md §9;
- text is XML-escaped but **never altered**: presentation forms, harakat,
  and extraction artifacts pass through byte-for-byte.

## CSS and fonts (M4-04)

`engine/epub/css.py` ships a reflowable stylesheet (no absolute positioning,
no fixed dimensions). When the document contains Arabic, FiraGO (SIL OFL —
redistributable open font) is embedded under `fonts/` and referenced via
`@font-face`; pass `font_bytes=` to override the source or
`embed_arabic_font=False` to skip embedding.

## Validation (M4-05)

`engine/validation/epub.py` checks: mimetype first and stored uncompressed,
`META-INF/container.xml` parseable, OPF manifest/spine consistency, and
well-formed XHTML with `lang` on the root. Severe problems raise
`EPUBValidationError` from `build_epub` (the export gate).

This is structural validation, **not** a full epubcheck replacement — wire
epubcheck into CI when a Java runtime is available.

## Deferred

- Images: ReflowDoc `Resource` has no binary payload yet, so image blocks
  render as `<figure>` with a placeholder `src` until resource storage lands
  (extraction side) — see M6-05.
- Footnote *detection* is M6-03/04; the renderer already renders footnote
  blocks when present.
