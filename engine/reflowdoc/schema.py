"""JSON Schema export for ReflowDoc.

The generated schema lives in packages/schemas/ and is the shared contract
for any consumer that cannot import the Python models (e.g. the web app).
"""

from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path

from engine.reflowdoc.models import ReflowDocument

DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "packages" / "schemas" / "reflowdoc.schema.json"
)


def json_schema() -> dict:
    schema = ReflowDocument.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://reflow.dev/schemas/reflowdoc-0.1.json"
    return schema


def export_schema(path: Path = DEFAULT_SCHEMA_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_schema(), indent=2, ensure_ascii=False) + "\n", "utf-8")
    return path


def schema_version() -> str:
    """Engine version that owns the current ReflowDoc schema."""
    try:
        return metadata.version("reflow-engine")
    except metadata.PackageNotFoundError:
        return "0.1.0"


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Export or check the ReflowDoc JSON schema")
    parser.add_argument("--check", action="store_true", help="fail if the exported schema is stale")
    parser.add_argument("--out", type=Path, default=DEFAULT_SCHEMA_PATH)
    args = parser.parse_args()

    if args.check:
        current = args.out.read_text("utf-8") if args.out.exists() else ""
        fresh = json.dumps(json_schema(), indent=2, ensure_ascii=False) + "\n"
        if current != fresh:
            sys.exit(f"stale schema at {args.out}; run: python -m engine.reflowdoc.schema")
        print(f"schema up to date: {args.out}")
    else:
        print(f"exported: {export_schema(args.out)}")
