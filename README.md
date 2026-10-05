# Reflow — Arabic–Latin PDF to EPUB 3 Reconstruction Engine

Open-source application that converts PDF documents containing mixed Latin and
Arabic text into clean, semantic, reflowable EPUB 3 files.

> Preserve first. Reconstruct second. Never invent.

This is not a format converter: it reconstructs documents. It preserves source
text, understands page structure, respects mixed LTR/RTL directionality,
reconstructs reading order, and produces EPUB output that reflows comfortably
across screen sizes.

## Governing documents

Read these before implementing any feature (see `VIBE-CODING-INSTRUCTIONS.md`):

1. [PRD.md](PRD.md)
2. [ARCHITECTURE.md](ARCHITECTURE.md)
3. [REFLOWDOC-SPEC.md](REFLOWDOC-SPEC.md)
4. [ARABIC-ENGINE.md](ARABIC-ENGINE.md)
5. [MVP-BACKLOG.md](MVP-BACKLOG.md)

## Architecture boundary

```text
Input Adapter (PDF/OCR) → ReflowDoc → Output Renderer (EPUB/preview/JSON)
```

No renderer may depend on PDF internals, and no parser may depend on EPUB
concerns. ReflowDoc (`engine/reflowdoc/`) is the only contract between them.

## Repository layout

```text
engine/        # processing engine (pure Python, no web framework code)
  analyzer/    # PDF profile: native vs scanned vs hybrid
  extraction/  # raw page/block/span primitives (PyMuPDF)
  ocr/         # pluggable OCR adapters (M5)
  layout/      # columns, regions, zoning (M2/M6)
  language/    # natural-language labels (id, ar, en, unknown)
  arabic/      # script detection, Unicode diagnostics, integrity
  reconstruction/  # primitives -> semantic blocks (M2)
  reflowdoc/   # canonical intermediate model + JSON schema
  epub/        # EPUB 3 renderer (M4)
  validation/  # output validation
apps/web/      # Next.js review UI
apps/api/      # FastAPI service
packages/      # shared generated schemas (reflowdoc.schema.json)
tests/         # unit + fixture + golden + snapshot tests
scripts/       # fixture generation and maintenance scripts
docker/        # Dockerfiles
```

## Development setup

Requires Python 3.11+ (project targets 3.14) and Node 20+.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows Git Bash: .venv/Scripts/activate
pip install -e ".[api,dev]"

# Regenerate the test fixture corpus (already committed; needs Arabic-capable fonts)
python scripts/make_fixtures.py

# Run the test suite (unit, fixture, golden, snapshot)
pytest

# Regenerate the shared JSON schema after ReflowDoc changes
python -m engine.reflowdoc.schema --check
```

### Web app

```bash
cd apps/web
npm install
npm run dev
```

## Docker

```bash
docker compose up       # boots api (http://localhost:8000) and web (http://localhost:3000)
```

Note: Docker Desktop is not required for engine development or tests.

## Testing rules (summary)

- Every Arabic-sensitive change tests: Arabic without harakat, with harakat,
  mixed Indonesian + Arabic, punctuation near Arabic, and one approved golden
  fixture.
- Reading-order changes test single-column, multi-column, and footnote pages.
- EPUB changes must generate valid XHTML/EPUB and preserve `lang`/`dir`.
- A release is blocked if an approved Arabic fixture loses characters,
  harakat, or reading order (MVP-BACKLOG.md release gate).

## License

MIT.
