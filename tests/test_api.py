"""API endpoint tests (backlog M7-01..M7-07)."""

from __future__ import annotations

import base64
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


# --- Review support endpoints (M8) -----------------------------------------------------


def test_document_meta_profile_job_and_source_page(client, fixtures_dir) -> None:
    meta = _upload(client, fixtures_dir, "indonesian-native.pdf")
    document_id = meta["id"]

    got = client.get(f"/api/v1/documents/{document_id}")
    assert got.status_code == 200
    assert got.json()["filename"] == "indonesian-native.pdf"

    assert client.get(f"/api/v1/documents/{document_id}/profile").status_code == 404
    assert client.post(f"/api/v1/documents/{document_id}/analyze").status_code == 200
    profile = client.get(f"/api/v1/documents/{document_id}/profile")
    assert profile.status_code == 200
    assert profile.json()["page_count"] == 1

    assert client.get(f"/api/v1/documents/{document_id}/job").status_code == 404
    client.post(f"/api/v1/documents/{document_id}/convert", json={"ocr": False})
    job = client.get(f"/api/v1/documents/{document_id}/job")
    assert job.status_code == 200
    assert job.json()["document_id"] == document_id

    page = client.get(f"/api/v1/documents/{document_id}/source/pages/1.png")
    assert page.status_code == 200
    assert page.headers["content-type"] == "image/png"
    assert page.content[:4] == b"\x89PNG"
    assert client.get(
        f"/api/v1/documents/{document_id}/source/pages/99.png"
    ).status_code == 404
    assert client.get(
        f"/api/v1/documents/{document_id}/source/pages/0.png"
    ).status_code == 422


def test_unknown_document_meta_404(client) -> None:
    assert client.get("/api/v1/documents/nope").status_code == 404


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

    # export always re-renders from the stored ReflowDoc, so repeated calls
    # are both valid EPUBs (byte equality is not expected: zip timestamps differ)
    again = client.post(f"/api/v1/documents/{meta['id']}/export/epub")
    assert again.status_code == 200
    assert again.content[:2] == b"PK"


def test_conversion_persists_documents_with_binary_resources(client, fixtures_dir) -> None:
    """Regression: documents with embedded images must survive JSON storage."""
    import base64

    meta, job = _convert_and_wait(client, fixtures_dir, "image-caption.pdf")
    assert job["status"] == "completed", job
    reflow = client.get(f"/api/v1/documents/{meta['id']}/reflow").json()
    resources = [r for r in reflow.get("resources", []) if r.get("content")]
    assert resources, "image resource persisted as base64"
    raw = base64.b64decode(resources[0]["content"])
    assert raw[:4] == b"\x89PNG"
    export = client.post(f"/api/v1/documents/{meta['id']}/export/epub")
    assert export.status_code == 200
    assert export.content[:2] == b"PK"


# --- Per-block Arabic repair (render-image / restore / normalize) -----------------


def _reflow_block_text(block: dict) -> str:
    if block["type"] == "paragraph":
        return "".join(node["text"] for node in block.get("content", []))
    return block.get("text", "")


def test_render_block_as_image_is_reversible(client, fixtures_dir) -> None:
    meta, job = _convert_and_wait(client, fixtures_dir, "arabic-native.pdf")
    assert job["status"] == "completed", job
    reflow = client.get(f"/api/v1/documents/{meta['id']}/reflow").json()
    paragraph = next(
        b for b in reflow["chapters"][0]["blocks"]
        if b["type"] == "paragraph"
        and any(
            "\u0600" <= ch <= "\u06FF" or "\uFB50" <= ch <= "\uFEFF"
            for ch in _reflow_block_text(b)
        )
    )
    original_text = _reflow_block_text(paragraph)

    rendered = client.post(
        f"/api/v1/documents/{meta['id']}/blocks/{paragraph['id']}/render-image"
    )
    assert rendered.status_code == 200
    block = rendered.json()
    assert block["type"] == "image"
    assert "ARABIC_RENDERED_AS_IMAGE" in block["warnings"]
    assert block["modified_by_user"] is True
    resource = next(
        r for r in client.get(f"/api/v1/documents/{meta['id']}/reflow").json()["resources"]
        if r["id"] == block["resource_id"]
    )
    assert base64.b64decode(resource["content"])[:4] == b"\x89PNG"

    restored = client.post(
        f"/api/v1/documents/{meta['id']}/blocks/{paragraph['id']}/restore-text"
    )
    assert restored.status_code == 200
    back = restored.json()
    assert back["type"] == "paragraph"
    assert _reflow_block_text(back) == original_text
    assert "ARABIC_RENDERED_AS_IMAGE" not in back["warnings"]

    # the render resource is cleaned up and restore is no longer possible
    remaining = [
        r for r in client.get(f"/api/v1/documents/{meta['id']}/reflow").json()["resources"]
        if r["id"] == block["resource_id"]
    ]
    assert remaining == []
    assert client.post(
        f"/api/v1/documents/{meta['id']}/blocks/{paragraph['id']}/restore-text"
    ).status_code == 404


def test_normalize_arabic_folds_presentation_forms_keeps_harakat(
    client, fixtures_dir
) -> None:
    meta, job = _convert_and_wait(client, fixtures_dir, "arabic-native.pdf")
    assert job["status"] == "completed", job
    reflow = client.get(f"/api/v1/documents/{meta['id']}/reflow").json()
    paragraph = next(
        b for b in reflow["chapters"][0]["blocks"]
        if b["type"] == "paragraph"
        and any("\uFB50" <= ch <= "\uFEFF" for ch in _reflow_block_text(b))
    )
    harakat_before = sum(
        1 for ch in _reflow_block_text(paragraph) if "\u064B" <= ch <= "\u065F"
    )

    response = client.post(
        f"/api/v1/documents/{meta['id']}/blocks/{paragraph['id']}/normalize-arabic"
    )
    assert response.status_code == 200
    normalized = response.json()
    assert normalized["modified_by_user"] is True
    text = "".join(node["text"] for node in normalized["content"])
    assert not any("\uFB50" <= ch <= "\uFEFF" for ch in text), (
        "presentation forms must be folded to core letters"
    )
    harakat_after = sum(1 for ch in text if "\u064B" <= ch <= "\u065F")
    assert harakat_after == harakat_before, "harakat must survive normalization"
    provenance = [n for n in normalized["content"] if n.get("source_text")]
    assert provenance, "original text kept in source_text"
    assert any(
        "arabic_nfkc_normalization" in n.get("transformations", [])
        for n in normalized["content"]
    )


def test_normalize_folds_latin_ligatures_too(client, fixtures_dir) -> None:
    """NFKC also repairs Latin extraction artifacts: the 'ﬁ' ligature in
    'ﬁkih' folds to plain 'fi'. The block is marked user-modified."""
    meta, _ = _convert_and_wait(client, fixtures_dir, "indonesian-native.pdf")
    reflow = client.get(f"/api/v1/documents/{meta['id']}/reflow").json()
    paragraph = next(
        b for b in reflow["chapters"][0]["blocks"]
        if b["type"] == "paragraph" and "\ufb01" in _reflow_block_text(b)
    )
    response = client.post(
        f"/api/v1/documents/{meta['id']}/blocks/{paragraph['id']}/normalize-arabic"
    )
    assert response.status_code == 200
    normalized = response.json()
    assert "\ufb01" not in _reflow_block_text(normalized)
    assert "fikih" in _reflow_block_text(normalized)
    assert normalized["modified_by_user"] is True


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
