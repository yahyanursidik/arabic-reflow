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
`error` message. The document job endpoint returns the latest job, including
after reconversion. Only one conversion per document may run at a time (409
for duplicate starts). Mutations and EPUB exports return 409 while converting.
After a server restart, interrupted jobs become failed and can be retried.
The MVP registry is single-process; use one API worker, not multiple workers.

## Security posture (PRD section 12)

- only `%PDF-` magic bytes accepted; `text/plain` disguises get 415;
- filenames sanitized to `A-Za-z0-9._-` (path traversal impossible);
- encrypted PDFs are rejected — passwords are never accepted or stored;
- 100 MB upload cap (the API reads at most the limit plus one byte);
- document IDs are validated before filesystem access; JSON writes use atomic replacement;
- document contents are never logged.

## Block edits

Block-to-image crops use the edge-clean region renderer
(`engine.ocr.base.render_region_png`): the crop padding grows until the
outer pixel ring is free of ink, because real-world PDFs often report text
bboxes tighter than the actual glyph ink (broken subset-font metrics),
which used to clip harakat and descenders.

For a source quotation split into touching fragments, `POST
.../blocks/{block_id}/render-image` also accepts an optional JSON body
`{"block_ids": ["first", "second"]}`. The anchor must be the first ID;
all requested text blocks must be consecutive siblings, in reading order,
with source geometry on the same PDF page. The action replaces the group
with one image of its combined source region, avoiding duplicate glyphs at
fragment boundaries. `restore-text` on that image restores all original
fragments in order, preserving text from before their first edits.

`PATCH .../blocks/{block_id}` supports `text`, `lang`, and `dir` for
paragraph/heading/quote blocks. Mixed-script paragraph edits retain inline
language/direction isolation without altering any character, including harakat.
Edits set `modified_by_user: true`, per PRD section 10. Text before the first
edit or normalization is preserved for explicit restoration through
`POST .../blocks/{block_id}/restore-text`. This restores the whole initial
block, not the immediately preceding edit. Report responses include
`review.restorable_block_ids` so the UI only offers restoration when available.
Arabic integrity annotations refresh after edits, and `/report` is assembled
from the current ReflowDoc rather than a stale conversion-time cache.
Export re-renders from the edited ReflowDoc.

`Content-Disposition` is exposed to web clients through CORS so downloaded
EPUBs keep their filename. For non-default web origins, set
`REFLOW_CORS_ORIGINS` to a comma-separated list of explicit origins.

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

## Engine/review feature extensions

- `GET /api/v1/capabilities`: OCR runtimes, available language data, processing
  modes, upload limit, and optional EPUBCheck availability. It does not initialize
  Paddle models or download anything.
- `POST .../convert`: optional `mode: native | auto | force`, `engine: paddle |
  tesseract`, and `languages: [ar, id, en]`. Legacy `ocr: bool` remains accepted;
  an explicit mode takes precedence. Auto on a healthy native PDF needs no OCR
  runtime. Force requires explicit user consent in the UI.
- `PATCH .../blocks/{block_id}` also accepts `type: paragraph | heading | quote`,
  `level: 1..6` (heading only), and `alt` (image only). Invalid type/field combinations
  return 422 before writing originals. Nested list/footnote paragraphs are supported.
- `POST .../blocks/{block_id}/move` accepts `{direction: up | down}`. Moves only
  within its sibling group and rejects boundary/cross-group moves (422).
- `/report` now contains `quality` (recursive counts, page review targets, structural
  issues, and `can_export`) and `ocr` (persisted conversion decisions/confidence,
  without rejected candidate text).
- `POST .../export/epub?validation=w3c` performs optional local EPUBCheck validation;
  unavailable validator returns 503, rejected package returns 422. Internal validation
  always runs. Empty content, duplicate IDs, and broken resource references block export.

See `docs/engine-features.md` for local setup and supported UI subfeatures.
# Perbaikan teks eksplisit

- `POST /api/v1/documents/{id}/blocks/{block_id}/repair-text`: perbaiki satu
  paragraf/judul/kutipan tanpa menebak kata. Cadangan sebelum suntingan pertama
  tetap tersedia melalui `.../restore-text`.
- `POST /api/v1/documents/{id}/repair-text` dengan JSON
  `{"block_ids": ["block-001", "block-002"]}`: memproses ID yang dipilih sekali,
  melewati blok nonteks dan blok yang sudah disunting. Maksimal 5000 ID.
- Respons kedua endpoint memuat `changed_block_ids`, `unchanged_block_ids`,
  `skipped_block_ids`, dan `review_block_ids`. Tidak ada perubahan aman berarti
  blok tetap utuh, bukan klaim perbaikan berhasil.
- Aksi terkunci selama konversi (409). Batch dengan ID yang tidak dikenal
  ditolak sebelum perubahan apa pun (404). Isi dan laporan dibaca ulang setelah
  aksi; ekspor EPUB berikutnya memakai hasil terbaru.
