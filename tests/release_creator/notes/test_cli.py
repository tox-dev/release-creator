"""Note command tests."""

import sys
from typing import TYPE_CHECKING

import pytest

from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path


def test_notes_cli_renders_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## 1.2.3 (2026-10-18)\n\n### Fixed\n\n- Correct a bug.\n")
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
    main()
    assert "### Bug fixes\n\n- Correct a bug." in capsys.readouterr().out


def test_notes_cli_renders_rst(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "changelog.rst"
    changelog.write_text("1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Correct a bug (:issue:`4`).\n")
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
    main()
    assert "- Correct a bug ([#4](https://github.com/tox-dev/example/issues/4))." in capsys.readouterr().out


def test_notes_cli_selects_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## example\n\n### 1.2.3 (today)\n\n#### Fixed\n\n- Correct a bug.\n")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "notes",
            "--changelog",
            str(changelog),
            "--tag",
            "example/1.2.3",
            "--repository",
            "tox-dev/example",
            "--package",
            "example",
        ],
    )

    main()

    assert "### Bug fixes\n\n- Correct a bug." in capsys.readouterr().out


@pytest.mark.parametrize("heading", [pytest.param("##", id="h2"), pytest.param("###", id="h3")])
def test_notes_cli_reads_generated_notes(
    heading: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## 1.2.3 (today)\n\n### Added\n\n- New option by [@alice](https://github.com/alice).\n")
    generated = tmp_path / "generated.md"
    generated.write_text(f"{heading} New Contributors\n* @alice made their first contribution in #42\n")
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
            "--generated-notes",
            str(generated),
        ],
    )

    main()

    assert (
        "### New Contributors\n\n"
        "- @alice made their first contribution in [#42](https://github.com/tox-dev/example/pull/42)"
        in capsys.readouterr().out
    )


def test_notes_cli_reports_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "notes",
            "--changelog",
            str(tmp_path / "missing.md"),
            "--tag",
            "1.2.3",
            "--repository",
            "tox-dev/example",
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    expected_usage_error = 2
    assert error.value.code == expected_usage_error
    assert "missing.md" in capsys.readouterr().err
