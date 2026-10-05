"""FastAPI service (apps/api).

The API layer owns job lifecycle and HTTP contracts only. Document parsing
rules live in the engine (ARCHITECTURE.md 3.2).
"""

from fastapi import FastAPI

app = FastAPI(
    title="Reflow API",
    version="0.1.0",
    description="Mixed Arabic-Latin PDF to reflowable EPUB 3 conversion.",
)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
