# MVP Backlog

## Milestone 0 — Repository and Test Foundation

### M0-01 Repository bootstrap
**Priority:** P0

- Create repository structure.
- Configure Python project.
- Configure Next.js app.
- Add Docker Compose.
- Add CI.

**Acceptance criteria**

- `docker compose up` boots web and API.
- CI runs Python and frontend tests.

### M0-02 Fixture corpus
**Priority:** P0

Create representative legal test fixtures:

- Indonesian-only native PDF.
- Arabic-only native PDF.
- Mixed Indonesian-Arabic PDF.
- Fully vocalized Arabic PDF.
- Two-column PDF.
- Scanned PDF.
- Hybrid PDF.
- Footnote-heavy PDF.

### M0-03 Define ReflowDoc schema
**Priority:** P0

Implement typed models and JSON serialization.

---

# Milestone 1 — Native PDF Prototype

### M1-01 PDF metadata analyzer
**Priority:** P0

Extract:

- page count,
- text coverage,
- image coverage,
- embedded fonts.

### M1-02 PyMuPDF block extraction
**Priority:** P0

Preserve:

- text,
- spans,
- bbox,
- font,
- font size,
- page number.

### M1-03 Script detection
**Priority:** P0

Classify Latin, Arabic, mixed, neutral.

### M1-04 Basic direction detection
**Priority:** P0

Produce block and span `dir`.

### M1-05 Native Arabic preservation tests
**Priority:** P0

Golden tests for Arabic and harakat.

---

# Milestone 2 — Reconstruction

### M2-01 Basic reading-order engine
**Priority:** P0

Start with single-column pages.

### M2-02 Paragraph reconstruction
**Priority:** P0

Merge line fragments safely.

### M2-03 Latin dehyphenation
**Priority:** P1

Only when confidence is high.

### M2-04 Heading detection
**Priority:** P1

Signals:

- font hierarchy,
- spacing,
- position,
- numbering.

### M2-05 Header/footer detection
**Priority:** P0

Use repeated-position heuristics.

### M2-06 Page number removal
**Priority:** P0

Preserve page provenance internally.

---

# Milestone 3 — Arabic Integrity

### M3-01 Unicode diagnostics
**Priority:** P0

### M3-02 Presentation-form detection
**Priority:** P0

### M3-03 Suspicious spacing detection
**Priority:** P0

### M3-04 Combining-mark checks
**Priority:** P0

### M3-05 BiDi diagnostics
**Priority:** P0

### M3-06 Arabic integrity report
**Priority:** P0

Expose block/page/document health.

---

# Milestone 4 — EPUB Renderer

### M4-01 XHTML renderer
**Priority:** P0

Semantic rendering for:

- heading,
- paragraph,
- quote,
- list,
- image.

### M4-02 Mixed-direction inline renderer
**Priority:** P0

Use safe bidi isolation.

### M4-03 EPUB packaging
**Priority:** P0

Generate manifest, spine, nav, metadata.

### M4-04 Arabic font embedding
**Priority:** P0

Use redistributable open font only.

### M4-05 EPUB validation
**Priority:** P0

Block severe invalid output.

---

# Milestone 5 — OCR

### M5-01 Scanned-page classifier
**Priority:** P0

### M5-02 PaddleOCR adapter
**Priority:** P0

### M5-03 Tesseract adapter
**Priority:** P2

### M5-04 Per-page OCR decision
**Priority:** P0

### M5-05 OCR confidence reporting
**Priority:** P0

### M5-06 Arabic extraction vs OCR candidate comparison
**Priority:** P1

No generative repair.

---

# Milestone 6 — Complex Layout

### M6-01 Column detection
**Priority:** P0

### M6-02 Multi-column reading order
**Priority:** P0

### M6-03 Footnote candidate detection
**Priority:** P1

### M6-04 EPUB semantic footnotes
**Priority:** P1

### M6-05 Image/caption relationships
**Priority:** P1

### M6-06 Basic table detection
**Priority:** P2

---

# Milestone 7 — API

### M7-01 Upload endpoint
**Priority:** P0

### M7-02 Analyze endpoint
**Priority:** P0

### M7-03 Conversion job endpoint
**Priority:** P0

### M7-04 Status endpoint
**Priority:** P0

### M7-05 ReflowDoc endpoint
**Priority:** P0

### M7-06 Block-edit endpoint
**Priority:** P0

### M7-07 EPUB export endpoint
**Priority:** P0

---

# Milestone 8 — Web UI

### M8-01 Upload screen
**Priority:** P0

### M8-02 Analysis summary
**Priority:** P0

### M8-03 Processing status
**Priority:** P0

### M8-04 Reflow preview
**Priority:** P0

### M8-05 Block inspector
**Priority:** P0

### M8-06 Review filters
**Priority:** P1

- Arabic issues
- reading order
- OCR
- footnotes

### M8-07 Export screen
**Priority:** P0

---

# Milestone 9 — CLI and Distribution

### M9-01 `reflow analyze`
**Priority:** P1

### M9-02 `reflow convert`
**Priority:** P1

### M9-03 Docker production image
**Priority:** P0

### M9-04 Local installation docs
**Priority:** P0

### M9-05 Contributor guide
**Priority:** P1

---

# Release Gate for v0.1

The release is blocked if:

- approved Arabic fixtures lose source characters,
- harakat regression is detected,
- generated XHTML is invalid,
- EPUB validation fails,
- mixed inline Arabic renders incorrectly in target readers,
- Docker installation is broken.

# Suggested Implementation Order

1. ReflowDoc.
2. Fixture corpus.
3. Native extraction.
4. Arabic preservation.
5. Basic reconstruction.
6. XHTML/EPUB rendering.
7. Arabic Integrity Engine.
8. OCR.
9. Complex reading order.
10. API.
11. Web review UI.
12. CLI and open-source packaging.
