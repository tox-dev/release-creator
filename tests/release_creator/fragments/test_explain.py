"""What the fragments and validate-news commands report on stderr about their choices."""

from __future__ import annotations

import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Exercise Git and replace the GitHub CLI boundary.
import sys
lazy from pathlib import Path
lazy from typing import cast

import pytest
lazy from pytest_mock import MockerFixture

from release_creator import process
from release_creator.cli import main
from release_creator.process import run_text


def _commit(*paths: str, email: str = "test@example.com") -> str:
    git = shutil.which("git")
    assert git is not None
    assert run_text([git, "add", *paths]).returncode == 0
    assert run_text([git, "-c", f"user.email={email}", "commit", "-qm", "Change"]).returncode == 0
    return run_text([git, "rev-parse", "HEAD"]).stdout.strip()


def _github(mocker: MockerFixture, pulls: list[dict[str, object]]) -> None:
    response = {"data": {"repository": {"c0": {"associatedPullRequests": {"nodes": pulls}}}}}
    original_run = process.subprocess.run

    def execute(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[0] == "gh":
            return subprocess.CompletedProcess(command, 0, json.dumps(response), "")
        return original_run(
            command,
            cwd=cast("Path | None", kwargs["cwd"]),
            input=cast("str | None", kwargs["input"]),
            stdin=cast("int | None", kwargs["stdin"]),
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            timeout=300,
        )

    mocker.patch("release_creator.process.subprocess.run", autospec=True, side_effect=execute)


def _pull(commit: str, login: str) -> dict[str, object]:
    return {
        "number": 3,
        "mergedAt": "2026-10-22T00:00:00Z",
        "mergeCommit": {"oid": commit, "authors": {"nodes": []}},
        "author": {"login": login, "__typename": "User"},
    }


def _link(monkeypatch: pytest.MonkeyPatch, *options: str) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "fragments", "--repository", "tox-dev/example", *options])
    main()


@pytest.fixture
def fragment(git_repository: tuple[Path, str]) -> Path:
    directory = git_repository[0] / "changelog.d"
    directory.mkdir()
    path = directory / "+topic.feature.md"
    path.write_text("Add a feature.\n")
    return path


@pytest.fixture
def unrelated_history(git_repository: tuple[Path, str]) -> Path:
    (git_repository[0] / "README.md").write_text("Example.\n")
    _commit("README.md")
    return git_repository[0]


def test_fragments_explains_on_stderr(
    fragment: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _github(mocker, [_pull(_commit(str(fragment)), "alice")])

    _link(monkeypatch)

    assert capsys.readouterr().err == (
        "Fragment directory: changelog.d (default for towncrier)\n"
        "Linking 1 pending fragment in changelog.d to tox-dev/example pull requests\n"
        "Linked +topic.feature.md -> #3 (credit @alice)\n"
    )


def test_fragments_keeps_stdout_empty(
    fragment: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _github(mocker, [_pull(_commit(str(fragment)), "alice")])

    _link(monkeypatch)

    assert not capsys.readouterr().out


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            ("Add a feature (#3) by Alice.\n", "alice", "Kept +topic.feature.md: already links #3"),
            id="already-linked",
        ),
        pytest.param(
            (
                "Add a feature.\n",
                "claude",
                "Linked +topic.feature.md -> #3 (no credit: only AI assistants authored it)",
            ),
            id="ai-only",
        ),
    ],
)
def test_fragments_explains_pull_request_outcome(
    case: tuple[str, str, str],
    fragment: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    content, login, expected = case
    fragment.write_text(content, encoding="utf-8")
    _github(mocker, [_pull(_commit(str(fragment)), login)])

    _link(monkeypatch)

    assert capsys.readouterr().err.splitlines()[-1] == expected


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            ("test@example.com", "Credited +topic.feature.md to Test (commit {sha} has no merged pull request)"),
            id="author",
        ),
        pytest.param(
            (
                "noreply@anthropic.com",
                "Kept +topic.feature.md: commit {sha} has no merged pull request and an uncredited author",
            ),
            id="uncredited",
        ),
    ],
)
def test_fragments_explains_commit_fallback(
    case: tuple[str, str],
    fragment: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    email, expected = case
    sha = _commit(str(fragment), email=email)
    _github(mocker, [])

    _link(monkeypatch)

    assert capsys.readouterr().err.splitlines()[-1] == expected.format(sha=sha[:7])


@pytest.mark.usefixtures("unrelated_history")
def test_fragments_explains_uncommitted_fragment(
    fragment: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _link(monkeypatch, "--directory", str(fragment.parent))

    assert capsys.readouterr().err == (
        f"Fragment directory: {fragment.parent} (from --directory)\n"
        f"Linking 1 pending fragment in {fragment.parent} to tox-dev/example pull requests\n"
        "Kept +topic.feature.md: no introducing commit found\n"
    )


def test_fragments_explains_empty_directory(
    unrelated_history: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (unrelated_history / "changelog.d").mkdir()

    _link(monkeypatch)

    assert capsys.readouterr().err.splitlines()[-1] == "No pending fragments in changelog.d, nothing to link"


def test_fragments_explains_shallow_clone(
    git_repository: tuple[Path, str],
    fragment: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository, git = git_repository
    _commit(str(fragment))
    checkout = tmp_path_factory.mktemp("shallow")
    assert run_text([git, "clone", "-q", "--depth", "1", f"file://{repository}", str(checkout)]).returncode == 0
    monkeypatch.chdir(checkout)

    _link(monkeypatch)

    assert capsys.readouterr().err.splitlines() == [
        "Fragment directory: changelog.d (default for towncrier)",
        "Shallow clone: the history that added the fragments is cut off, so they stay unchanged",
    ]
