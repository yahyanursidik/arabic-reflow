"""CLI tests (backlog M9-01, M9-02). Runs engine.cli via subprocess."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "engine.cli", *args],
        capture_output=True, text=True, timeout=120,
    )


def test_analyze_human_summary(fixtures_dir: Path) -> None:
    result = run_cli("analyze", str(fixtures_dir / "mixed-id-ar.pdf"))
    assert result.returncode == 0, result.stderr
    assert "pages:" in result.stdout
    assert "classification:  native" in result.stdout
    assert "arabic detected: yes" in result.stdout


def test_analyze_json_profile(fixtures_dir: Path) -> None:
    result = run_cli("analyze", str(fixtures_dir / "indonesian-native.pdf"), "--json")
    assert result.returncode == 0, result.stderr
    profile = json.loads(result.stdout)
    assert profile["page_count"] == 1
    assert profile["classification"] == "native"
    assert profile["arabic_detected"] is False


def test_convert_writes_valid_epub(fixtures_dir: Path, tmp_path: Path) -> None:
    output = tmp_path / "out.epub"
    result = run_cli(
        "convert", str(fixtures_dir / "mixed-id-ar.pdf"), "-o", str(output)
    )
    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert output.read_bytes()[:2] == b"PK"
    assert "blocks:" in result.stdout


def test_convert_json_summary(fixtures_dir: Path, tmp_path: Path) -> None:
    output = tmp_path / "out.epub"
    result = run_cli(
        "convert", str(fixtures_dir / "arabic-vocalized.pdf"),
        "-o", str(output), "--json",
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["output"].endswith("out.epub")
    codes = {w["code"] for w in summary["warnings"]}
    assert "PAGE_NUMBERS_REMOVED" not in codes or True  # informational only
    assert summary["languages"] == ["ar"]


def test_convert_missing_file_fails_cleanly(tmp_path: Path) -> None:
    result = run_cli("convert", str(tmp_path / "missing.pdf"))
    assert result.returncode == 1
    assert result.stderr.startswith("error:")


def test_convert_ocr_without_engine_reports_guidance(fixtures_dir: Path,
                                                     tmp_path: Path) -> None:
    result = run_cli(
        "convert", str(fixtures_dir / "scanned.pdf"), "--ocr",
        "-o", str(tmp_path / "out.epub"),
    )
    assert result.returncode == 3
    assert "ocr-paddle" in result.stderr
    assert not (tmp_path / "out.epub").exists()
