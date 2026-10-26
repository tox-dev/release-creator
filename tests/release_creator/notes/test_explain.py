"""What the notes command reports on stderr about its choices."""

import sys
from typing import TYPE_CHECKING

import pytest

from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path

_CHANGELOG = "## 1.2.3 (2026-10-18)\n\n### Added\n\n- Add a flag.\n- Add a cache.\n\n### Fixed\n\n- Correct a bug.\n"


@pytest.fixture
def changelog(tmp_path: Path) -> Path:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(_CHANGELOG)
    return path


def _render(monkeypatch: pytest.MonkeyPatch, changelog: Path, *options: str) -> None:
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
            *options,
        ],
    )
    main()


def test_notes_explains_on_stderr(
    changelog: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _render(monkeypatch, changelog, "--previous", "1.2.2", "--artifact-url", "https://pypi.org/project/example/1.2.3/")

    assert capsys.readouterr().err == (
        f"Changelog format: Markdown ({changelog} does not end in .rst)\n"
        f"Release notes for 1.2.3: 3 entries in 2 categories from {changelog}\n"
        "Comparison link: compare/1.2.2...1.2.3\n"
        "Artifact link: PyPI release -> https://pypi.org/project/example/1.2.3/\n"
    )


def test_notes_keeps_stdout_to_the_body(
    changelog: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _render(monkeypatch, changelog)

    assert capsys.readouterr().out == (
        "### Features\n\n- Add a flag.\n- Add a cache.\n\n### Bug fixes\n\n- Correct a bug.\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_notes_explains_missing_links(
    changelog: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _render(monkeypatch, changelog)

    assert capsys.readouterr().err.splitlines()[-2:] == [
        "Comparison link: commits/1.2.3 (no --previous tag)",
        "Artifact link: none (no --artifact-url)",
    ]


def test_notes_explains_rst_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "changelog.rst"
    changelog.write_text("1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Correct a bug.\n")

    _render(monkeypatch, changelog)

    assert capsys.readouterr().err.splitlines()[:2] == [
        f"Changelog format: reStructuredText ({changelog} ends in .rst)",
        f"Release notes for 1.2.3: 1 entry in 1 category from {changelog}",
    ]


def test_notes_explains_package_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## example\n\n### 1.2.3 (today)\n\n#### Fixed\n\n- Correct a bug.\n")

    _render(monkeypatch, changelog, "--package", "example")

    assert (
        f"Release notes for 1.2.3: 1 entry in 1 category from the example section of {changelog}\n"
        in capsys.readouterr().err
    )
