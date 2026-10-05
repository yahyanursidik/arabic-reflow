# PRD — Open-Source Arabic–Latin PDF to EPUB Reflow Engine

## 1. Product Summary

Open-source application to convert PDF documents containing mixed Latin and Arabic text into clean, semantic, reflowable EPUB 3 files.

The product is not a simple format converter. It is a document reconstruction engine designed to preserve source text, understand page structure, respect mixed LTR/RTL directionality, reconstruct reading order, and produce EPUB output that remains comfortable to read across screen sizes.

Core principle:

> Preserve first. Reconstruct second. Never invent.

## 2. Problem Statement

PDF is primarily a page-description format. Text is often stored as positioned glyphs rather than semantic paragraphs, headings, footnotes, or quotes. This becomes especially problematic in documents that contain mixed Indonesian and Arabic content.

Common failures include:

- Arabic rendered as boxes.
- Characters separated or reversed.
- Harakat lost or detached.
- Wrong reading order in multi-column pages.
- Arabic and Latin punctuation rearranged.
- Headers, footers, and page numbers included in body text.
- Footnotes inserted into the main paragraph flow.
- Fixed-layout EPUB that behaves like a PDF rather than a reflowable book.

## 3. Product Vision

Build an open-source document reconstruction platform that can transform difficult mixed Arabic–Latin PDFs into readable, semantic, reflowable digital books while preserving the integrity of the source.

## 4. Primary Users

- Readers of Islamic books and lecture materials.
- Students and researchers.
- Islamic education institutions.
- Digital library managers.
- Small publishers.
- Developers and open-source contributors.

## 5. Primary Use Case

1. User uploads a PDF.
2. System analyzes whether the PDF is native text, scanned, or hybrid.
3. System extracts text and page layout.
4. OCR is used only where necessary.
5. Reading order is reconstructed.
6. Script and direction are detected.
7. Arabic integrity checks are performed.
8. Document is converted into ReflowDoc.
9. User reviews low-confidence blocks.
10. System renders semantic XHTML and EPUB 3.
11. EPUB is validated and exported.

## 6. Product Principles

### 6.1 Preserve Source
Do not silently alter original source text.

### 6.2 Never Invent
No generative model is allowed to auto-complete, rewrite, or replace Qur'an, hadith, citations, names, or other source content.

### 6.3 Semantic over Pixel Preservation
The target is a structurally correct, reflowable document rather than visual pixel parity with the PDF.

### 6.4 Arabic as a First-Class Script
RTL behavior, harakat, Unicode handling, mixed-direction text, and font support are core architecture concerns.

### 6.5 Privacy by Default
The core conversion pipeline must be capable of running fully offline.

### 6.6 Open Standards
Prefer EPUB 3, XHTML, CSS, Unicode, JSON, Docker, and REST APIs.

## 7. MVP Scope

### Must Have

- PDF upload.
- Native text extraction.
- Scanned-page OCR fallback.
- Hybrid PDF support.
- Arabic and Latin script detection.
- LTR/RTL detection.
- Reading-order reconstruction.
- Paragraph reconstruction.
- Basic multi-column handling.
- Arabic integrity diagnostics.
- Header/footer detection.
- Page-number removal.
- Basic footnote detection.
- Image extraction.
- ReflowDoc intermediate model.
- Reflow preview.
- Structural block editor.
- EPUB 3 generation.
- Embedded Arabic font option.
- EPUB validation.
- CLI.
- Docker support.

### Should Have

- Table extraction.
- Metadata editor.
- Cover selection.
- Conversion quality report.
- Export ReflowDoc JSON.
- Block confidence indicator.

### Could Have

- Batch conversion.
- Pluggable OCR engines.
- Chapter boundary suggestions.
- HTML/Markdown/DOCX output.
- Local library mode.

### Won't Have in MVP

- Accounts.
- Billing.
- Cloud bookshelf.
- DRM.
- Marketplace.
- Translation.
- AI rewriting.
- Collaborative editing.

## 8. Core Functional Requirements

### 8.1 PDF Analysis
The system must detect:

- page count,
- page size,
- embedded text,
- images,
- Arabic presence,
- text coverage,
- likely scanned pages,
- likely multi-column layout.

