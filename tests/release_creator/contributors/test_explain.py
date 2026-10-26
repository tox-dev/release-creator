"""What the contributors command reports on stderr about its choices."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final

lazy import pytest

from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    from tests.release_creator.contributors.conftest import GitHub

_PULLS: Final = {"42": ("alice", "User", "2026-10-20T10:00:00Z"), "43": ("carol", "User", "2026-10-21T10:00:00Z")}


def _changelog(tmp_path: Path, numbers: list[str]) -> Path:
    changelog = tmp_path / "CHANGELOG.md"
    entries = "".join(
        f"- Change {number} ([#{number}](https://github.com/tox-dev/example/pull/{number})).\n" for number in numbers
    )
    changelog.write_text(f"## 1.2.3 (2026-10-25)\n\n### Added\n\n{entries or '- Change things.\n'}")
    return changelog


def _add(monkeypatch: pytest.MonkeyPatch, changelog: Path) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "contributors",
            "--changelog",
            str(changelog),
            "--version",
            "1.2.3",
            "--repository",
            "tox-dev/example",
        ],
    )
    main()


def test_contributors_explains_on_stderr(
    tmp_path: Path, github: GitHub, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    github(_PULLS, {"carol"})
    changelog = _changelog(tmp_path, ["42", "43"])

    _add(monkeypatch, changelog)

    assert capsys.readouterr().err == (
        f"Checking 2 pull requests from the 1.2.3 section of {changelog.as_posix()}: #42, #43\n"
        "Returning contributors: @carol (merged a pull request before this release)\n"
        "New Contributors: @alice (#42)\n"
    )


def test_contributors_keeps_stdout_empty(
    tmp_path: Path, github: GitHub, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    github(_PULLS, {"carol"})

    _add(monkeypatch, _changelog(tmp_path, ["42", "43"]))

    assert not capsys.readouterr().out


def test_contributors_explains_section_without_pull_requests(
    tmp_path: Path, github: GitHub, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    github({}, set())
    changelog = _changelog(tmp_path, [])

    _add(monkeypatch, changelog)

    assert capsys.readouterr().err == (
        f"New Contributors: none for 1.2.3 (its section in {changelog.as_posix()} links no pull requests)\n"
    )


def test_contributors_explains_only_returning_authors(
    tmp_path: Path, github: GitHub, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    github(_PULLS, {"alice", "carol"})

    _add(monkeypatch, _changelog(tmp_path, ["42", "43"]))

    assert capsys.readouterr().err.splitlines()[-1] == (
        "New Contributors: none for 1.2.3 (no first-time author among its pull requests)"
    )


def test_contributors_explains_skipped_pull_requests(
    tmp_path: Path, github: GitHub, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    github(
        {
            "1": ("alice", "User", "2026-10-20T10:00:00Z"),
            "2": ("alice", "User", "2026-10-20T09:00:00Z"),
            "3": ("alice", "User", "2026-10-20T11:00:00Z"),
            "4": ("bob", "User", None),
            "5": ("dependabot", "Bot", "2026-10-20T12:00:00Z"),
            "6": ("claude", "User", "2026-10-20T13:00:00Z"),
        },
        set(),
    )

    _add(monkeypatch, _changelog(tmp_path, ["1", "2", "3", "4", "5", "6"]))

    assert capsys.readouterr().err.splitlines()[1:] == [
        "Skipped unmerged pull requests: #4",
        "Skipped pull requests by bots and AI assistants: #5 @dependabot (bot), #6 @claude (AI assistant)",
        "Counting each author's earliest pull request: @alice #2 (also #1, #3)",
        "New Contributors: @alice (#2)",
    ]
