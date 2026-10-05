"""EPUB structural validation (backlog M4-05).

Checks the package structure that must hold for the file to open correctly
(OCF container, OPF manifest/spine consistency, well-formed XHTML). Severe
problems block export; callers enforce that via `assert_valid`.

This is not a substitute for epubcheck; wire it in CI when a Java runtime is
available. See docs/epub.md.
"""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree

from pydantic import BaseModel, Field

SEVERE = "error"
WARNING = "warning"


class ValidationIssue(BaseModel):
    code: str
    severity: str
    message: str


class ValidationReport(BaseModel):
    ok: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def severe(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == SEVERE]


class EPUBValidationError(Exception):
    """Raised when an EPUB has severe structural problems (M4-05 gate)."""

    def __init__(self, report: ValidationReport) -> None:
        messages = "; ".join(i.message for i in report.severe)
        super().__init__(f"EPUB validation failed: {messages}")
        self.report = report


def _error(code: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, severity=SEVERE, message=message)


def validate_epub(data: bytes) -> ValidationReport:
    issues: list[ValidationIssue] = []

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return ValidationReport(
            ok=False, issues=[_error("EPUB_UNREADABLE", "not a valid zip archive")]
        )

    with archive:
        names = archive.namelist()

        if not names or names[0] != "mimetype":
            issues.append(_error("EPUB_MIMETYPE_POSITION", "mimetype must be the first entry"))
        else:
            info = archive.infolist()[0]
            if info.compress_type != zipfile.ZIP_STORED:
                issues.append(_error("EPUB_MIMETYPE_COMPRESSED", "mimetype must be stored uncompressed"))
            content = archive.read("mimetype").decode("utf-8", "replace")
            if content.strip() != "application/epub+zip":
                issues.append(_error("EPUB_MIMETYPE_INVALID", f"unexpected mimetype {content!r}"))

        if "META-INF/container.xml" not in names:
            issues.append(_error("EPUB_CONTAINER_MISSING", "META-INF/container.xml missing"))
            return ValidationReport(ok=False, issues=issues)

        try:
            container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
            rootfile = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
            opf_path = rootfile.get("full-path") if rootfile is not None else None
        except ElementTree.ParseError as exc:
            issues.append(_error("EPUB_CONTAINER_INVALID", f"container.xml unparseable: {exc}"))
            return ValidationReport(ok=False, issues=issues)

        if not opf_path or opf_path not in names:
            issues.append(_error("EPUB_OPF_MISSING", f"package document {opf_path!r} not in archive"))
            return ValidationReport(ok=False, issues=issues)

        try:
            opf = ElementTree.fromstring(archive.read(opf_path))
        except ElementTree.ParseError as exc:
            issues.append(_error("EPUB_OPF_INVALID", f"package document unparseable: {exc}"))
            return ValidationReport(ok=False, issues=issues)

        base = opf_path.rsplit("/", 1)[0] + "/" if "/" in opf_path else ""
        manifest = {item.get("id"): item.get("href") for item in opf.iter() if item.tag.endswith("item")}
        spine_refs = [
            itemref.get("idref") for itemref in opf.iter() if itemref.tag.endswith("itemref")
        ]

        for ref in spine_refs:
            if ref not in manifest:
                issues.append(_error("EPUB_SPINE_BROKEN", f"spine references missing manifest id {ref!r}"))
        for item_id, href in manifest.items():
            if href and (base + href) not in names:
                issues.append(_error("EPUB_MANIFEST_BROKEN", f"manifest item {item_id!r} file {href!r} missing"))

        for name in names:
            if name.endswith(".xhtml"):
                try:
                    root = ElementTree.fromstring(archive.read(name))
                except ElementTree.ParseError as exc:
                    issues.append(_error("XHTML_MALFORMED", f"{name}: {exc}"))
                    continue
                if root.get("lang") is None:
                    issues.append(
                        ValidationIssue(
                            code="XHTML_LANG_MISSING", severity=WARNING,
                            message=f"{name}: root element has no lang attribute",
                        )
                    )

    report = ValidationReport(ok=not issues, issues=issues)
    return report


def assert_valid(data: bytes) -> ValidationReport:
    """Validate and raise when severe problems exist (export gate, M4-05)."""
    report = validate_epub(data)
    if report.severe:
        raise EPUBValidationError(report)
    return report
