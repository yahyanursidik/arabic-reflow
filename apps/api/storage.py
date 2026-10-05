"""MVP document storage (ARCHITECTURE.md section 8).

Temporary filesystem only, no database:

    {storage}/documents/{document_id}/
        source.pdf      uploaded bytes (validated)
        profile.json    analyzer output
        reflow.json     ReflowDoc after conversion
        report.json     quality report
        output.epub     validated EPUB 3
        job.json        conversion job state

Filenames are sanitized at the boundary; document contents are never logged.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from engine.analyzer.models import DocumentProfile
from engine.reflowdoc.models import ReflowDocument

MAX_FILENAME_LEN = 120
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str | None) -> str:
    """Strip path components and unsafe characters (PRD section 12)."""
    base = Path(name or "document.pdf").name
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "document.pdf"
    return cleaned[:MAX_FILENAME_LEN]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DocumentStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.documents_dir = self.root / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    def doc_dir(self, document_id: str) -> Path:
        return self.documents_dir / document_id

    def _doc_dir(self, document_id: str) -> Path:
        return self.documents_dir / document_id

    def create_document(self, filename: str, content: bytes) -> dict:
        document_id = uuid.uuid4().hex
        doc_dir = self._doc_dir(document_id)
        doc_dir.mkdir(parents=True, exist_ok=False)
        (doc_dir / "source.pdf").write_bytes(content)
        meta = {
            "id": document_id,
            "filename": sanitize_filename(filename),
            "size": len(content),
            "created_at": utc_now(),
        }
        (doc_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), "utf-8"
        )
        return meta

    def exists(self, document_id: str) -> bool:
        return self._doc_dir(document_id).is_dir()

    def get_meta(self, document_id: str) -> dict | None:
        path = self._doc_dir(document_id) / "meta.json"
        if not path.exists():
            return None
        return json.loads(path.read_text("utf-8"))

    def source_path(self, document_id: str) -> Path:
        return self._doc_dir(document_id) / "source.pdf"

    def _write_json(self, document_id: str, name: str, payload) -> None:
        target = self._doc_dir(document_id) / name
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), "utf-8"
        )

    def _read_json(self, document_id: str, name: str):
        path = self._doc_dir(document_id) / name
        if not path.exists():
            return None
        return json.loads(path.read_text("utf-8"))

    def write_profile(self, document_id: str, profile: DocumentProfile) -> None:
        self._write_json(document_id, "profile.json", profile.model_dump())

    def read_profile(self, document_id: str) -> dict | None:
        return self._read_json(document_id, "profile.json")

    def write_reflow(self, document_id: str, document: ReflowDocument) -> None:
        self._write_json(document_id, "reflow.json", document.model_dump())

    def read_reflow(self, document_id: str) -> dict | None:
        return self._read_json(document_id, "reflow.json")

    def write_report(self, document_id: str, report: dict) -> None:
        self._write_json(document_id, "report.json", report)

    def read_report(self, document_id: str) -> dict | None:
        return self._read_json(document_id, "report.json")

    def write_epub(self, document_id: str, data: bytes) -> None:
        (self._doc_dir(document_id) / "output.epub").write_bytes(data)

    def epub_path(self, document_id: str) -> Path | None:
        path = self._doc_dir(document_id) / "output.epub"
        return path if path.exists() else None

    def write_job(self, document_id: str, job: dict) -> None:
        self._write_json(document_id, "job.json", job)

    def read_job(self, document_id: str) -> dict | None:
        return self._read_json(document_id, "job.json")
