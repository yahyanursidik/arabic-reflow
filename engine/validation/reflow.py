"""Non-destructive semantic quality and reference checks for review/export."""

from __future__ import annotations

from collections import Counter

from engine.reflowdoc.models import ReflowDocument
from engine.reflowdoc.traversal import iter_blocks
from engine.epub.xml import WARN_XML_CHARACTERS, output_diagnostics


def quality_report(document: ReflowDocument) -> dict:
    blocks = list(iter_blocks(document))
    counts = Counter(block.type for block in blocks)
    ids = Counter(block.id for block in blocks)
    resource_ids = Counter(resource.id for resource in document.resources)
    resources = {resource.id: resource for resource in document.resources}
    issues = []

    def issue(code, severity, message, block_ids=None):
        issues.append({"code": code, "severity": severity, "message": message, "block_ids": block_ids or []})

    if not any(
        bool(getattr(block, "text", "").strip())
        or any(cell.text.strip() for row in getattr(block, "rows", []) for cell in row)
        or bool(getattr(block, "resource_id", None) or getattr(block, "fallback_resource_id", None))
        or any(getattr(node, "resource_id", None) for node in getattr(block, "content", []))
        for block in blocks
    ):
        issue("EMPTY_DOCUMENT", "error", "No readable content was reconstructed; scanned pages may require OCR.")
    duplicate_ids = [key for key, count in ids.items() if count > 1]
    if duplicate_ids:
        issue("DUPLICATE_BLOCK_IDS", "error", "Block identifiers must be unique.", duplicate_ids)
    if any(count > 1 for count in resource_ids.values()):
        issue("DUPLICATE_RESOURCE_IDS", "error", "Resource identifiers must be unique.")
    if document.metadata.cover_resource_id and document.metadata.cover_resource_id not in resource_ids:
        issue("MISSING_COVER_RESOURCE", "error", "The selected cover resource is missing.")
    elif document.metadata.cover_resource_id:
        cover = resources[document.metadata.cover_resource_id]
        if cover.kind != "image" or not cover.content:
            issue("INVALID_COVER_RESOURCE", "error", "The selected cover has no usable image payload.")

    xml = output_diagnostics(document)
    review_ids = set(xml["block_ids"])
    if xml["count"]:
        issue(
            WARN_XML_CHARACTERS, "warning",
            f"{xml['count']} character(s) cannot be represented in XML 1.0 "
            f"({', '.join(xml['codepoints'])}). EPUB output excludes them; "
            "the source PDF and ReflowDoc retain the originals. Review the affected blocks.",
            xml["block_ids"],
        )
    pages = {}
    for block in blocks:
        # SOURCE_VERIFIED is an explicit comparison with the source PDF.
        # It resolves the old extraction score without inventing a new one;
        # current Arabic, XML, resource and uncertainty checks still apply.
        if (
            ("SOURCE_VERIFIED" not in block.warnings and block.confidence is not None and block.confidence < 0.8)
            or (block.arabic_integrity is not None and block.arabic_integrity.score < 0.85)
            or any("UNCERTAIN" in code or "LOW_CONFIDENCE" in code or "LOW_ARABIC" in code for code in block.warnings)
        ):
            review_ids.add(block.id)
        references = [getattr(block, "resource_id", None), getattr(block, "fallback_resource_id", None),
                      getattr(block, "source_image_resource_id", None)]
        references.extend(getattr(node, "resource_id", None) for node in getattr(block, "content", []))
        for reference in filter(None, references):
            if reference not in resource_ids:
                issue("MISSING_RESOURCE", "error", f"Resource for block {block.id} is missing.", [block.id])
            elif not resources[reference].content or resources[reference].kind != "image":
                issue("INVALID_RESOURCE", "error", f"Image resource for block {block.id} has no usable payload.", [block.id])
        if block.source:
            summary = pages.setdefault(block.source.page, {"page": block.source.page, "block_count": 0, "review_block_ids": []})
            summary["block_count"] += 1
            if block.id in review_ids:
                summary["review_block_ids"].append(block.id)

    return {
        "block_count": len(blocks),
        "type_counts": dict(sorted(counts.items())),
        "edited_block_count": sum(block.modified_by_user for block in blocks),
        "source_verified_block_count": sum("SOURCE_VERIFIED" in block.warnings for block in blocks),
        "review_block_ids": [block.id for block in blocks if block.id in review_ids],
        "pages": list(pages[key] for key in sorted(pages)),
        "issues": issues,
        "can_export": not any(item["severity"] == "error" for item in issues),
        "xml_output": xml,
    }
