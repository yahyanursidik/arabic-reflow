"""Freeze the engine's current extraction of each fixture into tests/golden/.

Golden files are committed review artifacts: a test failure against them means
an approved fixture lost characters, harakat, or reading order (release gate).
Only re-run this when a fixture or extraction behavior intentionally changed —
and diff the result carefully before committing.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from engine.analyzer.analyzer import analyze
from engine.arabic.unicode import count_harakat, is_arabic_letter, is_presentation_form
from engine.extraction.extractor import extract

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
GOLDEN_DIR = Path(__file__).resolve().parents[1] / "tests" / "golden"


def golden_for(pdf_path: Path) -> dict:
    profile = analyze(pdf_path)
    raw = extract(pdf_path)

    pages = []
    all_text_parts: list[str] = []
    for page in raw.pages:
        blocks = [block.text for block in page.blocks]
        all_text_parts.extend(blocks)
        pages.append({"page": page.page, "blocks": blocks})

    full_text = "\n".join(all_text_parts)
    return {
        "fixture": pdf_path.name,
        "page_count": profile.page_count,
        "classification": profile.classification.value,
        "arabic_detected": profile.arabic_detected,
        "arabic_letter_count": sum(1 for ch in full_text if is_arabic_letter(ch)),
        "harakat_count": count_harakat(full_text),
        "presentation_form_count": sum(1 for ch in full_text if is_presentation_form(ch)),
        "full_text_sha256": hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
        "pages": pages,
    }


def main() -> int:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(FIXTURES_DIR.glob("*.pdf"))
    if not pdfs:
        print("no fixtures found; run scripts/make_fixtures.py first", file=sys.stderr)
        return 1
    for pdf_path in pdfs:
        golden = golden_for(pdf_path)
        target = GOLDEN_DIR / (pdf_path.stem + ".golden.json")
        target.write_text(
            json.dumps(golden, indent=2, ensure_ascii=False) + "\n", "utf-8"
        )
        print(
            f"froze {target.name}: {golden['page_count']} pages, "
            f"{golden['harakat_count']} harakat, "
            f"{golden['presentation_form_count']} presentation forms"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
