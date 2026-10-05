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
        description="Run the OCR stage for scanned pages (requires the paddle extra)",
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

    @app.post("/api/v1/documents/{document_id}/analyze")
    def analyze_document(document_id: str) -> dict:
        _require_document(document_id)
        from engine.analyzer.analyzer import analyze

        profile = analyze(storage.source_path(document_id))
        storage.write_profile(document_id, profile)
        return profile.model_dump()

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

    # ---- review (M7-06) ----------------------------------------------------------------

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
