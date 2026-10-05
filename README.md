# Arabic Reflow

**Open-source Arabic–Latin document reconstruction and EPUB engine.**

Arabic Reflow helps convert complex PDFs containing **Arabic, Indonesian, and other Latin-script text** into clean, semantic, reflowable EPUB documents.

It is designed for documents where ordinary PDF-to-EPUB converters often fail, especially when dealing with:

- Arabic text
- mixed RTL + LTR content
- harakat
- Arabic quotations
- bilingual paragraphs
- footnotes
- multi-column layouts
- scanned pages
- embedded fonts
- broken reading order

> Preserve the source. Reconstruct the structure. Respect Arabic.

---

## Why Arabic Reflow?

PDF is a page-layout format.

It usually stores things like:

```text
glyphs
coordinates
fonts
positions
page geometry
```

rather than meaningful document structure such as:

```text
headings
paragraphs
quotes
footnotes
chapters
reading order
```

That becomes especially problematic when a document contains both:

```text
LTR + RTL
```

For example:

> Hadits ini diriwayatkan dari أبي هريرة رضي الله عنه dalam Shahih Muslim.

A conventional converter may produce:

- reversed Arabic
- disconnected letters
- misplaced punctuation
- missing harakat
- broken paragraphs
- incorrect reading order
- square boxes instead of Arabic glyphs

Arabic Reflow approaches the problem as **document reconstruction**, not simple format conversion.

---

## Core Pipeline

```text
PDF
↓
PDF Analysis
↓
Text / OCR Extraction
↓
Layout Understanding
↓
Reading Order Reconstruction
↓
Language & Script Detection
↓
Arabic Integrity Analysis
↓
Document Reconstruction
↓
ReflowDoc
↓
Semantic XHTML
↓
EPUB 3
↓
Validation
```

---

## Key Features

### Arabic-first processing

Arabic is treated as a first-class script.

The engine is designed around:

- Unicode Arabic
- RTL direction
- mixed-direction text
- combining marks
- harakat preservation
- Arabic punctuation
- Arabic font handling
- inline Arabic inside Latin paragraphs

---

### Mixed RTL + LTR support

Arabic Reflow can reconstruct content such as:

```text
Hadits ini berasal dari أبي هريرة رضي الله عنه dan diriwayatkan oleh Muslim.
```

into proper semantic XHTML with correct directionality.

---

### Arabic Integrity Checker

The engine can detect common extraction problems such as:

```text
ا ل س ل ا م
```

instead of:

```text
السلام
```

It also checks for:

- suspicious spacing
- Arabic Presentation Forms
- broken combining marks
- possible reversed ordering
- character fragmentation
- RTL anomalies

---

### OCR only when needed

Arabic Reflow does not OCR everything by default.

It can classify documents as:

```text
Native Text PDF

Scanned PDF

Hybrid PDF
```

and choose extraction strategies per page.

---

### Semantic reflow

The goal is not to recreate the PDF pixel-by-pixel.

Instead:

```text
PDF Layout
↓
Document Structure
↓
Reflowable EPUB
```

Headings become headings.

Lists become lists.

Footnotes become footnotes.

Arabic paragraphs remain RTL.

---

### ReflowDoc

Arabic Reflow uses an intermediate document representation called:

# ReflowDoc

Example:

```json
{
  "type": "quote",
  "lang": "ar",
  "dir": "rtl",
  "text": "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ"
}
```

This separates extraction from rendering.

That means the same reconstructed document can eventually support:

```text
EPUB
HTML
Markdown
DOCX
JSON
```

---

## Design Principles

Arabic Reflow follows several core principles:

### Preserve first

Do not unnecessarily modify the original text.

### Never invent

The conversion engine must never generate or guess missing content.

### Semantic over visual

Prefer meaningful structure over fixed-position replication.

### Arabic is not an edge case

RTL and Arabic processing are core architectural concerns.

### Warn instead of guessing

Low-confidence blocks should be flagged for review.

### Local-first

The core conversion pipeline should be able to run without sending documents to external services.

---

## Planned Stack

### Web

```text
Next.js
React
TypeScript
Tailwind CSS
```

### API

```text
Python
FastAPI
Pydantic
```

### PDF Processing

```text
PyMuPDF
Docling
```

### OCR

```text
PaddleOCR
Tesseract
```

### EPUB

```text
EbookLib
Custom XHTML renderer
Custom CSS
```

### Infrastructure

```text
Docker
Docker Compose
```

---

## Target Documents

Arabic Reflow is especially intended for:

- Islamic books
- translated Arabic books
- lecture notes
- academic modules
- bilingual educational material
- theses
- research papers
- Islamic studies documents
- Arabic quotations inside Latin documents
- scanned books
- mixed Arabic–Indonesian documents

The architecture is intentionally not limited to Indonesian.

Future combinations may include:

```text
English + Arabic
Malay + Arabic
French + Arabic
Turkish + Arabic
```

---

## MVP Scope

The initial version focuses on:

- PDF upload
- native text extraction
- scanned PDF OCR fallback
- Indonesian + Arabic script detection
- RTL/LTR handling
- paragraph reconstruction
- reading-order reconstruction
- Arabic integrity diagnostics
- header/footer removal
- image preservation
- basic footnote handling
- EPUB 3 export
- embedded Arabic fonts
- EPUB validation
- Docker-based local deployment
- CLI support

