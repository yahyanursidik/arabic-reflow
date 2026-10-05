"""Conversion job lifecycle (ARCHITECTURE.md section 6).

Jobs run in background threads; state lives in memory with write-through to
the document directory so a restart can show the last known state.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from apps.api.storage import DocumentStore, utc_now

STAGES = (
    "uploaded", "analyzing", "extracting", "ocr", "layout", "reading_order",
    "arabic_analysis", "reconstruction", "review_ready", "rendering",
    "validating", "completed", "failed",
)


class JobState(BaseModel):
    id: str
    document_id: str
    status: str = "queued"  # queued | processing | completed | failed
    stage: str = "uploaded"
    progress: int = Field(default=0, ge=0, le=100)
    warnings: list[dict] = Field(default_factory=list)
    error: str | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class JobStore:
    """In-memory registry with write-through persistence per document."""

    def __init__(self, storage: DocumentStore) -> None:
        self._storage = storage
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()

    def create(self, document_id: str) -> JobState:
        import uuid

        job = JobState(id=uuid.uuid4().hex, document_id=document_id)
        with self._lock:
            self._jobs[job.id] = job
        self._persist(job)
        return job

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is not None:
            return job
        # Disk fallback (e.g. after a restart): the document's last job.
        for meta_dir in (self._storage.documents_dir).iterdir():
            persisted = self._storage.read_job(meta_dir.name)
            if persisted and persisted.get("id") == job_id:
                restored = JobState.model_validate(persisted)
                with self._lock:
                    self._jobs[job_id] = restored
                return restored
        return None

    def get_for_document(self, document_id: str) -> JobState | None:
        with self._lock:
            for job in self._jobs.values():
                if job.document_id == document_id:
                    return job
        persisted = self._storage.read_job(document_id)
        if persisted:
            restored = JobState.model_validate(persisted)
            with self._lock:
                self._jobs[restored.id] = restored
            return restored
        return None

    def update(
        self, job_id: str, *, status: str | None = None, stage: str | None = None,
        progress: int | None = None, warnings: list[dict] | None = None,
        error: str | None = None,
    ) -> JobState | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if status is not None:
                job.status = status
            if stage is not None:
                job.stage = stage
            if progress is not None:
                job.progress = max(job.progress, progress)
            if warnings is not None:
                job.warnings = warnings
            if error is not None:
                job.error = error
            job.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            snapshot = job.model_copy()
        self._persist(snapshot)
        return snapshot

    def _persist(self, job: JobState) -> None:
        self._storage.write_job(job.document_id, job.model_dump())
