"""Note command tests."""

import sys
from typing import TYPE_CHECKING

import pytest

lazy from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("name", "source"),
    [
        pytest.param("CHANGELOG.md", "## 1.2.3 (2026-10-18)\n\n- Correct a bug.\n", id="markdown"),
        pytest.param("changelog.rst", "1.2.3 (2026-10-18)\n------------------\n\n- Correct a bug.\n", id="rst"),
    ],
)
def test_notes_prints_section_in_source_format(
    name: str, source: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (changelog := tmp_path / name).write_text(source, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["release-creator", "notes", "--changelog", str(changelog), "--tag", "1.2.3"])

    main()

    assert capsys.readouterr().out == "- Correct a bug.\n"


def test_notes_selects_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (changelog := tmp_path / "CHANGELOG.md").write_text("## a\n\n### 1.0.0\n\n- A.\n\n## b\n\n### 1.0.0\n\n- B.\n")
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "notes", "--changelog", str(changelog), "--tag", "b/1.0.0", "--package", "b"],
    )

    main()

    assert capsys.readouterr().out == "- B.\n"


def test_notes_reports_missing_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (changelog := tmp_path / "CHANGELOG.md").write_text("## 1.0.0\n")
    monkeypatch.setattr(sys, "argv", ["release-creator", "notes", "--changelog", str(changelog), "--tag", "2.0.0"])

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "expected one changelog section for 2.0.0, found 0" in capsys.readouterr().err
