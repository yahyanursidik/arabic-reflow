# Fixture Corpus

Location: `tests/fixtures/` — regenerate with `scripts/make_fixtures.py`,
golden records with `scripts/update_golden.py` (commit both outputs).

## Files

| Fixture | Covers |
| --- | --- |
| `indonesian-native.pdf` | Latin-only native text, heading, page number |
| `arabic-native.pdf` | Arabic without harakat; presentation-form extraction artifacts |
| `mixed-id-ar.pdf` | Inline Arabic inside Indonesian sentences, punctuation near Arabic |
| `arabic-vocalized.pdf` | Fully vocalized Arabic (harakat + shadda + superscript alef) |
| `arabic-numbers.pdf` | Arabic-Indic digits, Arabic punctuation (، ؛ ٬) |
| `two-column.pdf` | Two-column Latin page |
| `scanned.pdf` | Image-only page (no text layer) |
| `hybrid.pdf` | Native page 1 + scanned page 2 |
| `footnote-heavy.pdf` | Footnotes below a rule, reference markers |
| `image-caption.pdf` | Embedded figure with caption below it (M6-05) |
| `reversed-extraction.pdf` | Trap: renders fine, text layer extracts with reversed glyph order (M3-06) |

## How Arabic is written into fixtures

Arabic is inserted with PyMuPDF's HTML box engine (`insert_htmlbox`), which
shapes text and lays it out right-to-left like real PDF content. This makes
extraction behave like real-world Arabic PDFs, which exhibit known artifacts.
We deliberately keep these artifacts because the engine must handle them:

- **Presentation forms**: extracted Arabic comes back as Unicode Presentation
  Forms-B (U+FE70–FEFF) and ligature codepoints (e.g. U+FDF2) instead of core
  block codepoints. This is the artifact the Arabic Integrity Engine (M3) must
  surface and optionally normalize with `source_text` preservation.
- **Harakat survive**: combining marks extract intact (often *more* marks than
  the source because shadda+vowel decompositions). Golden counts are frozen in
  `tests/golden/`.
- **Unusual glyph mappings**: FiraGO ligature glyphs map back to non-Arabic
  codepoints (e.g. Georgian range) — the "fonts with unusual glyph mapping"
  category from ARABIC-ENGINE.md section 13.
- **Reversed digit runs**: Arabic-Indic digit sequences extract reversed.
- **Bidi line splits**: punctuation and mixed-direction runs can appear as
  separate spans or reordered fragments.

### The reversed trap fixture

`reversed-extraction.pdf` is the one fixture written **without**
`insert_htmlbox`: ReportLab draws the vocalized hadith glyph-by-glyph in
left-to-right order, mimicking producers whose output renders correctly on
screen while the text layer extracts in reversed glyph order. The builder
verifier asserts the trap actually traps — the logical string must be absent
from extraction — and `test_reversed_fixture_flagged_by_pipeline` proves the
integrity engine flags it (`REVERSED_ORDER_SUSPECTED`, document level
`problem_likely`). ReportLab is only needed when regenerating fixtures; CI
consumes the committed PDF.

## Golden tests

`tests/test_golden.py` compares extraction (exact text, block order, harakat
counts, presentation-form counts) against the approved records in
`tests/golden/*.golden.json`. A release is blocked if an approved fixture
loses characters, harakat, or reading order. If a change is intentional,
re-run `scripts/update_golden.py` and review the diff carefully.

## Regeneration requirements

`pymupdf-fonts` (FiraGO) or a system Arabic font is required to regenerate
fixtures. CI does **not** regenerate fixtures; it consumes the committed files.
