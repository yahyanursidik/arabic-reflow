"""Pipeline wiring following ARCHITECTURE.md section 5.

Only the stages implemented so far are wired here; later stages (layout,
reading order, reconstruction, validation, rendering) plug in as they land.
"""

from __future__ import annotations

from engine.analyzer.analyzer import analyze
from engine.analyzer.models import DocumentProfile
from engine.arabic.detector import classify_block, infer_direction, classify_script
from engine.extraction.extractor import extract
from engine.extraction.models import RawDocument


def detect_scripts(raw: RawDocument) -> RawDocument:
    """Annotate spans and blocks with script and direction (M1-03, M1-04).

    Annotation only: text is never altered or normalized.
    """
    for page in raw.pages:
        for block in page.blocks:
            if block.type != "text":
                continue
            for line in block.lines:
                for span in line.spans:
                    span.script = classify_script(span.text)
                    span.dir = infer_direction(span.text)
            decision = classify_block(block.text)
            block.script = decision.script
            block.dir = decision.dir
    return raw


def analyze_and_extract(source: str | bytes) -> tuple[DocumentProfile, RawDocument]:
    """Analyze then extract; the two leading stages of the pipeline contract."""
    profile = analyze(source)
    raw = extract(source)
    return profile, raw
