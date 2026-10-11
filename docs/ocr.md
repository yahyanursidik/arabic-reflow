# OCR Layer (Milestone 5)

OCR is a **fallback, never the default** (ARCHITECTURE.md rule 4). Native
extraction always runs first; OCR steps in only where the text layer is
missing or the native Arabic is demonstrably corrupted.

## Interface

`engine/ocr/base.py` defines the replaceable adapter interface
(ARCHITECTURE.md 3.5):

```python
class OcrEngine(Protocol):
    name: str
    def recognize(self, image: bytes, languages: list[str]) -> OcrPage: ...
```

`OcrPage` carries lines/words with bboxes and per-item confidence. Engines
are lazily imported: the package installs and the full test suite runs
without any OCR dependency.

## Engines

| Name | Backlog | Extra | Notes |
| --- | --- | --- | --- |
| `paddle` | M5-02 (P0) | `pip install ".[ocr-paddle]"` | PaddleOCR, Arabic primary |
| `tesseract` | M5-03 (P2) | `pip install ".[ocr-tesseract]"` | needs the tesseract binary + `ara`/`ind` language data |

Requesting an engine whose dependency is missing raises
`OcrEngineUnavailable` with install guidance; `available_engines()` lists
available runtimes without initializing/downloading models. Tesseract checks
the executable and requested language packs, not just the Python package.
PaddleOCR adapters support both v2 `.ocr()` and v3 `.predict()` APIs; readiness
for Paddle indicates installed packages, not a guarantee that models exist.

## Decisions (M5-04) and confidence (M5-05)

`engine/ocr/decision.py`:

- a page goes to OCR when it has no usable text layer (scanned-like or
  fewer than 20 characters), or the Arabic integrity is demonstrably poor;
- recognized text is synthesized into the **same raw model** the native
  extractor produces (`OcrSynthesized` font), so layout, reconstruction,
  and rendering are unchanged downstream;
- warnings: `OCR_USED` (info, per page), `OCR_LOW_CONFIDENCE` (warning when
  mean word confidence < 0.7).

## Native vs OCR comparison (M5-06)

For pages that have *some* native text, candidates are compared by Arabic
integrity score (`engine.arabic.integrity`):

- the higher-integrity candidate wins;
- ties go to native extraction (preserve first);
- pages without Arabic keep native extraction — a real text layer beats
  synthesized text even when OCR confidence is high;
- no generative repair happens anywhere, and the rejected candidate is kept
  in `OcrReport.rejected_candidates` for diagnostics
  (`OCR_CANDIDATE_REPLACED_NATIVE` warning when OCR wins).

## Usage

```python
from engine.ocr.engines import get_engine
from engine.pipeline import build_reflowdoc

engine = get_engine("paddle")            # or "tesseract"
result = build_reflowdoc("book.pdf", ocr_engine=engine)
```

Without an engine, scanned pages simply produce no text (status quo) — the
decision stage is pure and fully unit-tested against a fake engine.

## Explicit processing modes

The API accepts `mode: native | auto | force` and `languages: [ar, id, en]`.
Legacy `{ocr: false}` maps to native and `{ocr: true}` maps to auto.
Native preserves extraction only; auto uses per-page decisions and keeps
the better native candidate when OCR is not better. Force replaces every
page with OCR output only after explicit user selection/confirmation.
The original PDF always remains available. Force is not a text repair tool.

Tesseract language labels map to `ara`, `ind`, and `eng`. A language pack
must exist for every selected language; missing packs are explained in
`GET /api/v1/capabilities`. Recognition has a 120-second per-page timeout.
OCR confidence is propagated to source blocks, and selected OCR pages get
`OCR_USED` / `OCR_LOW_CONFIDENCE` markers. A rejected OCR attempt is not
misreported as selected output.

API quality reports retain page decisions, selection status, and confidence
under `ocr`; rejected candidate text is not included in the public report.
Local setup and actual runtime verification: `docs/engine-features.md`.
