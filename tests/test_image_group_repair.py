"""A fragmented quotation must render once and restore all its original blocks."""
import pymupdf
import pytest
from fastapi.testclient import TestClient

from apps.api.blocks import BlockNotFound, render_block_as_image, restore_block_text
from apps.api.main import create_app
from apps.api.storage import DocumentStore
from engine.ocr.base import render_region_png
from engine.reflowdoc.models import ReflowDocument


def setup_group(tmp_path):
    storage = DocumentStore(tmp_path)
    pdf = pymupdf.open()
    page = pdf.new_page(width=400, height=400)
    page.insert_text((50, 80), "Source quotation")
    pdf.new_page(width=400, height=400)
    meta = storage.create_document("source.pdf", pdf.tobytes())
    pdf.close()
    document = ReflowDocument.model_validate({"chapters": [{"id": "c", "blocks": [
        {"id": "a", "type": "quote", "text": "bad a", "source": {"page": 1, "bbox": [40, 60, 100, 90]}},
        {"id": "b", "type": "quote", "text": "bad b", "source": {"page": 1, "bbox": [100, 60, 200, 90]}},
        {"id": "other", "type": "quote", "text": "untouched", "source": {"page": 2, "bbox": [40, 60, 100, 90]}},
    ]}]})
    storage.write_reflow(meta["id"], document)
    return storage, meta["id"], document


def test_group_uses_one_source_crop_and_restores_earliest_fragments(tmp_path):
    storage, doc_id, before = setup_group(tmp_path)
    earliest = before.chapters[0].blocks[1].model_dump(mode="json")
    earliest["text"] = "earliest b"
    storage.write_original_block(doc_id, "b", {"block": earliest})
    image = render_block_as_image(storage, doc_id, "a", block_ids=["a", "b"])
    after = ReflowDocument.model_validate(storage.read_reflow(doc_id))
    assert [b.id for b in after.chapters[0].blocks] == ["a", "other"]
    assert image.source.bbox == [40, 60, 200, 90]
    with pymupdf.open(storage.source_path(doc_id)) as source:
        assert after.resources[0].content == render_region_png(source[0], image.source.bbox)
    assert storage.read_original_block(doc_id, "b") is None
    restore_block_text(storage, doc_id, "a")
    restored = ReflowDocument.model_validate(storage.read_reflow(doc_id))
    assert [b.id for b in restored.chapters[0].blocks] == ["a", "b", "other"]
    assert restored.chapters[0].blocks[1].text == "earliest b"
    assert restored.chapters[0].blocks[2] == before.chapters[0].blocks[2]
    assert not restored.resources and not storage.read_originals(doc_id)


@pytest.mark.parametrize("group", [False, True])
def test_heading_image_retains_navigation_semantics_and_restores_text(tmp_path, group):
    from engine.reflowdoc.models import HeadingBlock

    storage, doc_id, document = setup_group(tmp_path)
    for index in range(2):
        old = document.chapters[0].blocks[index]
        document.chapters[0].blocks[index] = HeadingBlock(
            id=old.id, source=old.source, level=2, text=f"Title {index + 1}",
        )
    storage.write_reflow(doc_id, document)
    image = render_block_as_image(storage, doc_id, "a", block_ids=["a", "b"] if group else None)
    assert image.heading_level == 2
    assert image.alt == ("Title 1 Title 2" if group else "Title 1")
    restore_block_text(storage, doc_id, "a")
    restored = ReflowDocument.model_validate(storage.read_reflow(doc_id))
    assert [b.text for b in restored.chapters[0].blocks] == ["Title 1", "Title 2", "untouched"]


@pytest.mark.parametrize("ids,error", [
    (["b", "a"], ValueError), (["a", "other"], ValueError),
    (["a", "b", "other"], ValueError), (["a", "missing"], BlockNotFound),
])
def test_invalid_group_does_not_mutate_document_or_backups(tmp_path, ids, error):
    storage, doc_id, before = setup_group(tmp_path)
    with pytest.raises(error):
        render_block_as_image(storage, doc_id, "a", block_ids=ids)
    assert storage.read_reflow(doc_id) == before.model_dump(mode="json")
    assert not storage.read_originals(doc_id)


def test_group_restore_rejects_an_id_collision_before_mutating(tmp_path):
    storage, doc_id, before = setup_group(tmp_path)
    render_block_as_image(storage, doc_id, "a", block_ids=["a", "b"])
    document = ReflowDocument.model_validate(storage.read_reflow(doc_id))
    document.chapters[0].blocks.append(before.chapters[0].blocks[1])
    storage.write_reflow(doc_id, document)
    with pytest.raises(ValueError, match="already in use"):
        restore_block_text(storage, doc_id, "a")
    assert storage.read_reflow(doc_id) == document.model_dump(mode="json")
    assert storage.read_original_block(doc_id, "a") is not None


def test_api_group_request_and_restore_are_compatible(tmp_path):
    storage, doc_id, before = setup_group(tmp_path)
    app = create_app(tmp_path)
    with TestClient(app) as client:
        path = f"/api/v1/documents/{doc_id}/blocks/a"
        assert client.post(path + "/render-image", json={"block_ids": ["a", "b"]}).status_code == 200
        assert client.post(path + "/restore-text").status_code == 200
        assert [b["id"] for b in storage.read_reflow(doc_id)["chapters"][0]["blocks"]] == ["a", "b", "other"]
