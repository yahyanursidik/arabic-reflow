"""FastAPI service (apps/api, Milestone 7).

The API layer owns job lifecycle and HTTP contracts only. Document parsing
rules live in the engine (ARCHITECTURE.md 3.2). Security posture per PRD
section 12: MIME/magic validation, filename sanitization, encrypted-PDF
rejection, size limits, and no logging of document contents.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pymupdf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from apps.api.jobs import JobStore
from apps.api.services import run_conversion
from apps.api.storage import DocumentStore

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
PDF_MAGIC = b"%PDF-"


class ConvertRequest(BaseModel):
    ocr: bool = Field(
        default=False,
        description="Run the OCR stage for scanned pages (requires an OCR extra)",
    )
    engine: str | None = Field(
        default=None,
        description="OCR engine name (paddle | tesseract); default: first available",
    )


class BlockUpdate(BaseModel):
    """User block edit (PRD section 10). Edits are marked modified_by_user."""

    text: str | None = Field(default=None, min_length=1)
    lang: str | None = Field(
        default=None, pattern=r"^(?:[a-z]{2,3}(?:-[A-Za-z0-9]+)*|unknown)$"
    )
    dir: str | None = Field(default=None, pattern=r"^(ltr|rtl)$")


def create_app(storage_dir: Path | None = None) -> FastAPI:
    storage = DocumentStore(
        storage_dir
        or Path(__import__("os").environ.get("REFLOW_STORAGE_DIR", "/tmp/reflow"))
    )
    jobs = JobStore(storage)

    app = FastAPI(
        title="Reflow API",
        version="0.5.0",
        description="Mixed Arabic-Latin PDF to reflowable EPUB 3 conversion.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.storage = storage
    app.state.jobs = jobs

    # ---- health ----------------------------------------------------------------

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # ---- documents (M7-01, M7-02) ------------------------------------------------

    @app.post("/api/v1/documents", status_code=201)
    async def upload_document(file: UploadFile = File(...)) -> dict:
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="file exceeds the 100 MB limit")
        if not content.startswith(PDF_MAGIC):
            raise HTTPException(status_code=415, detail="only PDF files are accepted")
        try:
            probe = pymupdf.open(stream=content, filetype="pdf")
        except Exception:
            raise HTTPException(status_code=415, detail="file is not a readable PDF")
        encrypted = probe.needs_pass
        probe.close()
        if encrypted:
            raise HTTPException(
                status_code=400,
                detail="PDF is encrypted; encrypted documents are not accepted",
            )
        meta = storage.create_document(file.filename or "document.pdf", content)
        return meta

    @app.get("/api/v1/documents/{document_id}")
    def get_document(document_id: str) -> dict:
        meta = storage.get_meta(document_id) if storage.exists(document_id) else None
        if meta is None:
            raise HTTPException(status_code=404, detail="document not found")
        return meta

    @app.post("/api/v1/documents/{document_id}/analyze")
    def analyze_document(document_id: str) -> dict:
        _require_document(document_id)
        from engine.analyzer.analyzer import analyze

        profile = analyze(storage.source_path(document_id))
        storage.write_profile(document_id, profile)
        return profile.model_dump()

    @app.get("/api/v1/documents/{document_id}/profile")
    def get_profile(document_id: str) -> dict:
        _require_document(document_id)
        profile = storage.read_profile(document_id)
        if profile is None:
            raise HTTPException(
                status_code=404, detail="document has not been analyzed yet"
            )
        return profile

    @app.get("/api/v1/documents/{document_id}/job")
    def get_document_job(document_id: str) -> dict:
        _require_document(document_id)
        job = jobs.get_for_document(document_id)
        if job is None:
            raise HTTPException(status_code=404, detail="no conversion job yet")
        return job.model_dump()

    @app.get("/api/v1/documents/{document_id}/source/pages/{page_number}.png")
    def get_source_page(document_id: str, page_number: int) -> FileResponse:
        """Page raster for the source-vs-output review pane (M8)."""
        _require_document(document_id)
        if page_number < 1:
            raise HTTPException(status_code=422, detail="page number starts at 1")
        from engine.ocr.base import render_page_png

        source = storage.source_path(document_id)
        try:
            doc = pymupdf.open(source)
        except Exception:
            raise HTTPException(status_code=415, detail="unreadable PDF")
        try:
            if page_number > doc.page_count:
                raise HTTPException(status_code=404, detail="page out of range")
            png = render_page_png(doc.load_page(page_number - 1), dpi=110)
        finally:
            doc.close()
        target = storage.doc_dir(document_id) / f"page-{page_number}.png"
        target.write_bytes(png)
        return FileResponse(target, media_type="image/png")

    # ---- conversion (M7-03, M7-04) -------------------------------------------------

    @app.post("/api/v1/documents/{document_id}/convert", status_code=202)
    def convert_document(document_id: str, request: ConvertRequest) -> dict:
        _require_document(document_id)
        job = jobs.create(document_id)
        worker = threading.Thread(
            target=run_conversion,
            kwargs={
                "storage": storage,
                "jobs": jobs,
                "job_id": job.id,
                "document_id": document_id,
                "ocr": request.ocr,
                "ocr_engine_name": request.engine,
            },
            daemon=True,
            name=f"convert-{document_id}",
        )
        worker.start()
        return {"job_id": job.id, "status": job.status, "stage": job.stage}

    @app.get("/api/v1/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job.model_dump()

    # ---- results (M7-05, M7-07 + report) ---------------------------------------------

    @app.get("/api/v1/documents/{document_id}/reflow")
    def get_reflow(document_id: str) -> dict:
        _require_document(document_id)
        reflow = storage.read_reflow(document_id)
        if reflow is None:
            raise HTTPException(
                status_code=404, detail="document has not been converted yet"
            )
        return reflow

    @app.get("/api/v1/documents/{document_id}/report")
    def get_report(document_id: str) -> dict:
        _require_document(document_id)
        report = storage.read_report(document_id)
        if report is None:
            raise HTTPException(
                status_code=404, detail="document has not been converted yet"
            )
        return report

    @app.post("/api/v1/documents/{document_id}/export/epub")
    def export_epub(document_id: str) -> FileResponse:
        _require_document(document_id)
        reflow = storage.read_reflow(document_id)
        if reflow is None:
            raise HTTPException(
                status_code=404, detail="document has not been converted yet"
            )
        # Always re-render from the current ReflowDoc so user edits are
        # reflected; conversion-time packages are not stale caches.
        from engine.epub.renderer import render_epub
        from engine.reflowdoc.models import ReflowDocument
        from engine.validation.epub import assert_valid

        data = render_epub(ReflowDocument.model_validate(reflow))
        assert_valid(data)
        storage.write_epub(document_id, data)
        path = storage.epub_path(document_id)
        meta = storage.get_meta(document_id) or {}
        filename = Path(meta.get("filename", "document.pdf")).stem + ".epub"
        return FileResponse(
            path,
            media_type="application/epub+zip",
            filename=filename,
        )

    # ---- review (M7-06 + per-block Arabic repair) --------------------------------

    @app.patch("/api/v1/documents/{document_id}/blocks/{block_id}")
    def update_block(document_id: str, block_id: str, update: BlockUpdate) -> dict:
        _require_document(document_id)
        reflow = storage.read_reflow(document_id)
        if reflow is None:
            raise HTTPException(
                status_code=404, detail="document has not been converted yet"
            )
        from engine.reflowdoc.models import (
            Direction,
            HeadingBlock,
            ParagraphBlock,
            QuoteBlock,
            ReflowDocument,
            TextNode,
        )

        document = ReflowDocument.model_validate(reflow)
        block = _find_block(document, block_id)
        if block is None:
            raise HTTPException(status_code=404, detail="block not found")

        if update.text is not None:
            if isinstance(block, ParagraphBlock):
                block.content = [TextNode(text=update.text)]
            elif isinstance(block, (HeadingBlock, QuoteBlock)):
                block.text = update.text
            else:
                raise HTTPException(
                    status_code=422,
                    detail=f"block type {block.type} does not support text edits",
                )
        if update.lang is not None:
            block.lang = update.lang
        if update.dir is not None:
            block.dir = Direction(update.dir)
        block.modified_by_user = True

        storage.write_reflow(document_id, document)
        return block.model_dump()

    @app.post("/api/v1/documents/{document_id}/blocks/{block_id}/render-image")
    def render_block_image(document_id: str, block_id: str) -> dict:
        """Swap an Arabic text block for a pixel-perfect crop of the source
        page (explicit user repair, reversible via restore-text)."""
        _require_document(document_id)
        if storage.read_reflow(document_id) is None:
            raise HTTPException(
                status_code=404, detail="document has not been converted yet"
            )
        from apps.api import blocks as block_actions

        try:
            image_block = block_actions.render_block_as_image(
                storage, document_id, block_id
            )
        except block_actions.BlockNotFound:
            raise HTTPException(status_code=404, detail="block not found")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return image_block.model_dump()

    @app.post("/api/v1/documents/{document_id}/blocks/{block_id}/restore-text")
    def restore_block_text(document_id: str, block_id: str) -> dict:
        _require_document(document_id)
        from apps.api import blocks as block_actions

        try:
            restored = block_actions.restore_block_text(storage, document_id, block_id)
        except block_actions.BlockNotFound:
            raise HTTPException(status_code=404, detail="block not found")
        except block_actions.NoOriginalStored:
            raise HTTPException(
                status_code=404, detail="no pre-render original stored for this block"
            )
        return restored.model_dump()

    @app.post("/api/v1/documents/{document_id}/blocks/{block_id}/normalize-arabic")
    def normalize_block_arabic(document_id: str, block_id: str) -> dict:
        """NFKC-fold presentation forms to core letters; harakat preserved,
        original kept in source_text (explicit user action)."""
        _require_document(document_id)
        from apps.api import blocks as block_actions

        try:
            normalized = block_actions.normalize_block_arabic(
                storage, document_id, block_id
            )
        except block_actions.BlockNotFound:
            raise HTTPException(status_code=404, detail="block not found")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return normalized.model_dump()

    # ---- helpers -------------------------------------------------------------------------

    def _require_document(document_id: str) -> None:
        if not storage.exists(document_id):
            raise HTTPException(status_code=404, detail="document not found")

    def _find_block(document, block_id: str):
        for chapter in document.chapters:
            for block in chapter.blocks:
                if block.id == block_id:
                    return block
                if hasattr(block, "blocks"):
                    for inner in block.blocks:
                        if inner.id == block_id:
                            return inner
        return None

    return app


app = create_app()
