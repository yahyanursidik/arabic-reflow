"""API endpoint tests (backlog M7-01..M7-07)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


def _upload(client: TestClient, fixtures_dir: Path, name: str) -> dict:
    response = client.post(
        "/api/v1/documents",
        files={"file": (name, (fixtures_dir / name).read_bytes(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _wait_for_job(client: TestClient, job_id: str, timeout: float = 60.0) -> dict:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish in time")


# --- Upload (M7-01) ------------------------------------------------------------------


def test_upload_accepts_valid_pdf(client, fixtures_dir) -> None:
    meta = _upload(client, fixtures_dir, "mixed-id-ar.pdf")
    assert meta["filename"] == "mixed-id-ar.pdf"
    assert meta["size"] > 0
    assert len(meta["id"]) == 32


def test_upload_rejects_non_pdf(client) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 415


def test_upload_rejects_fake_pdf_extension(client) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("evil.pdf", b"MZ fake executable", "application/pdf")},
    )
    assert response.status_code == 415


def test_upload_rejects_encrypted_pdf(tmp_path, client) -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "rahasia")
    target = tmp_path / "enc.pdf"
    doc.save(target, encryption=pymupdf.PDF_ENCRYPT_AES_256,
             owner_pw="o", user_pw="u")
    doc.close()
    response = client.post(
        "/api/v1/documents",
        files={"file": ("enc.pdf", target.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 400
    assert "encrypted" in response.json()["detail"].lower()


def test_upload_sanitizes_filename(client, fixtures_dir) -> None:
    payload = (fixtures_dir / "mixed-id-ar.pdf").read_bytes()
    response = client.post(
        "/api/v1/documents",
        files={"file": ("../../we ird/name?.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 201
    assert "/" not in response.json()["filename"]
    assert "\\" not in response.json()["filename"]
    assert ".." not in response.json()["filename"]


# --- Analyze (M7-02) ------------------------------------------------------------------


def test_analyze_returns_profile(client, fixtures_dir) -> None:
    meta = _upload(client, fixtures_dir, "mixed-id-ar.pdf")
    response = client.post(f"/api/v1/documents/{meta['id']}/analyze")
    assert response.status_code == 200
    profile = response.json()
    assert profile["page_count"] == 1
    assert profile["classification"] == "native"
    assert profile["arabic_detected"] is True


def test_analyze_unknown_document_404(client) -> None:
    assert client.post("/api/v1/documents/doesnotexist/analyze").status_code == 404


# --- Conversion lifecycle (M7-03, M7-04, M7-05, M7-07) ---------------------------------


def _convert_and_wait(client, fixtures_dir, name="mixed-id-ar.pdf") -> tuple[dict, dict]:
    meta = _upload(client, fixtures_dir, name)
    response = client.post(f"/api/v1/documents/{meta['id']}/convert", json={"ocr": False})
    assert response.status_code == 202
    job = _wait_for_job(client, response.json()["job_id"])
    return meta, job


def test_conversion_completes_with_stages(client, fixtures_dir) -> None:
    meta, job = _convert_and_wait(client, fixtures_dir)
    assert job["status"] == "completed", job
    assert job["stage"] == "completed"
    assert job["progress"] == 100


def test_reflow_endpoint_returns_document(client, fixtures_dir) -> None:
    meta, _ = _convert_and_wait(client, fixtures_dir)
    response = client.get(f"/api/v1/documents/{meta['id']}/reflow")
    assert response.status_code == 200
    reflow = response.json()
    assert reflow["schema_version"] == "0.1"
    chapter = reflow["chapters"][0]
    texts = [
        "".join(node["text"] for node in b.get("content", []))
        if b["type"] == "paragraph" else b.get("text", "")
        for b in chapter["blocks"]
    ]
    assert any("Hadits ini diriwayatkan dari" in t for t in texts)


def test_reflow_before_conversion_404(client, fixtures_dir) -> None:
    meta = _upload(client, fixtures_dir, "mixed-id-ar.pdf")
    response = client.get(f"/api/v1/documents/{meta['id']}/reflow")
    assert response.status_code == 404


def test_report_endpoint(client, fixtures_dir) -> None:
    meta, _ = _convert_and_wait(client, fixtures_dir)
    response = client.get(f"/api/v1/documents/{meta['id']}/report")
    assert response.status_code == 200
    report = response.json()
    assert report["profile"]["page_count"] == 1
    assert "integrity" in report and "warnings" in report


def test_export_epub_returns_valid_package(client, fixtures_dir) -> None:
    meta, _ = _convert_and_wait(client, fixtures_dir, "arabic-native.pdf")
    response = client.post(f"/api/v1/documents/{meta['id']}/export/epub")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/epub+zip"
    data = response.content
    assert data[:2] == b"PK"
    archive = zipfile.ZipFile(io.BytesIO(data))
    assert archive.namelist()[0] == "mimetype"

    # second export serves the stored package
    again = client.post(f"/api/v1/documents/{meta['id']}/export/epub")
    assert again.content == data


def test_scanned_document_converts_to_empty_document(client, fixtures_dir) -> None:
    meta, job = _convert_and_wait(client, fixtures_dir, "scanned.pdf")
    assert job["status"] == "completed"
    reflow = client.get(f"/api/v1/documents/{meta['id']}/reflow").json()
    assert reflow["chapters"][0]["blocks"] == []


# --- Block editing (M7-06) ---------------------------------------------------------------


def test_block_edit_marks_user_modification(client, fixtures_dir) -> None:
    meta, _ = _convert_and_wait(client, fixtures_dir)
    reflow = client.get(f"/api/v1/documents/{meta['id']}/reflow").json()
    block = next(
        b for b in reflow["chapters"][0]["blocks"] if b["type"] == "paragraph"
    )
    response = client.patch(
        f"/api/v1/documents/{meta['id']}/blocks/{block['id']}",
        json={"text": "Teks yang disunting pembaca."},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["modified_by_user"] is True
    content_texts = [node["text"] for node in updated["content"]]
    assert "Teks yang disunted pembaca." not in content_texts
    assert "Teks yang disunting pembaca." in content_texts

    persisted = client.get(f"/api/v1/documents/{meta['id']}/reflow").json()
    persisted_block = next(
        b for b in persisted["chapters"][0]["blocks"] if b["id"] == block["id"]
    )
    assert persisted_block["modified_by_user"] is True


def test_block_edit_language_and_direction(client, fixtures_dir) -> None:
    meta, _ = _convert_and_wait(client, fixtures_dir)
    reflow = client.get(f"/api/v1/documents/{meta['id']}/reflow").json()
    block = next(
        b for b in reflow["chapters"][0]["blocks"] if b["type"] == "paragraph"
    )
    response = client.patch(
        f"/api/v1/documents/{meta['id']}/blocks/{block['id']}",
        json={"lang": "ar", "dir": "rtl"},
    )
    assert response.status_code == 200
    assert response.json()["lang"] == "ar"
    assert response.json()["dir"] == "rtl"


def test_block_edit_rejects_invalid_direction(client, fixtures_dir) -> None:
    meta, _ = _convert_and_wait(client, fixtures_dir)
    reflow = client.get(f"/api/v1/documents/{meta['id']}/reflow").json()
    block = reflow["chapters"][0]["blocks"][0]
    response = client.patch(
        f"/api/v1/documents/{meta['id']}/blocks/{block['id']}",
        json={"dir": "diagonal"},
    )
    assert response.status_code == 422


def test_block_edit_unknown_block_404(client, fixtures_dir) -> None:
    meta, _ = _convert_and_wait(client, fixtures_dir)
    response = client.patch(
        f"/api/v1/documents/{meta['id']}/blocks/block-999",
        json={"text": "x"},
    )
    assert response.status_code == 404


def test_export_epub_preserves_user_edit(client, fixtures_dir) -> None:
    meta, _ = _convert_and_wait(client, fixtures_dir)
    reflow = client.get(f"/api/v1/documents/{meta['id']}/reflow").json()
    block = next(
        b for b in reflow["chapters"][0]["blocks"] if b["type"] == "paragraph"
    )
    client.patch(
        f"/api/v1/documents/{meta['id']}/blocks/{block['id']}",
        json={"text": "Suntingan pembaca."},
    )
    response = client.post(f"/api/v1/documents/{meta['id']}/export/epub")
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    xhtml = next(n for n in archive.namelist() if n.endswith(".xhtml") and "chapter" in n)
    assert "Suntingan pembaca." in archive.read(xhtml).decode("utf-8")
