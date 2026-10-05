"""Conversion service: runs the engine pipeline stage by stage (M7-03).

The API layer owns job lifecycle only — every document rule lives in the
engine (ARCHITECTURE.md 3.2). Stage names follow ARCHITECTURE.md section 6.
"""

from __future__ import annotations

import traceback

from apps.api.jobs import JobStore
from apps.api.storage import DocumentStore
from engine.analyzer.analyzer import analyze
from engine.arabic.report import document_report
from engine.epub.renderer import render_epub
from engine.extraction.extractor import extract
from engine.layout.furniture import detect_layout
from engine.layout.reading_order import reconstruct_reading_order
from engine.ocr.decision import apply_ocr
from engine.ocr.engines import get_engine
from engine.pipeline import detect_scripts
from engine.reflowdoc.models import ReflowWarning
from engine.reconstruction.engine import reconstruct_semantics
from engine.validation.epub import assert_valid


def build_report(profile, document) -> dict:
    """Quality report (PRD section 11) assembled from engine outputs."""
    return {
        "generated_at": None,  # filled by the caller for determinism in tests
        "profile": profile.model_dump(),
        "integrity": document_report(document),
        "warnings": [warning.model_dump() for warning in document.warnings],
    }


def _pick_ocr_engine(explicit: str | None):
    """Resolve the OCR engine: explicit name, else the first available one."""
    from engine.ocr.base import OcrEngineUnavailable
    from engine.ocr.engines import available_engines, get_engine

    if explicit:
        return get_engine(explicit)
    available = available_engines()
    if not available:
        raise OcrEngineUnavailable(
            "no OCR engine is installed; install \".[ocr-paddle]\" (preferred) or "
            "\".[ocr-tesseract]\" plus the tesseract binary and language data"
        )
    return get_engine(available[0])


def run_conversion(
    storage: DocumentStore,
    jobs: JobStore,
    job_id: str,
    document_id: str,
    *,
    ocr: bool = False,
    ocr_engine_name: str | None = None,
) -> None:
    """Execute the full pipeline, updating the job at every stage."""
    jobs.update(job_id, status="processing", stage="analyzing", progress=5)
    try:
        source = storage.source_path(document_id)

        profile = analyze(source)
        storage.write_profile(document_id, profile)
        jobs.update(job_id, stage="extracting", progress=25)
        raw = extract(source)

        ocr_report = None
        if ocr:
            jobs.update(job_id, stage="ocr", progress=35)
            engine = _pick_ocr_engine(ocr_engine_name)
            raw, ocr_report = apply_ocr(source, profile, raw, engine)

        jobs.update(job_id, stage="layout", progress=50)
        raw, layout_report = detect_layout(raw)
        jobs.update(job_id, stage="reading_order", progress=60)
        raw, order_report = reconstruct_reading_order(raw, profile, layout_report)
        jobs.update(job_id, stage="arabic_analysis", progress=70)
        raw = detect_scripts(raw)
        jobs.update(job_id, stage="reconstruction", progress=80)
        document = reconstruct_semantics(profile, raw, layout_report, order_report)

        if ocr_report is not None:
            for code, message, page in ocr_report.warnings:
                document.warnings.append(
                    ReflowWarning(
                        code=code,
                        severity="info" if code == "OCR_USED" else "warning",
                        message=message,
                        source_page=page,
                    )
                )

        jobs.update(job_id, stage="review_ready", progress=85)
        storage.write_reflow(document_id, document)
        report = build_report(profile, document)
        report["generated_at"] = None
        storage.write_report(document_id, report)

        jobs.update(job_id, stage="rendering", progress=92)
        data = render_epub(document)
        jobs.update(job_id, stage="validating", progress=97)
        assert_valid(data)
        storage.write_epub(document_id, data)

        jobs.update(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            warnings=[warning.model_dump() for warning in document.warnings],
        )
    except Exception as exc:  # noqa: BLE001 - job boundary records everything
        traceback.print_exc(limit=4)
        jobs.update(
            job_id,
            status="failed",
            stage="failed",
            error=f"{type(exc).__name__}: {exc}",
        )
