"""Fragment command tests."""

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Test the fragment command against real Git history.
import sys
from typing import TYPE_CHECKING
from unittest.mock import create_autospec

import pytest

from release_creator.cli import main
from release_creator.fragments import cli as fragments_cli
from release_creator.fragments.pull_requests import PullRequestAuthor

if TYPE_CHECKING:
    from pathlib import Path


def test_fragments_cli_links_squash_pull_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    fragment = directory / "+topic.feature.md"
    fragment.write_text("Add a feature.\n")
    commits = tmp_path / "commits.tsv"
    commits.write_text("+topic.feature.md\tAdd a feature (#3)\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "fragments", "--repository", "tox-dev/example", "--commit-map", str(commits)],
    )

    main()

    assert fragment.read_text() == "Add a feature ([#3](https://github.com/tox-dev/example/pull/3)).\n"


def test_fragments_cli_links_knope_changeset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / ".changeset"
    directory.mkdir()
    fragment = directory / "trust-roots.md"
    fragment.write_text("---\ndefault: security\n---\n\n# Remove a distrusted root certificate\n")
    commits = tmp_path / "commits.tsv"
    commits.write_text("trust-roots.md\tPatch trust roots (#2377)\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "fragments",
            "--format",
            "knope",
            "--repository",
            "tox-dev/peryx",
            "--commit-map",
            str(commits),
        ],
    )

    main()

    assert fragment.read_text() == (
        "---\ndefault: security\n---\n\n"
        "# Remove a distrusted root certificate ([#2377](https://github.com/tox-dev/peryx/pull/2377))\n"
    )


def test_fragments_cli_rejects_unsupported_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    fragment = directory / "topic.feature.md"
    fragment.write_text("Add a feature.\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "fragments", "--repository", "tox-dev/example", "--commit-map", "missing.tsv"],
    )

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "unsupported changelog fragment name" in capsys.readouterr().err
    assert fragment.read_text() == "Add a feature.\n"


def test_fragments_cli_resolves_authors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    fragment = directory / "+topic.feature.md"
    fragment.write_text("Add a feature.\n")
    commits = tmp_path / "commits.tsv"
    commits.write_text("+topic.feature.md\tAdd a feature (#3)\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "fragments",
            "--repository",
            "tox-dev/example",
            "--commit-map",
            str(commits),
            "--resolve-authors",
        ],
    )
    resolve = create_autospec(
        fragments_cli.pull_request_authors,
        return_value={"3": PullRequestAuthor(handle="alice", is_bot=False)},
    )
    monkeypatch.setattr(fragments_cli, "pull_request_authors", resolve)

    main()

    assert fragment.read_text() == (
        "Add a feature ([#3](https://github.com/tox-dev/example/pull/3)) by [@alice](https://github.com/alice).\n"
    )
    resolve.assert_called_once_with("tox-dev/example", {"+topic.feature.md": "Add a feature (#3)"})


def test_fragments_cli_resolves_numbered_issue_author(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    fragment = directory / "3.feature.md"
    fragment.write_text("Add a feature.\n")
    commits = tmp_path / "commits.tsv"
    commits.write_text("3.feature.md\tAdd a feature (#4)\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "fragments",
            "--repository",
            "tox-dev/example",
            "--commit-map",
            str(commits),
            "--resolve-authors",
        ],
    )
    resolve = create_autospec(
        fragments_cli.pull_request_authors,
        return_value={"4": PullRequestAuthor(handle="alice", is_bot=False)},
    )
    monkeypatch.setattr(fragments_cli, "pull_request_authors", resolve)

    main()

    assert fragment.read_text() == (
        "Add a feature ([#4](https://github.com/tox-dev/example/pull/4)) by [@alice](https://github.com/alice).\n"
    )
    resolve.assert_called_once_with("tox-dev/example", {"3.feature.md": "Add a feature (#4)"})


def test_fragments_cli_reports_missing_commit_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "+topic.feature.md").write_text("Add a feature.\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "fragments", "--repository", "tox-dev/example", "--commit-map", "missing.tsv"],
    )

    with pytest.raises(SystemExit) as error:
        main()

    expected_usage_error = 2
    assert error.value.code == expected_usage_error
    assert "missing.tsv" in capsys.readouterr().err


def test_fragments_cli_reads_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    fragment = directory / "+topic.feature.md"
    fragment.write_text("Add a feature.\n")
    numbered = directory / "3.doc.md"
    numbered.write_text("Document a feature by a contributor.\n")
    git = shutil.which("git")
    assert git is not None
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Git fixture.
        [git, "init", "-q", str(tmp_path)],
        check=True,
    )
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Git fixture.
        [git, "-C", str(tmp_path), "add", "changelog.d"],
        check=True,
    )
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Git fixture.
        [
            git,
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "Add a feature (#3)",
        ],
        check=True,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["release-creator", "fragments", "--repository", "tox-dev/example", "--git"])

    main()

    assert fragment.read_text() == "Add a feature ([#3](https://github.com/tox-dev/example/pull/3)).\n"
    assert (
        numbered.read_text()
        == "Document a feature by a contributor ([#3](https://github.com/tox-dev/example/pull/3)).\n"
    )


def test_fragments_cli_reports_git_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "+topic.feature.md").write_text("Add a feature.\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["release-creator", "fragments", "--repository", "tox-dev/example", "--git"])

    with pytest.raises(SystemExit) as error:
        main()

    expected_usage_error = 2
    assert error.value.code == expected_usage_error
    assert "not a git repository" in capsys.readouterr().err


def test_fragments_cli_reports_missing_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "+topic.feature.md").write_text("Add a feature.\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["release-creator", "fragments", "--repository", "tox-dev/example", "--git"])

    with pytest.raises(SystemExit) as error:
        main()

    expected_usage_error = 2
    assert error.value.code == expected_usage_error
    assert "Git is required" in capsys.readouterr().err
