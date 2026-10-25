"""Fragment origin tests against real Git history."""

from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Model a failed Git history command.
lazy from pathlib import Path

import pytest
lazy from pytest_mock import MockerFixture

from release_creator.fragments import git as fragment_git
from release_creator.process import run_text


def test_fragment_commits_from_git_reads_multiple_origins(git_repository: tuple[Path, str]) -> None:
    tmp_path, git = git_repository
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    for name in ("+first.feature.md", "+also.doc.md"):
        (directory / name).write_text("First release change.\n")
    assert run_text([git, "-C", str(tmp_path), "add", "changelog.d"]).returncode == 0
    assert run_text([git, "-C", str(tmp_path), "commit", "-qm", "First release change"]).returncode == 0
    first = run_text([git, "-C", str(tmp_path), "rev-parse", "HEAD"]).stdout.strip()
    (directory / "+second.bugfix.md").write_text("Second release change.\n")
    assert run_text([git, "-C", str(tmp_path), "add", "changelog.d"]).returncode == 0
    assert run_text([git, "-C", str(tmp_path), "commit", "-qm", "Second release change"]).returncode == 0
    second = run_text([git, "-C", str(tmp_path), "rev-parse", "HEAD"]).stdout.strip()
    assert fragment_git.fragment_commits_from_git(directory) == {
        "+first.feature.md": first,
        "+also.doc.md": first,
        "+second.bugfix.md": second,
    }


def test_fragment_commits_from_git_reads_unicode_name(git_repository: tuple[Path, str]) -> None:
    repository, git = git_repository
    directory = repository / "changelog.d"
    directory.mkdir()
    (directory / "+café.feature.md").write_text("News.\n")
    assert run_text([git, "-C", str(repository), "add", "changelog.d"]).returncode == 0
    assert run_text([git, "-C", str(repository), "commit", "-qm", "News"]).returncode == 0

    assert fragment_git.fragment_commits_from_git(directory) == {
        "+café.feature.md": run_text([git, "-C", str(repository), "rev-parse", "HEAD"]).stdout.strip()
    }


def test_fragment_commits_from_git_follows_rename(git_repository: tuple[Path, str]) -> None:
    repository, git = git_repository
    directory = repository / "changelog.d"
    directory.mkdir()
    (directory / "+first.feature.md").write_text("News.\n")
    (directory / "+other.doc.md").write_text("Documentation.\n")
    assert run_text([git, "-C", str(repository), "add", "changelog.d"]).returncode == 0
    assert run_text([git, "-C", str(repository), "commit", "-qm", "Origin"]).returncode == 0
    original = run_text([git, "-C", str(repository), "rev-parse", "HEAD"]).stdout.strip()
    assert (
        run_text([
            git,
            "-C",
            str(repository),
            "mv",
            "changelog.d/+first.feature.md",
            "changelog.d/+renamed.feature.md",
        ]).returncode
        == 0
    )
    assert run_text([git, "-C", str(repository), "commit", "-qm", "Rename"]).returncode == 0
    (directory / "+renamed.feature.md").write_text("Updated news.\n")
    assert run_text([git, "-C", str(repository), "add", "changelog.d"]).returncode == 0
    assert run_text([git, "-C", str(repository), "commit", "-qm", "Edit"]).returncode == 0

    assert fragment_git.fragment_commits_from_git(directory) == {
        "+renamed.feature.md": original,
        "+other.doc.md": original,
    }


def test_fragment_commits_from_git_ignores_nested_same_name(git_repository: tuple[Path, str]) -> None:
    repository, git = git_repository
    directory = repository / "changelog.d"
    directory.mkdir()
    (directory / "+same.feature.md").write_text("Live news.\n")
    assert run_text([git, "-C", str(repository), "add", "changelog.d"]).returncode == 0
    assert run_text([git, "-C", str(repository), "commit", "-qm", "Live news"]).returncode == 0
    original = run_text([git, "-C", str(repository), "rev-parse", "HEAD"]).stdout.strip()
    (directory / "archive").mkdir()
    (directory / "archive" / "+same.feature.md").write_text("Archived news.\n")
    assert run_text([git, "-C", str(repository), "add", "changelog.d"]).returncode == 0
    assert run_text([git, "-C", str(repository), "commit", "-qm", "Archived news"]).returncode == 0

    assert fragment_git.fragment_commits_from_git(directory) == {"+same.feature.md": original}


def test_fragment_commits_from_git_rejects_uncommitted_fragment(git_repository: tuple[Path, str]) -> None:
    tmp_path, git = git_repository
    (tmp_path / "README.md").write_text("Project.\n", encoding="utf-8")
    assert run_text([git, "-C", str(tmp_path), "add", "README.md"]).returncode == 0
    assert run_text([git, "-C", str(tmp_path), "commit", "-qm", "Initial"]).returncode == 0
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "+news.feature.md").write_text("News.\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"no introducing Git commit for \+news.feature.md"):
        fragment_git.fragment_commits_from_git(directory)


def test_fragment_commits_from_git_reports_missing_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "+news.feature.md").write_text("News.\n")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="not a git repository"):
        fragment_git.fragment_commits_from_git(directory)


def test_fragment_commits_from_git_reports_missing_git(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch("release_creator.process.shutil.which", return_value=None)

    with pytest.raises(FileNotFoundError, match="git is required"):
        fragment_git.fragment_commits_from_git(tmp_path / "changelog.d")


def test_fragment_commits_from_git_reports_log_failure(tmp_path: Path, mocker: MockerFixture) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "+news.feature.md").write_text("News.\n", encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="git")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        side_effect=[
            subprocess.CompletedProcess([], 0, "false\n", ""),
            subprocess.CompletedProcess([], 1, "", "history unavailable"),
        ],
    )

    with pytest.raises(ValueError, match="history unavailable"):
        fragment_git.fragment_commits_from_git(directory)


def test_fragment_commits_from_git_rejects_shallow_clone(
    git_repository: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, git = git_repository
    directory = repository / "changelog.d"
    directory.mkdir()
    (directory / "+news.feature.md").write_text("News.\n", encoding="utf-8")
    assert run_text([git, "-C", str(repository), "add", "."]).returncode == 0
    assert run_text([git, "-C", str(repository), "commit", "-qm", "News"]).returncode == 0
    checkout = tmp_path / "shallow"
    assert run_text([git, "clone", "--depth", "1", f"file://{repository}", str(checkout)]).returncode == 0
    monkeypatch.chdir(checkout)

    with pytest.raises(ValueError, match="full Git history is required"):
        fragment_git.fragment_commits_from_git(Path("changelog.d"))
