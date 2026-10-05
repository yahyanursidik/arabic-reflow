# Reconstruction (Milestone 2)

How ordered raw primitives become ReflowDoc blocks. Pipeline position:

```text
analyze → extract → detect_layout → reconstruct_reading_order
        → detect_scripts → reconstruct_semantics → ReflowDoc
```

Modules: `engine/layout/` (furniture, columns, reading order) and
`engine/reconstruction/` (paragraphs, headings, ReflowDoc assembly).
Entry point: `engine.pipeline.build_reflowdoc(source)`.

## Header/footer and page numbers (M2-05, M2-06)

`engine/layout/furniture.py` removes blocks only when they are:

- in the top 15% / bottom 15% of the page, **and** at most 10 words, **and**
  either repeat (digit-normalized, case-folded) in the same band on ≥ 2 pages
  (header/footer), or are purely a printed page number: digits with optional
  decoration (`- 7 -`, `(12)`) or labeled (`Page 7`, `Halaman 7`, Arabic-Indic
  digits accepted). Any prose containing a digit never matches.

Removed blocks are recorded in `LayoutReport.removed_furniture`; the printed
page number mapping (`pdf page → printed number`) is preserved in
`LayoutReport.page_number_map` (M2-06 provenance rule).

Document-level warnings emitted: `FURNITURE_REMOVED` (info),
`PAGE_NUMBERS_REMOVED` (info).

## Reading order (M2-01)

`engine/layout/reading_order.py` never relies on plain y,x sorting:

- single-column pages: blocks are grouped into visual rows (≥ 50% vertical
  overlap of the shorter block) and ordered top-to-bottom; within a row the
  order follows the page's dominant direction (RTL pages read right-to-left);
- pages with a detected gutter (`engine/layout/columns.find_gutter`): left
  column, then right column, with full-width blocks (headings, spanning
  rules) kept at their vertical position;
- pages the analyzer flagged as multi-column where no gutter can be
  established produce `READING_ORDER_UNCERTAIN` (warning) and confidence
  0.5 instead of a silent guess. Confidence: 0.95 single column, 0.85 column
  layout.

## Paragraph reconstruction (M2-02)

`engine/reconstruction/paragraphs.py` merges conservatively (PRD 8.8):

- lines inside one block always join;
- a separate block continues the paragraph only when the paragraph's last
  line spans ≥ 55% of **its column's** reference width (gutter-aware; a
  220pt column is not held to a 480pt page standard) and lacks terminal
  punctuation (`.?!…:;،؛؟۔`), with compatible font size (± 1pt) and overlapping
  x-range (different columns never merge);
- stray punctuation fragments (`:` extracted as its own block) attach to the
  current paragraph;
- whitespace runs collapse to single spaces at line boundaries; **within a
  line, span text is preserved verbatim** — no character is ever altered.
  Presentation forms, harakat, and extraction artifacts pass through (M3
  owns explicit, provenance-preserving normalization).

Mixed-script runs are split per character (one span can cover both scripts
when the PDF shares a font), so Arabic inside an Indonesian paragraph becomes
its own `SpanNode` (`lang="ar"`, `dir="rtl"`) ready for `<bdi>` rendering;
digits/neutral characters stay with the surrounding text run.

Confidence: 0.95 paragraph built from a single block, 0.75 when blocks were
merged. Merged paragraphs with confidence < 0.8 carry the
`PARAGRAPH_MERGE_UNCERTAIN` block warning.

## Dehyphenation (M2-03)

Latin only, high confidence only: the previous line must end with a hyphen,
the continuation must start with a lowercase Latin letter, and the character
before the hyphen must be a letter. Applied transformations keep run-level
`source_text` (the original text, line break included) and
`transformations: ["dehyphenation"]`. Uppercase continuations (compounds like
`MIN-MAX`) and all Arabic text keep the hyphen.

## Headings (M2-04)

`engine/reconstruction/headings.py` scores brevity (≤ 90 chars), absence of
terminal punctuation, size ratio vs the length-weighted body font size
(≥ 1.15), bold spans, and numbering patterns (`Bab …`, `1. …`, `1.2 …`,
roman numerals). Two or more signals make a heading. Level: 1 for ratio
≥ 1.5 or "Bab" numbering, 2 for ≥ 1.25, otherwise 3.

## ReflowDoc assembly

`engine/reconstruction/engine.py` maps drafts to blocks: `HeadingBlock`
(plain text) and `ParagraphBlock` (content nodes); all blocks live in one
ungrouped chapter (`chapter-001`, `title: null`) until chapter detection
lands. Block `lang` comes from the dominant script (minority-script runs
become `SpanNode`s with their own lang/dir); `dir` is first-strong;
`metadata.languages` collects block- and span-level labels in order of
appearance. Block ids are deterministic (`block-001`…), so snapshots and
diffs stay stable.

## Known limits (deferred)

- Quote detection is not implemented; such content falls back to paragraphs.
- No page_break blocks: ReflowDoc is a flow document; page provenance lives
  in each block's `source.page` and the furniture report.
- Column handling supports N gutters via recursive splitting (M6-01), but
  column regions always read left-to-right even on RTL pages — RTL
  multi-column ordering is a known limitation for M6 refinement.
- Footnote *detection* is heuristic zoning (bottom quarter, small font,
  numbered marker) and emits `FOOTNOTE_UNCERTAIN`; body-text marker linking
  (noterefs) is not implemented yet (M6-04 refinement).
- Table detection (M6-06, P2) is not implemented; table-like content falls
  back to paragraphs.
- Arabic page numbers in decorated forms (e.g. `١٤٤٧` alone in a band) are
  removed by the digit rule only when they parse via the Arabic-Indic
  translation; complex decorations may survive into paragraphs.

## Milestone 6 additions

- **N-column reading order** (`engine/layout/columns.find_gutters` +
  `_column_order`): recursive gutter detection per region, columns read
  left-to-right between full-width section separators; confidence 0.8 for
  multi-gutter pages.
- **Footnotes** (`engine/layout/footnotes.py`): bottom-quarter small-font
  numbered blocks become `FootnoteBlock(marker=…)` with an inner paragraph;
  EPUB renders them as `aside epub:type="footnote"`.
- **Images and captions** (`engine/layout/captions.py`): figure-sized images
  become `ImageBlock` + binary `Resource` (base64 in JSON); captions
  (below-image, overlapping, caption-word or small-font) are linked via
  `caption_block_id`; full-page rasters are treated as scans and skipped
  (OCR's domain). The EPUB renderer writes image resources and `<figure>`.

