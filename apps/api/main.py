"""FastAPI service (apps/api, Milestone 7).

The API layer owns job lifecycle and HTTP contracts only. Document parsing
rules live in the engine (ARCHITECTURE.md 3.2). Security posture per PRD
section 12: MIME/magic validation, filename sanitization, encrypted-PDF
rejection, size limits, and no logging of document contents.
"""

from __future__ import annotations

import os
import subprocess
import threading
from functools import wraps
from pathlib import Path
from typing import Literal

import pymupdf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from apps.api.jobs import ConversionInProgress, JobStore
from apps.api.services import run_conversion
from apps.api.storage import DocumentStore

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
PDF_MAGIC = b"%PDF-"


class ConvertRequest(BaseModel):
    ocr: bool = Field(
        default=False,
        description="Run the OCR stage for scanned pages (requires an OCR extra)",
    )
    engine: Literal["paddle", "tesseract"] | None = Field(
        default=None,
        description="OCR engine name (paddle | tesseract); default: first available",
    )
    mode: Literal["native", "auto", "force"] | None = None
    languages: list[Literal["ar", "id", "en"]] = Field(default_factory=lambda: ["ar", "id", "en"], min_length=1, max_length=3)


class BlockUpdate(BaseModel):
    """User block edit (PRD section 10). Edits are marked modified_by_user."""

    text: str | None = Field(default=None, min_length=1)
    lang: str | None = Field(
        default=None, pattern=r"^(?:[a-z]{2,3}(?:-[A-Za-z0-9]+)*|unknown)$"
    )
    dir: str | None = Field(default=None, pattern=r"^(ltr|rtl)$")
    type: Literal["paragraph", "heading", "quote"] | None = None
    level: int | None = Field(default=None, ge=1, le=6)
    alt: str | None = Field(default=None, max_length=2000)


class BlockMove(BaseModel):
    direction: Literal["up", "down"]


class RepairRequest(BaseModel):
    block_ids: list[str] = Field(min_length=1, max_length=5000)


class RenderImageRequest(BaseModel):
    block_ids: list[str] = Field(min_length=1, max_length=500)


