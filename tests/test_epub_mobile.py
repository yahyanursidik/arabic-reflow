"""Source-pixel preservation and explicit, reversible footnote navigation."""
import io
import zipfile
from xml.etree import ElementTree as ET

import pytest
from PIL import Image

from engine.epub.renderer import render_epub
from engine.epub.xhtml import chapter_xhtml, image_view_filename
from engine.reflowdoc.editing import update_semantic_block
from engine.reflowdoc.models import InlineImageNode, ReflowDocument
from engine.reflowdoc.repair import repair_block
from engine.validation.epub import assert_valid
from engine.validation.reflow import quality_report

NS = {"h": "http://www.w3.org/1999/xhtml"}


def sample():
    image = io.BytesIO()
    Image.new("RGB", (80, 40), "white").save(image, format="PNG")
    return ReflowDocument.model_validate({
        "metadata": {"title": "Uji HP", "languages": ["id"]},
        "resources": [{"id": "r", "kind": "image", "filename": "word.png", "media_type": "image/png", "content": image.getvalue()}],
        "chapters": [{"id": "c", "blocks": [
            {"id": "p", "type": "paragraph", "footnote_refs": ["1"], "content": [{"type": "span", "text": "Bacaan¹ dan x².", "lang": "id", "dir": "ltr"}]},
            {"id": "n", "type": "footnote", "marker": "1", "source_image_resource_id": "r", "blocks": [
                {"id": "footnotes", "type": "paragraph", "content": [{"type": "text", "text": "1. Sumber "}, {"type": "inline_image", "resource_id": "r", "alt": "istilah"}, {"type": "text", "text": " utuh."}]}]},
            {"id": "next", "type": "paragraph", "content": [{"type": "text", "text": "Lanjutan bacaan."}]},
            {"id": "arabic", "type": "image", "resource_id": "r", "lang": "ar", "alt": "Arab sumber", "warnings": ["ARABIC_RENDERED_AS_IMAGE"], "footnote_refs": ["1"]},
            {"id": "frame", "type": "image", "resource_id": "r", "decorative": True},
            {"id": "logo", "type": "image", "resource_id": "r"},
        ]}],
    })


def test_only_explicit_references_move_notes_and_all_return_targets_exist():
    doc = sample()
    before = doc.model_dump_json()
    root = ET.fromstring(chapter_xhtml(doc, doc.chapters[0]))
    body = root.find("h:body", NS)
    assert "".join(body[0].itertext()) == "Bacaan¹ dan x²."
    assert "".join(body[1].itertext()) == "Lanjutan bacaan."
    refs = root.findall('.//h:a[@role="doc-noteref"]', NS)
    assert [a.text for a in refs] == ["¹", "Catatan 1"]
    assert all(a.attrib["href"] == "#n" for a in refs)
    note = root.find('.//h:aside[@id="n"]', NS)
    assert note.attrib["aria-label"] == "Catatan kaki 1"
    assert note.find('h:h3[@class="footnote-label"]', NS).text == "Catatan kaki 1"
    assert note in list(body[-1])
    assert body[-1].attrib["id"] != "footnotes"  # nested content owns this id
    backlinks = note.findall('.//h:a[@role="doc-backlink"]', NS)
    assert [a.attrib["href"] for a in backlinks] == ["#" + a.attrib["id"] for a in refs]
    ids = [e.attrib["id"] for e in root.iter() if "id" in e.attrib]
    assert len(ids) == len(set(ids))
    assert doc.model_dump_json() == before


@pytest.mark.parametrize("mode", ["unverified", "duplicate"])
def test_ambiguous_or_unverified_superscripts_never_become_links(mode):
    doc = sample()
    if mode == "unverified":
        doc.chapters[0].blocks[0].footnote_refs = []
        doc.chapters[0].blocks[3].footnote_refs = []
    else:
        note = doc.chapters[0].blocks[1].model_copy(deep=True)
        note.id = "n2"
        note.blocks[0].id = "child2"
        doc.chapters[0].blocks.append(note)
    root = ET.fromstring(chapter_xhtml(doc, doc.chapters[0]))
    assert not root.findall('.//h:a[@role="doc-noteref"]', NS)
    assert root.find('.//h:section[@class="endnotes"]', NS) is None
    assert root.find("h:body", NS)[1].tag.endswith("aside")


