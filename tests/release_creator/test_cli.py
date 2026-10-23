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


def test_source_imports_are_lazy_unless_used_at_import_time() -> None:
    source = Path(__file__).resolve().parents[2] / "src"
    for path in source.rglob("*.py"):
        imports = (
            node
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, (ast.Import, ast.ImportFrom))
        )
        assert all(
            node.is_lazy
            or (isinstance(node, ast.ImportFrom) and node.module in {"__future__", "dataclasses"})
            or (isinstance(node, ast.Import) and all(alias.name == "re" for alias in node.names))
            for node in imports
        ), path
