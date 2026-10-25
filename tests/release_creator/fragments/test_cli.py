"""Fragment command tests against a Git checkout."""

from __future__ import annotations

import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Exercise Git and replace the GitHub CLI boundary.
import sys
lazy from pathlib import Path
lazy from typing import cast
lazy from unittest.mock import MagicMock

import pytest
lazy from pytest_mock import MockerFixture

from release_creator import process
from release_creator.cli import main
from release_creator.process import run_text


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            (
                "+topic.feature.md",
                "Add a feature.\n",
                "towncrier",
                "Add a feature ([#3](https://github.com/tox-dev/example/pull/3)) by [@alice](https://github.com/alice).\n",
            ),
            id="towncrier",
        ),
        pytest.param(
            (
                "trust-roots.md",
                "---\ndefault: security\n---\n\n# Remove a distrusted root\n",
                "knope",
                (
                    "---\ndefault: security\n---\n\n# Remove a distrusted root "
                    "([#3](https://github.com/tox-dev/example/pull/3)) by [@alice](https://github.com/alice)\n"
                ),
            ),
            id="knope",
        ),
    ],
)
def test_fragments_cli_links_merged_pull_request(
    git_repository: tuple[Path, str],
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    case: tuple[str, str, str, str],
) -> None:
    name, content, format_name, expected = case
    checkout, git = git_repository
    directory = checkout / (".changeset" if format_name == "knope" else "changelog.d")
    directory.mkdir()
    fragment = directory / name
    fragment.write_text(content)
    assert run_text([git, "add", str(directory)]).returncode == 0
    assert run_text([git, "commit", "-qm", "A subject without a PR number"]).returncode == 0
    commit = run_text([git, "rev-parse", "HEAD"]).stdout.strip()
    query = _mock_github_pull(mocker, commit)
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "fragments", "--format", format_name, "--repository", "tox-dev/example"],
    )

    main()

    assert fragment.read_text() == expected
    assert "c0: object" in next(call.kwargs["input"] for call in query.call_args_list if call.args[0][0] == "gh")


def _mock_github_pull(mocker: MockerFixture, commit: str) -> MagicMock:
    response = {
        "data": {
            "repository": {
                "c0": {
                    "associatedPullRequests": {
                        "nodes": [
                            {
                                "number": 3,
                                "mergedAt": "2026-10-22T00:00:00Z",
                                "mergeCommit": {"oid": commit, "authors": {"nodes": []}},
                                "author": {"login": "alice", "__typename": "User"},
                            }
                        ]
                    }
                }
            }
        }
    }
    original_run = process.subprocess.run
    original_which = shutil.which

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

    mocker.patch(
        "release_creator.process.shutil.which",
        autospec=True,
        side_effect=lambda name: "gh" if name == "gh" else original_which(name),
    )
    return cast("MagicMock", mocker.patch("release_creator.process.subprocess.run", autospec=True, side_effect=execute))


def test_fragments_cli_rejects_unsupported_name(
    git_repository: tuple[Path, str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = git_repository[0] / "changelog.d"
    directory.mkdir()
    (directory / "topic.feature.md").write_text("Add a feature.\n")
    monkeypatch.setattr(sys, "argv", ["release-creator", "fragments", "--repository", "tox-dev/example"])

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "unsupported changelog fragment name" in capsys.readouterr().err


def test_fragments_cli_reports_missing_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "+topic.feature.md").write_text("Add a feature.\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["release-creator", "fragments", "--repository", "tox-dev/example"])

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "not a git repository" in capsys.readouterr().err
