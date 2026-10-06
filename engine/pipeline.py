"""Pipeline wiring following ARCHITECTURE.md section 5.

Implemented stages:

    analyze → extract → detect_layout (furniture) →
    reconstruct_reading_order → detect_scripts → reconstruct_semantics

Later stages (Arabic integrity, validation, rendering) plug in as they land.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.analyzer.analyzer import analyze
from engine.analyzer.models import DocumentProfile
from engine.arabic.detector import classify_block, classify_script, infer_direction
from engine.extraction.extractor import extract
from engine.extraction.models import RawDocument
from engine.layout.furniture import detect_layout
from engine.layout.models import LayoutReport, OrderReport
from engine.layout.reading_order import reconstruct_reading_order
from engine.reflowdoc.models import ReflowDocument
from engine.reconstruction.engine import reconstruct_semantics


def detect_scripts(raw: RawDocument) -> RawDocument:
    """Annotate spans and blocks with script and direction (M1-03, M1-04).

    Annotation only: text is never altered or normalized.
    """
    for page in raw.pages:
        for block in page.blocks:
            if block.type != "text":
                continue
            for line in block.lines:
                for span in line.spans:
                    span.script = classify_script(span.text)
                    span.dir = infer_direction(span.text)
            decision = classify_block(block.text)
            block.script = decision.script
            block.dir = decision.dir
    return raw


def analyze_and_extract(source: str | bytes) -> tuple[DocumentProfile, RawDocument]:
    """Analyze then extract; the two leading stages of the pipeline contract."""
    profile = analyze(source)
    raw = extract(source)
    return profile, raw


@dataclass
class ReconstructionResult:
    """Everything the pipeline produces up to (but excluding) rendering."""

    profile: DocumentProfile
    document: ReflowDocument
    layout: LayoutReport
    order: OrderReport


def build_reflowdoc(
    source: str | bytes,
    *,
    ocr_engine: "object | None" = None,  # engine.ocr.base.OcrEngine
    ocr_languages: list[str] | None = None,
) -> ReconstructionResult:
    """Run the full implemented pipeline: PDF/OCR in, ReflowDoc out.

    When an OCR engine is supplied, scanned pages and corrupted-Arabic pages
    go through the OCR stage (M5) with native-vs-OCR comparison.
    """
    profile = analyze(source)
    raw = extract(source)

    ocr_report = None
    if ocr_engine is not None:
        from engine.ocr.decision import apply_ocr

        raw, ocr_report = apply_ocr(source, profile, raw, ocr_engine, ocr_languages)

    raw, layout_report = detect_layout(raw)
    raw, order_report = reconstruct_reading_order(raw, profile, layout_report)
    raw = detect_scripts(raw)
    from engine.reconstruction.engine import _table_page_renderer

    document = reconstruct_semantics(
        profile, raw, layout_report, order_report,
        page_renderer=_table_page_renderer(source),
    )

    if ocr_report is not None:
        from engine.reflowdoc.models import ReflowWarning

        for code, message, page in ocr_report.warnings:
            document.warnings.append(
                ReflowWarning(
                    code=code,
                    severity="info" if code == "OCR_USED" else "warning",
                    message=message,
                    source_page=page,
                )
            )

    return ReconstructionResult(
        profile=profile,
        document=document,
        layout=layout_report,
        order=order_report,
    )


def build_epub(source: str | bytes, *, embed_arabic_font: bool | None = None):
    """PDF in, validated EPUB 3 out (M4 export gate).

    Raises engine.validation.epub.EPUBValidationError when the package has
    severe structural problems.
    """
    from engine.epub.renderer import render_epub
    from engine.validation.epub import assert_valid

    result = build_reflowdoc(source)
    data = render_epub(result.document, embed_arabic_font=embed_arabic_font)
    report = assert_valid(data)
    return result, data, report