def test_inline_source_images_and_decoration_preserve_package_pixels():
    doc = sample()
    data = render_epub(doc)
    assert_valid(data)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.read("EPUB/resources/word.png") == doc.resources[0].content
        root = ET.fromstring(z.read("EPUB/chapter-001.xhtml"))
        inline = root.find('.//h:img[@class="inline-source"]', NS)
        assert inline.attrib["src"] == "resources/word.png"
        assert inline.attrib["alt"] == "istilah"
        assert root.find('.//*[@id="frame"]') is None
        assert root.find('.//*[@id="logo"]') is not None
        for link in root.findall(".//h:a", NS):
            href = link.attrib["href"]
            if href.startswith("image-view-"):
                view = ET.fromstring(z.read("EPUB/" + href))
                assert view.find('.//h:details/h:div/h:img', NS).attrib["src"] == "resources/word.png"
                enlarged = view.find('.//h:div[@class="image-enlarged"]', NS)
                assert enlarged.attrib["tabindex"] == "0"
                assert enlarged.find("h:img", NS).attrib["src"] == "resources/word.png"
                assert view.find('.//h:figure[@id="gambar-utuh"]/h:img', NS).attrib["src"] == "resources/word.png"
                assert view.find('.//h:a', NS).attrib["href"].startswith("chapter-001.xhtml#")
        opf = ET.fromstring(z.read("EPUB/content.opf"))
        opfns = {"o": "http://www.idpf.org/2007/opf"}
        manifest = {item.attrib["id"]: item.attrib["href"] for item in opf.findall("o:manifest/o:item", opfns)}
        spine = opf.findall("o:spine/o:itemref", opfns)
        views = [item for item in spine if manifest[item.attrib["idref"]].startswith("image-view-")]
        assert len(views) == 2
        assert all(item.attrib["linear"] == "no" for item in views)
        nav = z.read("EPUB/nav.xhtml").decode()
        assert "Catatan kaki" in nav and 'chapter-001.xhtml#n' in nav
        view = ET.fromstring(z.read("EPUB/" + image_view_filename("arabic")))
        assert view.find('.//h:details/h:div', NS).attrib["dir"] == "rtl"
        assert view.find('.//h:div[@class="image-enlarged"]', NS).attrib["dir"] == "rtl"
        assert root.find('.//h:figure[@id="arabic"]', NS).attrib["class"] == "source-image"


def test_missing_inline_or_note_source_resource_blocks_export():
    doc = sample()
    doc.resources = []
    report = quality_report(doc)
    assert not report["can_export"]
    assert any(i["code"] == "MISSING_RESOURCE" and i["block_ids"] == ["footnotes"] for i in report["issues"])
    assert any(i["code"] == "MISSING_RESOURCE" and i["block_ids"] == ["n"] for i in report["issues"])


def test_image_only_paragraph_is_readable_and_cannot_be_flattened_by_edit_or_repair():
    doc = sample()
    paragraph = doc.chapters[0].blocks[1].blocks[0]
    original_node = paragraph.content[1].model_copy(deep=True)
    repaired, _ = repair_block(paragraph)
    assert [n for n in repaired.content if isinstance(n, InlineImageNode)] == [original_node]
    for edit in [{"text": paragraph.text}, {"type": "quote"}]:
        with pytest.raises(ValueError, match="source images"):
            update_semantic_block(paragraph, **edit)
    paragraph.content = [InlineImageNode(resource_id="r")]
    doc.chapters[0].blocks = [paragraph]
    assert quality_report(doc)["can_export"]
    assert image_view_filename("../unsafe") == image_view_filename("../unsafe")
    assert "/" not in image_view_filename("../unsafe")
