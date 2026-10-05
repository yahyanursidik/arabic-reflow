"""Per-page OCR decisions and candidate comparison (backlog M5-04, M5-05, M5-06).

Policy (PRD 8.3, ARCHITECTURE.md rule 4): OCR is a fallback, never the
default. A page goes to OCR when it has no usable text layer, or when its
native Arabic extraction is corrupted — and the native-vs-OCR comparison
selects the higher-integrity candidate without any generative rewriting.
The rejected candidate stays in the report for diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pymupdf

from engine.analyzer.models import DocumentProfile
from engine.arabic.integrity import inspect_text, level_of
from engine.arabic.report import LEVEL_PROBLEM
from engine.arabic.unicode import is_arabic_letter
from engine.extraction.models import RawBlock, RawDocument, RawLine, RawPage, RawSpan
from engine.ocr.base import OcrEngine, OcrPage, render_page_png

WARN_OCR_USED = "OCR_USED"
WARN_OCR_LOW_CONFIDENCE = "OCR_LOW_CONFIDENCE"
WARN_OCR_CANDIDATE_REPLACED_NATIVE = "OCR_CANDIDATE_REPLACED_NATIVE"

OCR_FONT = "OcrSynthesized"
MIN_OCR_MEAN_CONFIDENCE = 0.7


@dataclass
class PageDecision:
    page: int
    use_ocr: bool
    reason: str  # 'no_text_layer' | 'low_arabic_confidence' | 'healthy_native'


@dataclass
class OcrReport:
    decisions: list[PageDecision] = field(default_factory=list)
    ocr_pages: list[int] = field(default_factory=list)
    replaced: dict[int, str] = field(default_factory=dict)  # page -> reason
    rejected_candidates: dict[int, OcrPage] = field(default_factory=dict)
    mean_confidence: dict[int, float] = field(default_factory=dict)

    @property
    def warnings(self) -> list[tuple[str, str, int | None]]:
        """(code, message, page) tuples for the document warning list."""
        result: list[tuple[str, str, int | None]] = []
        for page in self.ocr_pages:
            result.append((WARN_OCR_USED, f"Page {page} was recognized via OCR.", page))
        for page, confidence in self.mean_confidence.items():
            if confidence < MIN_OCR_MEAN_CONFIDENCE:
                result.append(
                    (
                        WARN_OCR_LOW_CONFIDENCE,
                        f"OCR confidence on page {page} is low ({confidence:.2f}).",
                        page,
                    )
                )
        for page, reason in self.replaced.items():
            result.append(
                (
                    WARN_OCR_CANDIDATE_REPLACED_NATIVE,
                    f"Page {page}: OCR candidate selected over native extraction ({reason}).",
                    page,
                )
            )
        return result


def decide_pages(profile: DocumentProfile, raw: RawDocument) -> list[PageDecision]:
    """Decide per page whether OCR is warranted (M5-04)."""
    decisions: list[PageDecision] = []
    profile_pages = {p.page: p for p in profile.pages}
    for page in raw.pages:
        signals = profile_pages.get(page.page)
        text_chars = sum(len(b.text) for b in page.blocks)
        if signals is not None and signals.scanned_like:
            decisions.append(PageDecision(page.page, True, "no_text_layer"))
        elif text_chars < 20:
            decisions.append(PageDecision(page.page, True, "no_text_layer"))
        else:
            decisions.append(PageDecision(page.page, False, "healthy_native"))
    return decisions


def _open(source: str | bytes) -> pymupdf.Document:
    if isinstance(source, bytes):
        return pymupdf.open(stream=source, filetype="pdf")
    return pymupdf.open(source)


def ocr_raw_page(
    source: str | bytes, page_number: int, engine: OcrEngine,
    languages: list[str] | None = None, dpi: int = 200,
) -> tuple[OcrPage, RawPage]:
    """Render a page, recognize it, and synthesize a RawPage from the result.

    The synthesized page uses the raw model with an 'OcrSynthesized' font so
    the rest of the pipeline is unchanged; provenance stays in OcrReport.
    """
    doc = _open(source)
    try:
        pdf_page = doc.load_page(page_number - 1)
        rect = pdf_page.rect
        image = render_page_png(pdf_page, dpi=dpi)
    finally:
        doc.close()

    ocr_page = engine.recognize(image, languages or [])
    scale_x = rect.width / ocr_page.width if ocr_page.width else 1.0
    scale_y = rect.height / ocr_page.height if ocr_page.height else 1.0

    blocks: list[RawBlock] = []
    for index, line in enumerate(ocr_page.lines, start=1):
        bbox = (
            line.bbox[0] * scale_x,
            line.bbox[1] * scale_y,
            line.bbox[2] * scale_x,
            line.bbox[3] * scale_y,
        )
        size = max(6.0, (bbox[3] - bbox[1]) * 0.8)
        blocks.append(
            RawBlock(
                number=index,
                type="text",
                bbox=bbox,
                lines=[
                    RawLine(
                        bbox=bbox,
                        spans=[
                            RawSpan(
                                text=" ".join(w.text for w in line.words),
                                font=OCR_FONT,
                                size=round(size, 1),
                                bbox=bbox,
                            )
                        ],
                    )
                ],
            )
        )

    raw_page = RawPage(
        page=page_number,
        width=round(rect.width, 2),
        height=round(rect.height, 2),
        rotation=0,
        blocks=blocks,
        images=[],
    )
    return ocr_page, raw_page


def _arabic_integrity_score(text: str) -> float | None:
    if not any(is_arabic_letter(ch) for ch in text):
        return None
    integrity, _ = inspect_text(text)
    return integrity.score


def prefer_candidate(
    native: RawPage, ocr_page: OcrPage, ocr_raw: RawPage
) -> tuple[RawPage, str]:
    """M5-06: pick the higher-integrity candidate without generative repair.

    Arabic-bearing pages are compared by Arabic integrity score; ties go to
    the native extraction (preserve first). Pages without Arabic keep native
    extraction (a text layer, however poor, beats synthesized text).
    """
    native_text = "\n".join(b.text for b in native.blocks)
    ocr_text = ocr_page.text
    native_score = _arabic_integrity_score(native_text)
    ocr_score = _arabic_integrity_score(ocr_text)

    if native_score is None or ocr_score is None:
        return native, "native_kept_no_arabic_comparison"
    if level_of(ocr_score) == LEVEL_PROBLEM and level_of(native_score) != LEVEL_PROBLEM:
        return native, "native_kept_higher_integrity"
    if ocr_score > native_score:
        return ocr_raw, "ocr_higher_integrity"
    return native, "native_kept_higher_integrity"


def apply_ocr(
    source: str | bytes,
    profile: DocumentProfile,
    raw: RawDocument,
    engine: OcrEngine,
    languages: list[str] | None = None,
) -> tuple[RawDocument, OcrReport]:
    """Run the OCR stage over a raw document (M5-04/05/06)."""
    report = OcrReport()
    report.decisions = decide_pages(profile, raw)

    new_pages: list[RawPage] = []
    for page, decision in zip(raw.pages, report.decisions):
        if not decision.use_ocr:
            new_pages.append(page)
            continue
        ocr_page, ocr_raw = ocr_raw_page(source, page.page, engine, languages)
        report.ocr_pages.append(page.page)
        report.mean_confidence[page.page] = round(ocr_page.mean_confidence, 3)

        native_text = "\n".join(b.text for b in page.blocks)
        if native_text.strip():
            chosen, reason = prefer_candidate(page, ocr_page, ocr_raw)
            report.rejected_candidates[page.page] = ocr_page
            if chosen is ocr_raw:
                report.replaced[page.page] = reason
                new_pages.append(ocr_raw)
            else:
                new_pages.append(page)
        else:
            new_pages.append(ocr_raw)

    updated = raw.model_copy(update={"pages": new_pages})
    return updated, report