class MetadataUpdate(BaseModel):
    """Book metadata edit (PRD 7 Should-Have: metadata editor)."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    author: list[str] | None = Field(default=None, max_length=10)

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value):
        if value is not None and not value.strip():
            raise ValueError("title cannot be blank")
        return value


COVER_RESOURCE_ID = "cover"


def create_app(storage_dir: Path | None = None) -> FastAPI:
    storage = DocumentStore(
        storage_dir
        or Path(os.environ.get("REFLOW_STORAGE_DIR", "/tmp/reflow"))
    )
    jobs = JobStore(storage)

    app = FastAPI(
        title="Reflow API",
        version="0.8.0",
        description="Mixed Arabic-Latin PDF to reflowable EPUB 3 conversion.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in os.environ.get(
            "REFLOW_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://[::1]:3000"
        ).split(",") if origin.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    app.state.storage = storage
    app.state.jobs = jobs

    def editable(function):
        """Serialize edits and reject them during a running conversion."""
        @wraps(function)
        def guarded(document_id: str, *args, **kwargs):
            _require_document(document_id)
            with storage.lock(document_id):
                job = jobs.get_for_document(document_id)
                if job and job.status in ("queued", "processing"):
                    raise HTTPException(409, "conversion in progress; wait before editing or exporting")
                return function(document_id, *args, **kwargs)
        return guarded

    # ---- health ----------------------------------------------------------------

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/capabilities")
    def get_capabilities() -> dict:
        from engine.ocr.runtime import ocr_capabilities
        from engine.validation.epubcheck import epubcheck_available

        return {"ocr": ocr_capabilities(), "max_upload_bytes": MAX_UPLOAD_BYTES, "validation": {"internal": True, "epubcheck": epubcheck_available()}}

    # ---- documents (M7-01, M7-02) ------------------------------------------------

    @app.post("/api/v1/documents", status_code=201)
    async def upload_document(file: UploadFile = File(...)) -> dict:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
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
        with storage.lock(document_id):
            try:
                job = jobs.create(document_id)
            except ConversionInProgress:
                raise HTTPException(409, "a conversion is already running for this document")
        worker = threading.Thread(
            target=run_conversion,
            kwargs={
                "storage": storage,
                "jobs": jobs,
                "job_id": job.id,
                "document_id": document_id,
                "ocr": request.ocr,
                "ocr_engine_name": request.engine,
                "ocr_mode": request.mode,
                "ocr_languages": request.languages,
            },
            daemon=True,
            name=f"convert-{document_id}",
        )
        try:
            worker.start()
        except RuntimeError:
            jobs.update(job.id, status="failed", stage="failed", error="Could not start conversion worker")
            raise HTTPException(503, "could not start conversion; please retry")
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
        reflow = storage.read_reflow(document_id)
        profile = storage.read_profile(document_id)
        if reflow is None or profile is None:
            raise HTTPException(
                status_code=404, detail="document has not been converted yet"
            )
        from apps.api.services import build_report
        from engine.analyzer.models import DocumentProfile
        from engine.reflowdoc.models import ReflowDocument

        report = build_report(DocumentProfile.model_validate(profile), ReflowDocument.model_validate(reflow))
        report["review"] = {"restorable_block_ids": list(storage.read_originals(document_id))}
        saved = storage.read_report(document_id) or {}
        if "ocr" in saved:
            report["ocr"] = saved["ocr"]
        return report

    # ---- book metadata and cover (PRD 7 Should-Have) ------------------------------

    @app.patch("/api/v1/documents/{document_id}/metadata")
    @editable
    def update_metadata(document_id: str, update: MetadataUpdate) -> dict:
        """Edit book title/author (Should-Have: metadata editor)."""
        _require_document(document_id)
        reflow = storage.read_reflow(document_id)
        if reflow is None:
            raise HTTPException(
                status_code=404, detail="document has not been converted yet"
            )
        from engine.reflowdoc.models import ReflowDocument

        document = ReflowDocument.model_validate(reflow)
        if update.title is not None:
            document.metadata.title = update.title.strip()
        if update.author is not None:
            document.metadata.author = [a.strip() for a in update.author if a.strip()]
        storage.write_reflow(document_id, document)
        return {
            "title": document.metadata.title,
            "author": document.metadata.author,
            "cover_resource_id": document.metadata.cover_resource_id,
        }

    @app.post("/api/v1/documents/{document_id}/cover")
    @editable
    def set_cover(document_id: str, page: int) -> dict:
        """Choose a source page as the EPUB cover (Should-Have: cover selection)."""
        _require_document(document_id)
        reflow = storage.read_reflow(document_id)
        if reflow is None:
            raise HTTPException(
                status_code=404, detail="document has not been converted yet"
            )
        if page < 1:
            raise HTTPException(status_code=422, detail="page number starts at 1")
        from engine.ocr.base import render_page_png
        from engine.reflowdoc.models import ReflowDocument, Resource

        source = storage.source_path(document_id)
        try:
            pdf = pymupdf.open(source)
        except Exception:
            raise HTTPException(status_code=415, detail="unreadable PDF")
        try:
            if page > pdf.page_count:
                raise HTTPException(status_code=404, detail="page out of range")
            png = render_page_png(pdf.load_page(page - 1), dpi=150)
        finally:
            pdf.close()

        document = ReflowDocument.model_validate(reflow)
        document.resources = [
            r for r in document.resources if r.id != COVER_RESOURCE_ID
        ]
        document.resources.append(
            Resource(
                id=COVER_RESOURCE_ID,
                kind="image",
                media_type="image/png",
                filename="cover.png",
                source_page=page,
                content=png,
            )
        )
        document.metadata.cover_resource_id = COVER_RESOURCE_ID
        storage.write_reflow(document_id, document)
        return {"cover_resource_id": COVER_RESOURCE_ID, "source_page": page}

    @app.delete("/api/v1/documents/{document_id}/cover")
    @editable
    def clear_cover(document_id: str) -> dict:
        _require_document(document_id)
        reflow = storage.read_reflow(document_id)
        if reflow is None:
            raise HTTPException(
                status_code=404, detail="document has not been converted yet"
            )
        from engine.reflowdoc.models import ReflowDocument

        document = ReflowDocument.model_validate(reflow)
        document.resources = [
            r for r in document.resources if r.id != COVER_RESOURCE_ID
        ]
        document.metadata.cover_resource_id = None
        storage.write_reflow(document_id, document)
        return {"cover_resource_id": None}

    @app.post("/api/v1/documents/{document_id}/export/epub")
    @editable
    def export_epub(document_id: str, validation: Literal["internal", "w3c"] = "internal") -> FileResponse:
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

        from engine.validation.reflow import quality_report

        document = ReflowDocument.model_validate(reflow)
        if not quality_report(document)["can_export"]:
            raise HTTPException(422, "document references are incomplete; inspect the quality report before exporting")
        data = render_epub(document)
        assert_valid(data)
        if validation == "w3c":
            from engine.validation.epubcheck import epubcheck_available, run_epubcheck

            if not epubcheck_available():
                raise HTTPException(503, "EPUBCheck W3C is not ready; install Java and configure EPUBCHECK_JAR")
            try:
                checked = run_epubcheck(data)
            except (OSError, RuntimeError, subprocess.SubprocessError):
                raise HTTPException(503, "EPUBCheck could not finish; check the local validator setup")
            if not checked.passed:
                raise HTTPException(422, "EPUBCheck W3C rejected the package: " + " | ".join(checked.messages[:8]))
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
    @editable
    def update_block(document_id: str, block_id: str, update: BlockUpdate) -> dict:
        _require_document(document_id)
        reflow = storage.read_reflow(document_id)
        if reflow is None:
            raise HTTPException(
                status_code=404, detail="document has not been converted yet"
            )
        from engine.reflowdoc.models import ReflowDocument
        from engine.reflowdoc.editing import update_semantic_block
        from engine.reflowdoc.traversal import block_locations

        document = ReflowDocument.model_validate(reflow)
        block = _find_block(document, block_id)
        if block is None:
            raise HTTPException(status_code=404, detail="block not found")

        values = update.model_dump(exclude_none=True)
        if not values:
            return block.model_dump()
        try:
            changed = update_semantic_block(block, **values)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        if storage.read_original_block(document_id, block_id) is None:
            storage.write_original_block(
                document_id, block_id, {"block": block.model_dump(mode="json")}
            )
        for blocks, index in block_locations(document):
            if blocks[index].id == block_id:
                blocks[index] = changed
                break
        from engine.arabic.report import attach_integrity

        document = attach_integrity(document)
        storage.write_reflow(document_id, document)
        return changed.model_dump()

    @app.post("/api/v1/documents/{document_id}/blocks/{block_id}/move")
    @editable
    def move_document_block(document_id: str, block_id: str, update: BlockMove) -> dict:
        from engine.reflowdoc.editing import move_block
        from engine.reflowdoc.models import ReflowDocument

        reflow = storage.read_reflow(document_id)
        if reflow is None:
            raise HTTPException(404, "document has not been converted yet")
        document = ReflowDocument.model_validate(reflow)
        try:
            block = move_block(document, block_id, update.direction)
        except KeyError:
            raise HTTPException(404, "block not found")
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        storage.write_reflow(document_id, document)
        return block.model_dump()

    @app.post("/api/v1/documents/{document_id}/blocks/{block_id}/render-image")
    @editable
    def render_block_image(document_id: str, block_id: str, update: RenderImageRequest | None = None) -> dict:
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
                storage, document_id, block_id,
                block_ids=update.block_ids if update else None,
            )
        except block_actions.BlockNotFound:
            raise HTTPException(status_code=404, detail="block not found")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return image_block.model_dump()

    @app.post("/api/v1/documents/{document_id}/blocks/{block_id}/restore-text")
    @editable
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
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return restored.model_dump()

    @app.post("/api/v1/documents/{document_id}/blocks/{block_id}/normalize-arabic")
    @editable
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

    @app.post("/api/v1/documents/{document_id}/blocks/{block_id}/repair-text")
    @editable
    def repair_block_text(document_id: str, block_id: str) -> dict:
        from apps.api import blocks as block_actions

        if storage.read_reflow(document_id) is None:
            raise HTTPException(404, "document has not been converted yet")
        try:
            return block_actions.repair_blocks(storage, document_id, [block_id])
        except block_actions.BlockNotFound:
            raise HTTPException(404, "block not found")

    @app.post("/api/v1/documents/{document_id}/repair-text")
    @editable
    def repair_problem_blocks(document_id: str, request: RepairRequest) -> dict:
        from apps.api import blocks as block_actions

        if storage.read_reflow(document_id) is None:
            raise HTTPException(404, "document has not been converted yet")
        try:
            return block_actions.repair_blocks(storage, document_id, request.block_ids, skip_edited=True)
        except block_actions.BlockNotFound:
            raise HTTPException(404, "block not found")

    # ---- helpers -------------------------------------------------------------------------

    def _require_document(document_id: str) -> None:
        if not storage.exists(document_id):
            raise HTTPException(status_code=404, detail="document not found")

    def _find_block(document, block_id: str):
        from apps.api.blocks import find_block

        return find_block(document, block_id)

    return app


app = create_app()
