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

### Phone layout and source images

Small screens use start-aligned paragraphs, readable footnotes, narrower margins,
and proportional source images. Image inspection links open XHTML pages in the
EPUB, with a fit-to-screen image, an optional original-size view, and a return link.
Inspection pages do not enter the linear reading order. Resource bytes are preserved.

Paragraphs use a consistent gap with no first-line indent or stretched justification.
Explicit source newlines remain visible (credits, contents, verse), and long lines
are bounded to 38 em on large screens. Latin text uses Source Serif 4 when available,
then Georgia/Times/reader serif; Arabic uses embedded FiraGO, including inline spans,
with larger type and room for harakat. Nested RTL spans inherit the block size rather
than scaling repeatedly. Reader colors are inherited to support light/dark themes.
Each footnote has a visible marker label; verified links retain their return targets.
The web preview bundles the same FiraGO under its SIL OFL license and uses the same
paragraph rhythm. Review annotations can be shown separately from the reading flow.

Verified source-image blocks occupy the full reading width, with proportional height
and no viewport-height cap. The separate, non-linear inspection page opens at 200%
inside a scrollable region (RTL starts on the right), with a fit-width image and
return link. Every view references the same unchanged resource bytes: no cropping,
resampling or reconstructed Arabic. Readers without overflow support can use the
complete fit-width view and their native zoom. App artwork is never added to book content.

Only explicitly verified `footnote_refs` create superscript links. Referenced notes
move to a chapter-end section with return links and navigation entries; unreferenced
or ambiguous markers retain their original placement. `inline_image` paragraph nodes
carry source word pixels alongside reflowable text. Text edits cannot silently flatten
these nodes. `decorative` images can be omitted from the reading flow while retaining
their original resources and source provenance.

`engine/validation/epub.py` checks: mimetype first and stored uncompressed,
`META-INF/container.xml` parseable, OPF manifest/spine consistency, and
well-formed XHTML with `lang` on the root. Severe problems raise
`EPUBValidationError` from `build_epub` (the export gate).

Additionally `engine/validation/epubcheck.py` runs the official W3C
epubcheck when a JAR (`EPUBCHECK_JAR`) and Java are available — CI installs
both, so every fixture package is epubchecked there. Locally the tests skip.

### Real-reader verification

CI runs the official epubcheck on every fixture package. On top of that, the
generated packages (mixed Arabic, table + cover) were round-tripped through
Calibre's conversion engine (`ebook-convert`): both parse cleanly, the cover
page is recognized, and Arabic text, harakat, and `<bdi>` isolation survive
intact. Apple Books/kobo behave the same way on EPUB 3 packages that pass
epubcheck; report any reader-specific issue with the fixture that produced it.

### Cover (PRD 7 Should-Have)

`metadata.cover_resource_id` names a binary `Resource` (a rendered source
page); the renderer registers it via ebooklib `set_cover` (cover image +
cover.xhtml page + `<meta name="cover">`) and puts the cover page first on
the spine.

## Deferred

- Images: ReflowDoc `Resource` has no binary payload yet, so image blocks
  render as `<figure>` with a placeholder `src` until resource storage lands
  (extraction side) — see M6-05.
- Footnote *detection* is M6-03/04; the renderer already renders footnote
  blocks when present.
