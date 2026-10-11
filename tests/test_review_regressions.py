"""Regression coverage for the review workflow and storage/job boundaries."""

from pathlib import Path

import pytest

from apps.api.jobs import ConversionInProgress, JobStore
from apps.api.storage import DocumentStore
from engine.arabic.report import attach_integrity
from engine.reflowdoc.editing import edited_content
from engine.reflowdoc.models import ReflowDocument


def test_latest_job_and_duplicate_conversion_guard(tmp_path: Path):
    storage = DocumentStore(tmp_path)
    meta = storage.create_document("book.pdf", b"%PDF-")
    jobs = JobStore(storage)
    first = jobs.create(meta["id"])
    with pytest.raises(ConversionInProgress):
        jobs.create(meta["id"])
    jobs.update(first.id, status="completed", stage="completed", progress=100)
    second = jobs.create(meta["id"])
    assert jobs.get_for_document(meta["id"]).id == second.id
    assert storage.read_job(meta["id"])["id"] == second.id
    second.status = "completed"
    assert jobs.get_for_document(meta["id"]).status == "queued"


def test_interrupted_conversion_is_retryable_after_restart(tmp_path: Path):
    storage = DocumentStore(tmp_path)
    meta = storage.create_document("book.pdf", b"%PDF-")
    first = JobStore(storage).create(meta["id"])
    restarted = JobStore(storage)
    job = restarted.get(first.id)
    assert job.status == "failed"
    assert "restarted" in job.error
    assert restarted.create(meta["id"]).id != first.id


def test_storage_rejects_path_traversal(tmp_path: Path):
    storage = DocumentStore(tmp_path)
    for document_id in ("..", "../outside", "C:\\Windows", "a" * 31):
        assert not storage.exists(document_id)
        with pytest.raises(ValueError):
            storage.source_path(document_id)


@pytest.mark.parametrize("text", [
    "Hadits ini dari أَبِي هُرَيْرَةَ, dalam kitab.",
    "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ", "السلام عليكم", "Teks Indonesia.",
    " العربيةُlatin", "(Latin) عربيّ! Latin; 123.",
])
def test_edited_content_preserves_every_character(text):
    nodes = edited_content(text)
    assert "".join(node.text for node in nodes) == text
    if "Latin" in text or "latin" in text or "Hadits" in text:
        assert any(getattr(node, "dir", None) == "rtl" for node in nodes)


def test_integrity_refresh_is_idempotent_and_clears_fixed_issue():
    document = ReflowDocument.model_validate({"chapters": [{"id": "one", "blocks": [{
        "id": "paragraph", "type": "paragraph",
        "content": [{"type": "text", "text": "ا ل س ل ا م სტ სტ"}],
    }]}]})
    attach_integrity(document)
    attach_integrity(document)
    assert document.chapters[0].blocks[0].warnings.count("LOW_ARABIC_CONFIDENCE") == 1
    assert len([w for w in document.warnings if w.code == "LOW_ARABIC_CONFIDENCE"]) == 1
    document.chapters[0].blocks[0].content = edited_content("Teks sudah diganti pengguna.")
    attach_integrity(document)
    assert document.chapters[0].blocks[0].arabic_integrity is None
    assert "LOW_ARABIC_CONFIDENCE" not in document.chapters[0].blocks[0].warnings
    assert not any(w.code == "LOW_ARABIC_CONFIDENCE" for w in document.warnings)


def test_conversion_failure_does_not_log_source_contents(tmp_path, monkeypatch, caplog):
    from apps.api.services import run_conversion

    storage = DocumentStore(tmp_path)
    meta = storage.create_document("book.pdf", b"%PDF-")
    jobs = JobStore(storage)
    job = jobs.create(meta["id"])

    def fail(*args):
        raise ValueError("sensitive document passage")

    monkeypatch.setattr("apps.api.services.analyze", fail)
    run_conversion(storage, jobs, job.id, meta["id"])
    assert jobs.get(job.id).status == "failed"
    assert job.id in caplog.text
    assert "sensitive document passage" not in caplog.text
