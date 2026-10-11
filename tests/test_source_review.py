from engine.reflowdoc.models import ReflowDocument
from engine.reflowdoc.editing import update_semantic_block
from engine.validation.reflow import quality_report
from tests.test_image_group_repair import setup_group
from apps.api.blocks import restore_block_text
import os
import pytest


def reviewed(text="Source text", **kwargs):
    return ReflowDocument.model_validate({"chapters": [{"id": "c", "blocks": [
        {"id": "a", "type": "quote", "text": text, "confidence": 0.4,
         "warnings": ["SOURCE_VERIFIED"], **kwargs},
    ]}]})


def test_source_review_keeps_extraction_confidence_and_edit_invalidates_it():
    document = reviewed()
    assert not quality_report(document)["review_block_ids"]
    assert document.chapters[0].blocks[0].confidence == 0.4
    document.chapters[0].blocks[0] = update_semantic_block(document.chapters[0].blocks[0], text="Changed")
    assert quality_report(document)["review_block_ids"] == ["a"]


def test_source_review_does_not_hide_xml_or_arabic_diagnostics():
    assert quality_report(reviewed("bad\x1b"))["review_block_ids"] == ["a"]
    assert quality_report(reviewed(arabic_integrity={"score": 0.3}))["review_block_ids"] == ["a"]
    assert quality_report(reviewed(warnings=["SOURCE_VERIFIED", "PARAGRAPH_MERGE_UNCERTAIN"]))["review_block_ids"] == ["a"]


def test_restore_container_allows_its_own_child_ids(tmp_path):
    storage, doc_id, document = setup_group(tmp_path)
    original = {"id": "a", "type": "footnote", "marker": "1", "blocks": [
        {"id": "child", "type": "quote", "text": "Original"},
    ]}
    current = {**original, "blocks": [{"id": "child", "type": "quote", "text": "Reviewed"}]}
    document.chapters[0].blocks[0] = ReflowDocument.model_validate({"chapters": [{"id": "x", "blocks": [current]}]}).chapters[0].blocks[0]
    storage.write_reflow(doc_id, document)
    storage.write_original_block(doc_id, "a", {"block": original})
    restore_block_text(storage, doc_id, "a")
    assert storage.read_reflow(doc_id)["chapters"][0]["blocks"][0]["blocks"][0]["text"] == "Original"


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing violations")
def test_atomic_write_retries_transient_windows_reader_lock(tmp_path, monkeypatch):
    storage, doc_id, document = setup_group(tmp_path)
    real_replace = os.replace
    calls = []
    monkeypatch.setattr("apps.api.storage.time.sleep", lambda _: None)
    document.metadata.title = "Saved"
    # The old document remains readable until the final successful swap.
    old = document.model_copy(deep=True)
    old.metadata.title = ""
    def transient(source, target):
        calls.append(target)
        if len(calls) < 3:
            assert storage.read_reflow(doc_id) == old.model_dump(mode="json")
            raise PermissionError("file temporarily held by reader")
        return real_replace(source, target)
    monkeypatch.setattr("apps.api.storage.os.replace", transient)
    storage.write_reflow(doc_id, document)
    assert len(calls) == 3
    assert storage.read_reflow(doc_id)["metadata"]["title"] == "Saved"
