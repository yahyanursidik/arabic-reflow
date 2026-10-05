"""Golden regression tests (backlog M0-02, M1-05).

Each golden file is a manually reviewed, approved record of what the engine
extracts from a fixture. A failure here means the extraction pipeline changed
behavior: per MVP-BACKLOG.md release gate, a release is blocked if an approved
Arabic fixture loses source characters, harakat, or reading order.

If a change is intentional, re-run scripts/update_golden.py and review the diff.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from engine.arabic.unicode import count_harakat, is_arabic_letter, is_presentation_form
from engine.extraction.extractor import extract


def _actual(golden: dict, fixtures_dir) -> dict:
    raw = extract(fixtures_dir / golden["fixture"])
    pages = [{"page": page.page, "blocks": [b.text for b in page.blocks]} for page in raw.pages]
    full_text = "\n".join(b for page in pages for b in page["blocks"])
    return {
        "pages": pages,
        "arabic_letter_count": sum(1 for ch in full_text if is_arabic_letter(ch)),
        "harakat_count": count_harakat(full_text),
        "presentation_form_count": sum(1 for ch in full_text if is_presentation_form(ch)),
        "full_text_sha256": hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
    }


def test_golden_corpus_loads(golden_dir) -> None:
    goldens = sorted(golden_dir.glob("*.golden.json"))
    assert len(goldens) == 9


def test_arabic_golden_fixtures_do_not_regress(golden_dir, fixtures_dir) -> None:
    for golden_path in sorted(golden_dir.glob("*.golden.json")):
        golden = json.loads(golden_path.read_text("utf-8"))
        actual = _actual(golden, fixtures_dir)

        assert actual["full_text_sha256"] == golden["full_text_sha256"], (
            f"{golden['fixture']}: extracted text changed vs approved golden "
            f"({golden_path.name}); if intentional, re-run scripts/update_golden.py "
            "and review the diff"
        )
        assert actual["harakat_count"] == golden["harakat_count"], golden["fixture"]
        assert actual["arabic_letter_count"] == golden["arabic_letter_count"], (
            golden["fixture"]
        )
        assert actual["pages"] == golden["pages"], (
            f"{golden['fixture']}: block structure or reading order changed"
        )


def test_harakat_preserved_in_vocalized_fixture(golden_dir, fixtures_dir) -> None:
    golden = json.loads((golden_dir / "arabic-vocalized.golden.json").read_text("utf-8"))
    assert golden["harakat_count"] >= 60, "vocalized fixture lost its harakat"
    actual = _actual(golden, fixtures_dir)
    assert actual["harakat_count"] == golden["harakat_count"]


def test_mixed_fixture_keeps_inline_arabic(golden_dir) -> None:
    golden = json.loads((golden_dir / "mixed-id-ar.golden.json").read_text("utf-8"))
    assert golden["arabic_detected"] is True
    inline_block = next(b for p in golden["pages"] for b in p["blocks"]
                        if "Hadits ini diriwayatkan dari" in b)
    assert any(is_arabic_letter(ch) for ch in inline_block), "inline Arabic vanished"


def test_scanned_fixture_golden_has_no_text(golden_dir) -> None:
    golden = json.loads((golden_dir / "scanned.golden.json").read_text("utf-8"))
    assert all(b == "" or not b.strip() for p in golden["pages"] for b in p["blocks"])


def test_golden_classification_matches_analyzer(golden_dir, fixtures_dir) -> None:
    from engine.analyzer.analyzer import analyze

    for golden_path in sorted(golden_dir.glob("*.golden.json")):
        golden = json.loads(golden_path.read_text("utf-8"))
        profile = analyze(fixtures_dir / golden["fixture"])
        assert profile.classification.value == golden["classification"], golden["fixture"]
        assert profile.arabic_detected == golden["arabic_detected"], golden["fixture"]
