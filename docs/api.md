# HTTP API (Milestone 7)

`apps/api` — FastAPI service. The API layer owns job lifecycle and HTTP
contracts only; every document rule lives in the engine (ARCHITECTURE.md 3.2).
MVP storage is the temporary filesystem, no database (ARCHITECTURE.md 8):

```text
{REFLOW_STORAGE_DIR}/documents/{document_id}/
    source.pdf  profile.json  reflow.json  report.json  output.epub  job.json
```

## Endpoints

| Method | Path | Backlog | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/documents` | M7-01 | Upload a PDF (201). Magic-byte validation, 100 MB limit, filename sanitization, encrypted PDFs rejected (400/415) |
| POST | `/api/v1/documents/{id}/analyze` | M7-02 | Analyzer profile (sync) |
| POST | `/api/v1/documents/{id}/convert` | M7-03 | Start a conversion job (202, `{ocr: bool}`) |
| GET | `/api/v1/jobs/{job_id}` | M7-04 | Job status: `{status, stage, progress, warnings, error}`; stages follow ARCHITECTURE.md 6 |
| GET | `/api/v1/documents/{id}/reflow` | M7-05 | ReflowDoc JSON (404 before conversion) |
| PATCH | `/api/v1/documents/{id}/blocks/{block_id}` | M7-06 | Edit text/lang/dir of a block; sets `modified_by_user: true` |
| POST | `/api/v1/documents/{id}/export/epub` | M7-07 | Validated EPUB 3 bytes; re-renders from the current ReflowDoc so user edits are included |
| GET | `/api/v1/documents/{id}/report` | — | Quality report: profile, Arabic integrity rollup, warnings |
| GET | `/api/v1/health` | — | Liveness |
| GET | `/api/v1/documents/{id}` | M8 | Document metadata |
| GET | `/api/v1/documents/{id}/profile` | M8 | Stored analyzer profile (404 before analysis) |
| GET | `/api/v1/documents/{id}/job` | M8 | Latest conversion job for the document |
| GET | `/api/v1/documents/{id}/source/pages/{n}.png` | M8 | Page raster for the source-vs-output review pane |
| PATCH | `/api/v1/documents/{id}/metadata` | PRD 7 | Metadata editor: set book `title` / `author` on the stored ReflowDoc (404 before conversion) |
| POST | `/api/v1/documents/{id}/cover?page={n}` | PRD 7 | Render source page `n` (150 dpi PNG) and set it as the EPUB cover |
| DELETE | `/api/v1/documents/{id}/cover` | PRD 7 | Clear the cover resource and reference |

## Lifecycle

```text
POST /documents (201) → POST /convert (202, job_id)
  job: queued → processing (analyzing 5 → extracting 25 → [ocr 35] → layout 50
       → reading_order 60 → arabic_analysis 70 → reconstruction 80 →
       review_ready 85 → rendering 92 → validating 97) → completed (100)
GET /reflow → PATCH /blocks/{id} → POST /export/epub
```

Conversions run in background threads; failures set `status: "failed"` with an
`error` message. Job state is persisted per document so a restart shows the
last known state.

## Security posture (PRD section 12)

- only `%PDF-` magic bytes accepted; `text/plain` disguises get 415;
- filenames sanitized to `A-Za-z0-9._-` (path traversal impossible);
- encrypted PDFs are rejected — passwords are never accepted or stored;
- 100 MB upload cap;
- document contents are never logged.

## Block edits

Block-to-image crops use the edge-clean region renderer
(`engine.ocr.base.render_region_png`): the crop padding grows until the
outer pixel ring is free of ink, because real-world PDFs often report text
bboxes tighter than the actual glyph ink (broken subset-font metrics),
which used to clip harakat and descenders.

`PATCH .../blocks/{block_id}` supports `text`, `lang`, and `dir` for
paragraph/heading/quote blocks. A text edit replaces the paragraph's content
with a single text node (inline span reconstruction from arbitrary user text
is a later concern) and always sets `modified_by_user: true`, per PRD section
10. Export re-renders from the edited ReflowDoc.

## Running

```bash
uvicorn apps.api.main:app --reload        # dev
docker compose up api                     # container (REFLOW_STORAGE_DIR=/tmp/reflow)
```

Interactive docs: `http://localhost:8000/docs`.

## Tests

`tests/test_api.py` covers the full lifecycle with the real fixture corpus:
upload validation (non-PDF, fake PDF, encrypted, hostile filenames), analyze,
conversion to completion, reflow/report retrieval, block edits (persisted and
marked), export validity, and the empty-document (scanned) path.
