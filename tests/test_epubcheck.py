"""Official epubcheck validation of generated packages (M4-05 hardening).

Skips when Java/epubcheck are not installed locally; CI installs both and
sets EPUBCHECK_JAR, so the checks below run for real there.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from engine.epub.renderer import render_epub
from engine.ocr.base import render_page_png
from engine.pipeline import build_epub, build_reflowdoc
from engine.reflowdoc.models import ReflowDocument, Resource
from engine.validation.epubcheck import epubcheck_available, run_epubcheck

pytestmark = pytest.mark.skipif(
    not epubcheck_available(),
    reason="epubcheck JAR + Java not available (set EPUBCHECK_JAR)",
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "fixture_name",
    ["mixed-id-ar.pdf", "indonesian-native.pdf", "table-grid.pdf"],
)
def test_fixture_epub_passes_epubcheck(fixture_name: str) -> None:
    _result, data, _report = build_epub(FIXTURES / fixture_name)
    result = run_epubcheck(data)
    assert result.passed, "\n".join(result.messages)


def test_cover_package_passes_epubcheck(fixtures_dir) -> None:
    """A chosen cover page must not break the package."""
    source = fixtures_dir / "indonesian-native.pdf"
    result = build_reflowdoc(source)
    pdf = pymupdf.open(source)
    png = render_page_png(pdf.load_page(0), dpi=100)
    pdf.close()
    result.document.resources.append(
        Resource(
            id="cover",
            kind="image",
            media_type="image/png",
            filename="cover.png",
            source_page=1,
            content=png,
        )
    )
    result.document.metadata.cover_resource_id = "cover"
    data = render_epub(result.document)
    check = run_epubcheck(data)
    assert check.passed, "\n".join(check.messages)
