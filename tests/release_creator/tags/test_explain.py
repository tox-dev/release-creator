"""What the tags command reports on stderr about its choices."""

import sys
from io import StringIO
from typing import TYPE_CHECKING

import pytest

from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def fragments(tmp_path: Path) -> Path:
    for name in ("+one.feature.md", "+two.feature.md", "+three.bugfix.md"):
        (tmp_path / name).write_text("Change something.\n")
    return tmp_path


def _next(monkeypatch: pytest.MonkeyPatch, directory: Path, tags: str, bump: str = "auto") -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "--next", bump, "--directory", str(directory)])
    monkeypatch.setattr(sys, "stdin", StringIO(tags))
    main()


def test_tags_next_explains_on_stderr(
    fragments: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _next(monkeypatch, fragments, "1.17.7\n1.17.8\njunk\n")

    assert capsys.readouterr().err == (
        f"Fragment directory: {fragments} (from --directory)\n"
        "Ignored 1 non-release tag (not major.minor.patch): junk\n"
        "Current version: 1.17.8 (newest of 2 release tags)\n"
        "Next version: 1.18.0 (minor bump from 3 pending fragments: 1 bugfix, 2 feature)\n"
    )


def test_tags_next_keeps_stdout_to_the_version(
    fragments: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _next(monkeypatch, fragments, "1.17.7\n1.17.8\njunk\n")

    assert capsys.readouterr().out == "1.18.0\n"


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(("major", "1.2.3\n", "Next version: 2.0.0 (major bump requested)\n"), id="requested"),
        pytest.param(("auto", "", "Next version: 0.0.1 (patch bump: no pending fragments)\n"), id="no-fragments"),
        pytest.param(
            ("patch", "1.0.0rc1\n", "Next version: 1.0.0 (patch bump requested, finalizing prerelease 1.0.0rc1)\n"),
            id="prerelease",
        ),
    ],
)
def test_tags_next_explains_the_bump(
    case: tuple[str, str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bump, tags, expected = case
    _next(monkeypatch, tmp_path, tags, bump)

    assert capsys.readouterr().err.splitlines(keepends=True)[-1] == expected


def test_tags_next_explains_missing_tags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _next(monkeypatch, tmp_path, "")

    assert "Current version: 0.0.0 (no release tags yet)\n" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("package", "expected"),
    [
        pytest.param(None, "Fragment directory: changelog.d (default)\n", id="default"),
        pytest.param(
            "pkg",
            "Fragment directory: changelog.d/pkg (default for package pkg)\n"
            "Package scope: pkg (1 of 2 tags start with pkg/)\n",
            id="package",
        ),
    ],
)
def test_tags_next_explains_the_default_directory(
    package: str | None,
    expected: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    scope = [] if package is None else ["--package", package]
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "--next", "patch", *scope])
    monkeypatch.setattr(sys, "stdin", StringIO("pkg/1.0.0\nother/2.0.0\n"))

    main()

    assert capsys.readouterr().err.startswith(expected)


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        pytest.param("1.2.3", "Previous release tag: 1.2.2 (newest release tag before 1.2.3)\n", id="found"),
        pytest.param("1.0.0", "Previous release tag: none (no release tag before 1.0.0)\n", id="first"),
        pytest.param("nightly", "Previous release tag: none (nightly is not a major.minor.patch tag)\n", id="invalid"),
    ],
)
def test_tags_previous_explains_on_stderr(
    tag: str, expected: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", tag, "--previous"])
    monkeypatch.setattr(sys, "stdin", StringIO("1.0.0\n1.2.2\n1.2.3\n"))

    main()

    assert capsys.readouterr().err == expected
