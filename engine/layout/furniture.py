"""Header/footer and page-number detection (backlog M2-05, M2-06).

Repeated-position heuristics only (PRD 8.11). False positives are minimized:

- headers/footers must repeat (normalized) in the same band on at least two
  pages and stay short;
- page numbers must be almost purely numeric inside the top/bottom bands.

Removed blocks are recorded in the LayoutReport — page provenance is
preserved, never destroyed (M2-06).
"""

from __future__ import annotations

import re

from engine.extraction.models import RawBlock, RawDocument
from engine.layout.models import FurnitureItem, LayoutReport

TOP_BAND = 0.15  # block must end within the top 15% of the page height
BOTTOM_BAND = 0.85  # block must start within the bottom 15%
MIN_REPEAT = 2
MAX_FURNITURE_WORDS = 10

# Page numbers: digits with optional decoration ("- 7 -", "(12)"), or labeled
# ("Page 7", "Halaman 7"). Deliberately strict — any prose containing a digit
# must never match (PRD 8.11: minimize false positives).
_PAGE_NUMBER = re.compile(r"^[\s\-–—.(\[]*(\d{1,4})[\s\-–—.)\]]*$")
_LABELED_PAGE = re.compile(r"^(?:page|halaman|p)\.?\s+(\d{1,4})$", re.IGNORECASE)
_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _printed_page_number(text: str) -> int | None:
    folded = text.translate(_ARABIC_INDIC)
    match = _PAGE_NUMBER.match(folded) or _LABELED_PAGE.match(folded)
    return int(match.group(1)) if match else None


def _normalize(text: str) -> str:
    """Repetition key: digits and Arabic-Indic digits become '#', case folded."""
    folded = text.translate(_ARABIC_INDIC)
    return re.sub(r"\d+", "#", " ".join(folded.split())).casefold()


def _band(block: RawBlock, height: float) -> str | None:
    if block.bbox[3] <= height * TOP_BAND:
        return "header"
    if block.bbox[1] >= height * BOTTOM_BAND:
        return "footer"
    return None


def detect_layout(raw: RawDocument) -> tuple[RawDocument, LayoutReport]:
    """Remove furniture blocks and report what was removed.

    Returns a new RawDocument (input is not mutated) plus a LayoutReport.
    """
    candidates: dict[int, list[tuple[RawBlock, str, str]]] = {}
    repetition: dict[tuple[str, str], int] = {}

    for page in raw.pages:
        page_candidates = []
        for block in page.blocks:
            text = " ".join(block.text.split())
            if not text or len(text.split()) > MAX_FURNITURE_WORDS:
                continue
            band = _band(block, page.height)
            if band is None:
                continue
            page_candidates.append((block, band, text))
            key = (band, _normalize(text))
            repetition[key] = repetition.get(key, 0) + 1
        candidates[page.page] = page_candidates

    items: list[FurnitureItem] = []
    page_number_map: dict[int, int] = {}
    removed: set[tuple[int, int]] = set()

    for page in raw.pages:
        for block, band, text in candidates[page.page]:
            kind: str | None = None
            printed = _printed_page_number(text)

            if printed is not None:
                kind = "page_number"
            elif repetition[(band, _normalize(text))] >= MIN_REPEAT:
                kind = band  # "header" or "footer"

            if kind is None:
                continue
            removed.add((page.page, block.number))
            items.append(
                FurnitureItem(
                    page=page.page,
                    block_number=block.number,
                    kind=kind,  # type: ignore[arg-type]
                    text=text,
                    printed_page_number=printed,
                )
            )
            if kind == "page_number" and printed is not None:
                page_number_map[page.page] = printed

    new_pages = [
        page.model_copy(
            update={
                "blocks": [
                    b
                    for b in page.blocks
                    if (page.page, b.number) not in removed
                ]
            }
        )
        for page in raw.pages
    ]
    report = LayoutReport(removed_furniture=items, page_number_map=page_number_map)
    return raw.model_copy(update={"pages": new_pages}), report