---

## What This Project Is Not

Arabic Reflow is not intended to be:

- a pixel-perfect PDF clone
- a translation engine
- an AI rewriting tool
- an automatic religious-text correction system
- a DRM platform
- a commercial ebook marketplace
- a cloud bookshelf

The goal is document reconstruction and reflow.

---

## AI Policy

The core conversion pipeline does **not require an LLM**.

Generative AI must never silently rewrite:

- Qur'an text
- hadith
- Arabic quotations
- names
- references
- source paragraphs

Future AI-assisted features may only provide optional structural suggestions such as:

- probable chapter boundaries
- heading hierarchy
- block classification

The source text remains authoritative.

---

## Architecture

```text
                    User
                      │
                      ▼
                Next.js Web
                      │
                      ▼
                  FastAPI
                      │
                      ▼
                PDF Analyzer
                      │
              ┌───────┴───────┐
              ▼               ▼
       Text Extraction        OCR
              │               │
              └───────┬───────┘
                      ▼
               Layout Analysis
                      │
                      ▼
                Reading Order
                      │
                      ▼
              Script Detection
                      │
                      ▼
             Arabic Integrity
                      │
                      ▼
         Document Reconstruction
                      │
                      ▼
                  ReflowDoc
                      │
              ┌───────┴───────┐
              ▼               ▼
          Web Preview         EPUB
                                │
                                ▼
                          EPUB Validation
```

---

## Development Priorities

The project intentionally prioritizes:

```text
1. Correct text
2. Correct Arabic
3. Correct reading order
4. Correct document structure
5. Correct directionality
6. Good typography
7. Speed
```

A fast converter that corrupts Arabic is not considered successful.

---

## Current Status

Arabic Reflow is currently in early development.

Initial work focuses on:

```text
ReflowDoc schema
↓
PDF extraction
↓
Arabic preservation
↓
EPUB rendering
↓
Golden test corpus
↓
Arabic Integrity Engine
```

The project should not be considered production-ready yet.

---

## Contributing

Contributions are welcome.

Areas where help will be especially valuable:

- Arabic Unicode processing
- Unicode Bidirectional Algorithm
- PDF text extraction
- OCR
- document layout analysis
- EPUB
- accessibility
- multilingual typography
- test fixtures
- Arabic document datasets
- technical documentation

Please read:

```text
CONTRIBUTING.md
ARCHITECTURE.md
ARABIC-ENGINE.md
REFLOWDOC-SPEC.md
```

before working on core conversion behavior.

---

## Testing Philosophy

Every core change should be tested against representative documents.

Test categories include:

```text
native text
Arabic only
Indonesian only
Arabic + Indonesian
fully vocalized Arabic
two-column layout
footnotes
scanned pages
hybrid PDFs
unusual embedded fonts
```

Regression in Arabic text preservation is considered a release blocker.

---

## Privacy

The project is designed to support local processing.

When self-hosted:

> Your documents do not need to leave your machine.

Arabic Reflow should not require external document-processing APIs for its core functionality.

---

## License

Licensed under the **Apache License 2.0**.

See:

```text
LICENSE
```

for details.

Third-party libraries, OCR models, and bundled fonts may have their own licenses.

---

## Project Philosophy

```text
Preserve the source.

Understand the structure.

Respect Arabic.

Respect directionality.

Reflow instead of reproducing pixels.

Warn instead of guessing.

Never invent content.

Stay open.
```

---

## Vision

Arabic Reflow starts with:

> PDF → EPUB

But the larger goal is:

> **an open-source multilingual document reconstruction engine for mixed LTR and RTL content.**

---

## Getting Started (Development)

Requires Python 3.11+ (project targets 3.14) and Node 20+.

```bash
# Engine + tests
python -m venv .venv
source .venv/bin/activate            # Windows Git Bash: .venv/Scripts/activate
pip install -e ".[api,dev]"
pytest

# Regenerate fixtures / golden records only when they intentionally change
python scripts/make_fixtures.py
python scripts/update_golden.py

# Check the shared ReflowDoc JSON schema after model changes
python -m engine.reflowdoc.schema --check

# Web app
cd apps/web
npm install
npm run dev
```

### Docker

```bash
docker compose up    # api on :8000, web on :3000
```

### PDF to EPUB in three lines

```python
from engine.pipeline import build_epub

result, data, report = build_epub("book.pdf")   # ReflowDoc + validated EPUB 3
open("book.epub", "wb").write(data)
```

See `docs/` for the reconstruction heuristics (`docs/reconstruction.md`),
the Arabic integrity engine (`docs/arabic-integrity.md`), the EPUB rendering
contract (`docs/epub.md`), and the fixture corpus (`docs/fixtures.md`).

### Repository layout

```text
engine/        processing engine (analyzer, extraction, arabic, reflowdoc, ...)
apps/web/      Next.js review UI scaffold
apps/api/      FastAPI service
packages/      shared generated schemas (reflowdoc.schema.json)
tests/         fixtures + golden records + snapshots
docs/          contributor documentation (fixture corpus, etc.)
```

Governing documents: `PRD.md`, `ARCHITECTURE.md`, `REFLOWDOC-SPEC.md`,
`ARABIC-ENGINE.md`, `MVP-BACKLOG.md`, `VIBE-CODING-INSTRUCTIONS.md` — read
them before implementing any feature.
