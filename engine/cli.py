"""Reflow command-line interface (backlog M9-01, M9-02).

    reflow analyze BOOK.pdf [--json]
    reflow convert BOOK.pdf [-o OUT.epub] [--ocr] [--engine paddle] [--json]

Correctness before speed: convert refuses to write an EPUB that fails
structural validation (exit code 2).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.analyzer.analyzer import analyze
from engine.validation.epub import EPUBValidationError


def cmd_analyze(args: argparse.Namespace) -> int:
    profile = analyze(args.pdf)
    if args.json:
        print(json.dumps(profile.model_dump(), ensure_ascii=False, indent=2))
        return 0
    print(f"file:            {Path(args.pdf).name}")
    print(f"pages:           {profile.page_count}")
    print(f"classification:  {profile.classification.value} "
          f"(confidence {profile.classification_confidence:.2f})")
    print(f"text layer:      {'yes' if profile.text_layer else 'no'}")
    print(f"arabic detected: {'yes' if profile.arabic_detected else 'no'}")
    if profile.likely_multicolumn_pages:
        print(f"multi-column:    pages {profile.likely_multicolumn_pages}")
    if profile.scanned_pages:
        print(f"scanned pages:   {profile.scanned_pages}")
    for warning in profile.warnings:
        print(f"warning:         [{warning.code}] {warning.message}")
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    from engine.epub.renderer import render_epub
    from engine.pipeline import build_reflowdoc
    from engine.validation.epub import assert_valid

    engine = None
    if args.ocr:
        from engine.ocr.engines import get_engine

        engine = get_engine(args.engine)

    result = build_reflowdoc(args.pdf, ocr_engine=engine)
    document = result.document
    data = render_epub(document)
    assert_valid(data)

    output = Path(args.output) if args.output else Path(args.pdf).with_suffix(".epub")
    output.write_bytes(data)

    blocks = [b for chapter in document.chapters for b in chapter.blocks]
    if args.json:
        print(json.dumps({
            "output": str(output),
            "pages": result.profile.page_count,
            "blocks": len(blocks),
            "languages": document.metadata.languages,
            "warnings": [w.model_dump() for w in document.warnings],
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"output:     {output}")
    print(f"pages:      {result.profile.page_count}")
    print(f"blocks:     {len(blocks)}")
    print(f"languages:  {', '.join(document.metadata.languages) or '-'}")
    if document.warnings:
        print("warnings:")
        for warning in document.warnings:
            page = f" (page {warning.source_page})" if warning.source_page else ""
            print(f"  - [{warning.code}]{page} {warning.message}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reflow",
        description="Convert mixed Arabic-Latin PDFs into reflowable EPUB 3.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser(
        "analyze", help="inspect a PDF: pages, classification, Arabic presence"
    )
    analyze_parser.add_argument("pdf", help="path to the PDF")
    analyze_parser.add_argument("--json", action="store_true", help="emit full JSON profile")
    analyze_parser.set_defaults(func=cmd_analyze)

    convert_parser = subparsers.add_parser(
        "convert", help="convert a PDF into a validated EPUB 3"
    )
    convert_parser.add_argument("pdf", help="path to the PDF")
    convert_parser.add_argument("-o", "--output", help="output EPUB path (default: <pdf>.epub)")
    convert_parser.add_argument(
        "--ocr", action="store_true", help="OCR scanned pages (requires an OCR extra)"
    )
    convert_parser.add_argument(
        "--engine", default="paddle", help="OCR engine name (default: paddle)"
    )
    convert_parser.add_argument("--json", action="store_true", help="emit JSON summary")
    convert_parser.set_defaults(func=cmd_convert)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except EPUBValidationError as exc:
        print(f"error: EPUB validation failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        from engine.ocr.base import OcrEngineUnavailable

        if isinstance(exc, OcrEngineUnavailable):
            print(f"error: {exc}", file=sys.stderr)
            return 3
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
