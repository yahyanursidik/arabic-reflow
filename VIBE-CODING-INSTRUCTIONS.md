# Vibe Coding Instructions

## Role

You are acting as a senior Python document-processing engineer, full-stack TypeScript developer, EPUB engineer, Unicode/BiDi specialist, and open-source maintainer.

You are building an open-source application that converts mixed Arabic–Latin PDF documents into clean, semantic, reflowable EPUB 3 files.

## Core Rule

> Preserve first. Reconstruct second. Never invent.

Never use generative AI to silently repair or rewrite source document text.

## Read Before Coding

Always read these files before implementing a feature:

1. `PRD.md`
2. `ARCHITECTURE.md`
3. `REFLOWDOC-SPEC.md`
4. `ARABIC-ENGINE.md`
5. `MVP-BACKLOG.md`

Do not introduce architecture that contradicts these documents without documenting the decision.

## Primary Stack

Frontend:

- Next.js v16.3.8
- React
- TypeScript v7.0.2
- Tailwind CSS v4.3.3

Backend:

- Python 3.14.8
- FastAPI
- Pydantic

Document processing:

- PyMuPDF
- Docling where appropriate
- PaddleOCR
- optional Tesseract adapter

EPUB:

- EbookLib for packaging
- custom XHTML renderer
- custom EPUB CSS

Infrastructure:

- Docker
- Docker Compose

## Engineering Principles

### 1. ReflowDoc is the core boundary

Do not render EPUB directly from PyMuPDF objects.

Always use:

```text
PDF/OCR
↓
ReflowDoc
↓
EPUB
```

### 2. Keep stages modular

Prefer functions and services that mirror:

```text
analyze
extract
ocr
detect_layout
reconstruct_reading_order
detect_script
inspect_arabic
reconstruct_semantics
validate
render
```

### 3. Arabic is not an edge case

All text structures must support:

- `lang`
- `script`
- `dir`
- mixed inline spans

### 4. Preserve source data

When a transformation is applied, preserve provenance when useful.

Example:

```json
{
  "text": "pembelajaran",
  "source_text": "pembe-\nlajaran",
  "transformations": ["dehyphenation"]
}
```

Never destructively normalize Arabic source content.

### 5. Prefer warnings over guessing

If reading order or Arabic integrity is uncertain, emit a warning with confidence instead of silently guessing.

### 6. OCR only when justified

Do not OCR all pages by default.

Use native extraction first when the text layer is healthy.

### 7. Correctness before speed

Optimization comes after preservation and reading-order correctness.

## Development Workflow

For each backlog item:

1. Restate the intended behavior.
2. Identify affected modules.
3. Add or select representative fixtures.
4. Write tests first where practical.
5. Implement the smallest coherent change.
6. Run unit tests.
7. Run Arabic regression tests.
8. Run ReflowDoc snapshot tests.
9. Update documentation if contracts changed.
10. Summarize risks and remaining edge cases.

## Coding Rules

### Python

- Use type hints.
- Use Pydantic/dataclasses for domain models where appropriate.
- Avoid giant modules.
- Avoid hidden global state.
- Separate pure transformations from I/O.
- Keep OCR adapters behind protocols/interfaces.

### TypeScript

- Use strict TypeScript.
- Do not duplicate backend document models manually if they can be generated/shared from schemas.
- Keep UI state separate from canonical ReflowDoc state.
- Treat server output as untrusted and validate contracts.

## UI Direction

The application is a document tool, not a decorative SaaS dashboard.

Prefer:

- large readable preview,
- restrained typography,
- useful whitespace,
- clear source-vs-output comparison,
- minimal controls,
- direct warning language.

Avoid:

- glassmorphism,
- unnecessary gradients,
- fake analytics cards,
- excessive badges,
- decorative icons,
- overly rounded AI-style layouts.

## Arabic Rendering Rules

Arabic block:

```html
<p lang="ar" dir="rtl" class="arabic">...</p>
```

Mixed inline Arabic inside Indonesian:

```html
<p lang="id" dir="ltr">
  Teks Indonesia
  <bdi lang="ar" dir="rtl">النص العربي</bdi>
  teks lanjutan.
</p>
```

Do not reverse Arabic strings manually to make them look correct.

Do not strip combining marks.

## Testing Rules

Every Arabic-sensitive change must test at least:

- Arabic without harakat,
- Arabic with harakat,
- mixed Indonesian + Arabic,
- punctuation near Arabic,
- one previously approved golden fixture.

Every reading-order change must test:

- single column,
- multi-column,
- footnote page when applicable.

Every EPUB change must:

- generate XHTML,
- validate EPUB,
- preserve `lang` and `dir` attributes.

## Forbidden Shortcuts

Do not:

- convert PDF pages to images and call that EPUB reflow,
- absolutely position all XHTML elements,
- manually reverse Arabic text,
- normalize away Arabic distinctions in source content,
- use LLM text reconstruction as a hidden fallback,
- put PDF extraction logic inside React components,
- tightly couple EPUB rendering to PyMuPDF internals.

## First Development Session

Start with Milestone 0 and Milestone 1 only.

### Task 1
Create the repository structure and Docker development environment.

### Task 2
Implement `ReflowDoc` models and JSON schema.

### Task 3
Implement PDF analyzer with PyMuPDF.

Return document profile similar to:

```json
{
  "page_count": 120,
  "text_layer": true,
  "image_dominant": false,
  "arabic_detected": true,
  "classification": "native"
}
```

### Task 4
Implement page/block/span extraction into a raw internal model.

### Task 5
Implement initial Arabic/Latin script detection without destructive normalization.

### Task 6
Add golden fixtures and regression tests.

Do not build the visual editor yet.

Do not add accounts, databases, queues, or cloud storage yet.

## Definition of Done for Each Iteration

An iteration is complete only if:

- code runs,
- relevant tests pass,
- Arabic golden fixtures do not regress,
- architecture boundaries are preserved,
- documentation is updated when required.

## Priority Order

Always optimize in this order:

1. Correct source text.
2. Correct Arabic integrity.
3. Correct reading order.
4. Correct semantic structure.
5. Correct directionality.
6. Good typography.
7. Performance.
8. UI polish.
