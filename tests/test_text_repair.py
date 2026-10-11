"""Repairs must be bounded, idempotent, and reversible across all review actions."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from engine.reflowdoc.models import ReflowDocument
from engine.reflowdoc.repair import repair_block, repair_text
from engine.epub.renderer import render_epub
from engine.validation.epub import assert_valid


@pytest.mark.parametrize("text", [
    "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ", "السلام عليكم", "Hadits dari أَبِي هُرَيْرَةَ, dalam kitab.",
    "(العربيةُ)، ١٢٣; Latin!", "ا ل س ل ا م", "ُعربي", "Teks biasa.",
])
def test_valid_source_text_and_uncertain_arabic_are_not_rewritten(text):
    assert repair_text(text) == (text, [])


def test_letter_forms_repair_keeps_harakat_order_and_xml_provenance():
    block = ReflowDocument.model_validate({"chapters": [{"id": "c", "blocks": [{
        "id": "p", "type": "paragraph", "content": [{"type": "text", "text": "ﻻ\u0651\u064e\x1b"}],
    }]}]}).chapters[0].blocks[0]
    repaired, changed = repair_block(block)
    assert changed and repaired.text == "لا\u0651\u064e"
    assert repaired.content[0].source_text == block.text
    assert repaired.dir == "rtl" and repaired.lang == "ar"
    assert not repair_block(repaired)[1]
    assert block.text == "ﻻ\u0651\u064e\x1b"


def test_mixed_inline_direction_is_repaired_without_text_changes():
    block = ReflowDocument.model_validate({"chapters": [{"id": "c", "blocks": [{
        "id": "p", "type": "paragraph", "lang": "id", "dir": "ltr",
        "content": [{"type": "text", "text": "Hadits dari أَبِي هُرَيْرَةَ, dalam kitab."}],
    }]}]}).chapters[0].blocks[0]
    repaired, changed = repair_block(block)
    assert changed and repaired.text == block.text
    assert any(getattr(node, "dir", None) == "rtl" for node in repaired.content)
    assert not repair_block(repaired)[1]


def setup_document(tmp_path: Path):
    app = create_app(tmp_path)
    storage = app.state.storage
    meta = storage.create_document("repair.pdf", Path("tests/fixtures/mixed-id-ar.pdf").read_bytes())
    document = ReflowDocument.model_validate({"document_id": meta["id"], "chapters": [{"id": "c", "blocks": [
        {"id": "p", "type": "paragraph", "source": {"page": 1, "bbox": [72, 72, 400, 110]},
         "content": [{"type": "text", "text": "ﻻ\u0651\u064e\x1b"}]},
        {"id": "edited", "type": "quote", "text": "ﻻ", "modified_by_user": True},
        {"id": "uncertain", "type": "quote", "lang": "ar", "dir": "rtl", "script": "Arabic", "text": "ا ل س ل ا م"},
        {"id": "nested", "type": "footnote", "marker": "1", "blocks": [
            {"id": "child", "type": "heading", "level": 2, "text": "ﻻ"}]},
    ]}]})
    storage.write_reflow(meta["id"], document)
    return app, TestClient(app), storage, meta["id"], document


def test_batch_skips_edits_and_uncertain_words_and_can_restore_after_image(tmp_path):
    app, client, storage, doc_id, original = setup_document(tmp_path)
    path = f"/api/v1/documents/{doc_id}"
    response = client.post(path + "/repair-text", json={"block_ids": ["p", "edited", "uncertain", "child", "p"]})
    assert response.status_code == 200
    assert response.json()["changed_block_ids"] == ["p", "child"]
    assert response.json()["skipped_block_ids"] == ["edited"]
    assert response.json()["unchanged_block_ids"] == ["uncertain"]
    assert storage.read_original_block(doc_id, "p")["block"] == original.chapters[0].blocks[0].model_dump(mode="json")
    assert client.post(path + "/blocks/p/repair-text").json()["changed_block_ids"] == []
    assert client.post(path + "/blocks/p/render-image").status_code == 200
    restored = client.post(path + "/blocks/p/restore-text")
    assert restored.status_code == 200
    assert restored.json()["content"][0]["text"] == original.chapters[0].blocks[0].text
    assert storage.read_original_block(doc_id, "p") is None
    assert_valid(render_epub(ReflowDocument.model_validate(storage.read_reflow(doc_id))))


def test_batch_unknown_id_is_atomic_and_running_job_blocks_repairs(tmp_path):
    app, client, storage, doc_id, original = setup_document(tmp_path)
    path = f"/api/v1/documents/{doc_id}"
    assert client.post(path + "/repair-text", json={"block_ids": ["p", "missing"]}).status_code == 404
    assert storage.read_reflow(doc_id) == original.model_dump(mode="json")
    assert not storage.read_originals(doc_id)
    app.state.jobs.create(doc_id)
    assert client.post(path + "/blocks/p/repair-text").status_code == 409
    assert client.post(path + "/repair-text", json={"block_ids": ["p"]}).status_code == 409