### 8.2 PDF Type Classification
Classify as:

- native-text PDF,
- scanned PDF,
- hybrid PDF.

### 8.3 Extraction Strategy

- Native page → text extraction first.
- Scanned page → OCR.
- Hybrid → per-page decision.

### 8.4 Processing Modes

- Automatic.
- Text layer only.
- Force OCR.

Default: Automatic.

### 8.5 Reading Order
Reading order must consider:

- block position,
- columns,
- alignment,
- indentation,
- text direction,
- font hierarchy,
- proximity and block relationships.

### 8.6 Language and Script Detection
Minimum supported labels:

- `id`
- `ar`
- `en`
- `unknown`

Script classification is more important than natural-language classification.

### 8.7 Arabic Integrity
Checks must include:

- Arabic Unicode ranges,
- presentation forms,
- suspicious character spacing,
- combining marks,
- harakat retention,
- punctuation placement,
- bidi anomalies,
- mixed-direction spans.

### 8.8 Paragraph Reconstruction
Reconstruct paragraphs from line-level PDF extraction while avoiding unsafe merging.

### 8.9 Dehyphenation
Apply language-aware dehyphenation to Latin text only when confidence is high.

### 8.10 Structural Reconstruction
Support:

- heading,
- paragraph,
- quote,
- list,
- image,
- caption,
- table,
- footnote,
- page break.

### 8.11 Header/Footer Removal
Detect repeated blocks in stable page regions. False positives must be minimized.

### 8.12 Footnote Handling
Footnotes should be converted to EPUB semantic notes where reliable.

### 8.13 Image Handling
Modes:

- preserve meaningful images,
- preserve all,
- text only.

Default: preserve meaningful images.

### 8.14 Table Handling
- High-confidence table → semantic HTML table.
- Low-confidence table → image fallback with warning.

### 8.15 EPUB Rendering
Target EPUB 3 with:

- semantic XHTML,
- `lang` attributes,
- `dir` attributes,
- `<bdi>` for mixed inline Arabic,
- reflowable CSS,
- navigation,
- metadata,
- optional embedded Arabic font.

## 9. User Flow

`Upload → Analyze → Process → Review → Preview → Export`

## 10. Review Interface

Desktop layout:

`Page Source | Reflow Preview | Block Inspector`

Block actions:

- change type,
- change language,
- change direction,
- merge,
- split,
- move,
- delete,
- restore,
- edit text.

User text edits must be explicitly marked as user modifications.

## 11. Quality Metrics

Track:

- text preservation rate,
- Arabic character preservation,
- harakat preservation,
- reading-order accuracy,
- footnote accuracy,
- header/footer removal accuracy,
- EPUB validation result,
- warning count.

## 12. Security and Privacy

- Validate MIME type.
- Sanitize filenames.
- Detect encrypted PDFs.
- Resource-limit public workers.
- Do not log document contents by default.
- Delete temporary hosted jobs after configurable retention.
- Passwords for encrypted documents must never be persisted.

## 13. Product Success Criteria

MVP is successful when:

1. Arabic native text remains readable.
2. Harakat are preserved on representative fixtures.
3. Inline Arabic inside Latin paragraphs renders correctly.
4. Native/scanned/hybrid PDFs are handled appropriately.
5. Typical headers and page numbers are removed.
6. Multi-column pages are reconstructed acceptably on benchmark documents.
7. Low-confidence blocks are surfaced for review.
8. Generated EPUB validates successfully.
9. Core processing works offline.
10. Docker installation works without proprietary services.

## 14. Recommended Initial Stack

### Web
- Next.js
- React
- TypeScript
- Tailwind CSS

### API
- FastAPI
- Python
- Pydantic

### Processing
- PyMuPDF
- Docling
- PaddleOCR
- Tesseract as optional fallback

### EPUB
- EbookLib
- Custom XHTML renderer
- Custom EPUB CSS

### Infrastructure
- Docker
- Docker Compose
- Temporary filesystem for MVP

## 15. Final Product Positioning

> An open-source reconstruction engine for turning complex mixed Arabic–Latin PDFs into clean, semantic, reflowable digital books.
