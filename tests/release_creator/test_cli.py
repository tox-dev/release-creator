"""Root command tests."""

import sys
from runpy import run_module
lazy import ast
lazy from pathlib import Path

lazy import pytest


def test_module_entrypoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## 1.2.3 (2026-10-18)\n")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "notes",
            "--changelog",
            str(changelog),
            "--tag",
            "1.2.3",
            "--repository",
            "tox-dev/example",
        ],
    )
    run_module("release_creator", run_name="__main__")
    assert "https://github.com/tox-dev/example/commits/1.2.3" in capsys.readouterr().out


def test_source_imports_are_lazy() -> None:
    source = Path(__file__).resolve().parents[2] / "src"
    for path in source.rglob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"))
        imports = (node for node in ast.walk(module) if isinstance(node, (ast.Import, ast.ImportFrom)))
        assert all(
            node.is_lazy or (isinstance(node, ast.ImportFrom) and node.module == "__future__") for node in imports
        ), path
