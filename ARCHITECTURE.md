# Architecture

## 1. Architectural Goal

Separate input extraction from semantic reconstruction and final rendering.

The key rule is:

`Input Adapter → ReflowDoc → Output Renderer`

This prevents EPUB-specific concerns from leaking into PDF parsing and allows future inputs and outputs without rewriting the core engine.

## 2. High-Level Architecture

```text
User
  ↓
Next.js Web
  ↓
FastAPI
  ↓
Job Orchestrator
  ↓
PDF Analyzer
  ↓
Extraction Strategy
  ├─ PyMuPDF
  └─ OCR
       ├─ PaddleOCR
       └─ Tesseract fallback
  ↓
Layout Analysis
  ↓
Reading Order Engine
  ↓
Language / Script Detection
  ↓
Arabic Integrity Engine
  ↓
Document Reconstruction
  ↓
ReflowDoc
  ├─ Web Preview
  ├─ EPUB Renderer
  ├─ JSON Export
  └─ Future renderers
```

## 3. Core Components

### 3.1 Web App
Responsibilities:

- upload,
- settings,
- progress,
- quality warnings,
- source/preview comparison,
- block editing,
- export.

The web layer must not implement document parsing rules.

### 3.2 API Layer
Responsibilities:

- job lifecycle,
- file validation,
- conversion configuration,
- ReflowDoc retrieval,
- block updates,
- export endpoints.

### 3.3 Analyzer
Determines:

- native vs scanned vs hybrid,
- page-level text coverage,
- image density,
- likely language/script distribution,
- candidate problematic pages.

### 3.4 Extraction Layer
Provides raw blocks, lines, spans, glyph metadata, bounding boxes, fonts, and images.

### 3.5 OCR Layer
Must be replaceable through a common adapter interface.

Example:

```python
class OcrEngine(Protocol):
    def recognize(self, image, languages: list[str]) -> OcrPage:
        ...
```

### 3.6 Layout Engine
Responsibilities:

- page region detection,
- column detection,
- block grouping,
- title/body/footnote zoning,
- image/caption relationships.

### 3.7 Reading Order Engine
Must not use simple `y,x` sorting as the only heuristic.

Inputs:

- block geometry,
- column model,
- script direction,
- font hierarchy,
- adjacency,
- detected regions.

Outputs:

- ordered block graph,
- confidence score,
- warnings.

### 3.8 Arabic Engine
Dedicated module for:

- Arabic script detection,
- Unicode diagnostics,
- BiDi checks,
- harakat preservation checks,
- presentation-form detection,
- suspicious spacing,
- Arabic block confidence.

### 3.9 Reconstruction Engine
Converts raw page primitives to semantic blocks:

- heading,
- paragraph,
- quote,
- list,
- image,
- caption,
- table,
- footnote.

### 3.10 ReflowDoc
Canonical intermediate representation.

No renderer may directly depend on PDF internals.

### 3.11 EPUB Renderer
Consumes ReflowDoc and produces:

- XHTML,
- CSS,
- navigation,
- OPF metadata,
- images,
- fonts,
- final EPUB package.

## 4. Proposed Repository Structure

```text
reflow/
├── apps/
│   ├── web/
│   └── api/
├── engine/
│   ├── analyzer/
│   ├── extraction/
│   ├── ocr/
│   ├── layout/
│   ├── language/
│   ├── arabic/
│   ├── reconstruction/
│   ├── reflowdoc/
│   ├── epub/
│   └── validation/
├── packages/
│   └── schemas/
├── tests/
│   ├── fixtures/
│   ├── golden/
│   └── snapshots/
├── docs/
├── scripts/
├── docker/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## 5. Pipeline Contract

Each stage should receive and return typed data structures.

Recommended conceptual sequence:

```python
profile = analyze(pdf)
raw_document = extract(pdf, profile)
layout_document = detect_layout(raw_document)
ordered_document = reconstruct_reading_order(layout_document)
scripted_document = detect_scripts(ordered_document)
checked_document = inspect_arabic(scripted_document)
reflow_doc = reconstruct_semantics(checked_document)
validation = validate_reflow(reflow_doc)
epub = render_epub(reflow_doc)
```

## 6. Job Model

```json
{
  "id": "uuid",
  "status": "processing",
  "stage": "reading_order",
  "progress": 44,
  "warnings": [],
  "created_at": "..."
}
```

Recommended stages:

- uploaded,
- analyzing,
- extracting,
- ocr,
- layout,
- reading_order,
- arabic_analysis,
- reconstruction,
- review_ready,
- rendering,
- validating,
- completed,
- failed.

## 7. API Shape

```text
POST   /api/v1/documents
POST   /api/v1/documents/{id}/analyze
POST   /api/v1/documents/{id}/convert
GET    /api/v1/documents/{id}/reflow
PATCH  /api/v1/documents/{id}/blocks/{block_id}
GET    /api/v1/jobs/{id}
POST   /api/v1/documents/{id}/export/epub
GET    /api/v1/documents/{id}/report
```

## 8. Storage

MVP:

```text
/tmp/reflow/{job_id}/
├── source.pdf
├── pages/
├── images/
├── reflow.json
├── report.json
└── output.epub
```

No database is required initially.

## 9. Future Scalable Deployment

When hosted usage grows:

- API nodes stateless.
- Background workers.
- Redis-compatible queue.
- PostgreSQL for durable job metadata.
- S3-compatible object storage.
- Container resource isolation.

These must remain optional so self-hosting stays simple.

## 10. Error Philosophy

Errors and uncertainty should be explicit.

Example warning codes:

```text
LOW_ARABIC_CONFIDENCE
READING_ORDER_UNCERTAIN
FOOTNOTE_UNCERTAIN
TABLE_FALLBACK_IMAGE
OCR_USED
OCR_LOW_CONFIDENCE
FONT_SUBSTITUTED
```

No silent generative repair.

## 11. Testing Architecture

### Unit
Every engine module must be unit-testable without running the web app.

### Snapshot
Known PDF → expected ReflowDoc fragment.

### Golden
Representative files manually reviewed and approved.

### EPUB
Validate generated EPUB and inspect output on multiple readers.

## 12. Architecture Decision Rules

1. Correctness before speed.
2. No hidden source mutation.
3. ReflowDoc is the boundary between parsing and rendering.
4. OCR is a fallback, not the default.
5. Arabic processing has dedicated tests.
6. Core functionality must work offline.
7. Every heuristic should expose confidence where practical.
