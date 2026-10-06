"""Official EPUB validation via epubcheck (backlog M4-05 hardening).

The structural validator in engine.validation.epub catches packaging
mistakes cheaply; epubcheck (W3C) is the authoritative checker. This adapter
locates the epubcheck JAR (EPUBCHECK_JAR env or an `epubcheck` launcher on
PATH) and a Java runtime; both are optional locally and installed in CI.

Finding epubcheck: https://github.com/w3c/epubcheck/releases
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EpubCheckResult:
    passed: bool
    returncode: int
    messages: list[str] = field(default_factory=list)


def epubcheck_available() -> bool:
    """True when a JAR (or launcher) and Java are both reachable."""
    return _jar_command() is not None and shutil.which("java") is not None


def _jar_command() -> list[str] | None:
    jar = os.environ.get("EPUBCHECK_JAR")
    if jar:
        if Path(jar).exists():
            return ["java", "-jar", jar]
        return None
    launcher = shutil.which("epubcheck")
    if launcher:
        return [launcher]
    return None


def run_epubcheck(data: bytes) -> EpubCheckResult:
    """Validate an EPUB package with epubcheck; raises when unavailable."""
    command = _jar_command()
    if command is None or shutil.which("java") is None:
        raise RuntimeError(
            "epubcheck is unavailable; install Java and set EPUBCHECK_JAR "
            "to the epubcheck.jar (or put an `epubcheck` launcher on PATH)"
        )
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "book.epub")
        with open(target, "wb") as handle:
            handle.write(data)
        process = subprocess.run(
            [*command, target],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    output = (process.stdout + "\n" + process.stderr).splitlines()
    # Keep only meaningful lines (epubcheck prints blank spacers and a long
    # help banner on failure to run).
    messages = [
        line.strip()
        for line in output
        if line.strip() and not line.startswith("EPUB Check version")
    ]
    return EpubCheckResult(
        passed=process.returncode == 0,
        returncode=process.returncode,
        messages=messages,
    )
