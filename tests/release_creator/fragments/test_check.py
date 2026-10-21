"""Check pull request news against real Git history."""

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Exercise the public command in a real repository.
import sys
lazy from pathlib import Path

import pytest
lazy from pytest_mock import MockerFixture

from release_creator.cli import main
from release_creator.fragments.check import changed_changesets, changed_fragments


def _git(*args: str) -> None:
    git = shutil.which("git")
    assert git is not None
    subprocess.run([git, *args], check=True)  # ruff: ignore[subprocess-without-shell-equals-true]  # Git fixture.


@pytest.fixture
def news_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.towncrier]\ndirectory = "changelog.d"\nfilename = "CHANGELOG.md"\n'
        'type = [{ directory = "feature", name = "Added" }]\n',
        encoding="utf-8",
    )
    _git("init", "-qb", "main", str(tmp_path))
    _git("-C", str(tmp_path), "add", ".")
    _git("-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Initial")
    _git("-C", str(tmp_path), "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    ("filename", "content", "count", "error"),
    [
        pytest.param("+topic.feature.md", "Add a feature.\n", 1, "", id="named"),
        pytest.param("42.feature.md", "Add a feature.\n", 1, "", id="numbered"),
        pytest.param("+topic.feature.1.md", "Add a feature.\n", 1, "", id="multiple-entries"),
        pytest.param("+topic.doc.md", "Add a feature.\n", 0, "unsupported changelog fragment", id="category"),
        pytest.param("topic.feature.md", "Add a feature.\n", 0, "unsupported changelog fragment", id="name"),
        pytest.param("+topic.feature.md", " \n", 0, "empty changelog fragment", id="empty"),
        pytest.param("README.md", "Read me.\n", 0, "", id="outside-directory"),
        pytest.param("+.md", "Uncategorized.\n", 0, "", id="incomplete-name"),
        pytest.param("+topic.feature.rst", "Add a feature.\n", 0, "", id="wrong-extension"),
    ],
)
def test_changed_fragments(news_repository: Path, filename: str, content: str, count: int, error: str) -> None:
    destination = news_repository / (filename if filename == "README.md" else f"changelog.d/{filename}")
    destination.write_text(content, encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    if error:
        with pytest.raises(ValueError, match=error):
            changed_fragments(news_repository / "pyproject.toml", "main")
    else:
        assert changed_fragments(news_repository / "pyproject.toml", "main") == count


@pytest.mark.parametrize(
    ("base", "filename"),
    [
        pytest.param("", "CHANGELOG.md", id="missing-base"),
        pytest.param("main", "CHANGELOG.txt", id="unsupported-format"),
    ],
)
def test_changed_fragments_rejects_invalid_context(news_repository: Path, base: str, filename: str) -> None:
    config = news_repository / "pyproject.toml"
    config.write_text(config.read_text(encoding="utf-8").replace("CHANGELOG.md", filename), encoding="utf-8")

    with pytest.raises(ValueError, match="news validation needs a PR base"):
        changed_fragments(config, base)


def test_changed_fragments_requires_git(news_repository: Path, mocker: MockerFixture) -> None:
    mocker.patch("release_creator.fragments.check.shutil.which", return_value=None)

    with pytest.raises(FileNotFoundError, match="Git is required"):
        changed_fragments(news_repository / "pyproject.toml", "main")


def test_changed_fragments_rejects_missing_base(news_repository: Path) -> None:
    with pytest.raises(ValueError, match="bad revision"):
        changed_fragments(news_repository / "pyproject.toml", "missing")


def test_validate_news_cli_reports_count(
    news_repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (news_repository / "changelog.d" / "+topic.feature.md").write_text("Add a feature.\n", encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")
    monkeypatch.setattr(sys, "argv", ["release-creator", "validate-news", "--base", "main"])

    main()

    assert capsys.readouterr().out == "1\n"


@pytest.mark.parametrize(
    ("content", "count", "error"),
    [
        pytest.param("---\ndefault: security\n---\n\n# Remove a distrusted root\n", 1, "", id="custom-type"),
        pytest.param("---\ndefault: patch\n---\n\n# Fix a bug\n", 1, "", id="built-in-type"),
        pytest.param("---\ndefault: unknown\n---\n\n# Fix a bug\n", 0, "unsupported changeset type", id="type"),
        pytest.param("---\n---\n\n# Fix a bug\n", 0, "empty changeset front matter", id="empty-front-matter"),
        pytest.param("---\ndefault: patch\n---\n\n# \n", 0, "empty changeset summary", id="empty-summary"),
        pytest.param("Fix a bug\n", 0, "missing YAML front matter", id="missing-front-matter"),
    ],
)
def test_changed_changesets(news_repository: Path, content: str, count: int, error: str) -> None:
    (news_repository / ".changeset").mkdir()
    (news_repository / "knope.toml").write_text(
        '[package]\nextra_changelog_sections = [{ name = "Security", types = ["security"] }]\n',
        encoding="utf-8",
    )
    (news_repository / ".changeset" / "trust-roots.md").write_text(content, encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    if error:
        with pytest.raises(ValueError, match=error):
            changed_changesets(news_repository / "knope.toml", "main")
    else:
        assert changed_changesets(news_repository / "knope.toml", "main") == count


def test_validate_news_cli_reports_knope_count(
    news_repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (news_repository / ".changeset").mkdir()
    (news_repository / "knope.toml").write_text("[package]\n", encoding="utf-8")
    (news_repository / ".changeset" / "fix.md").write_text("---\ndefault: patch\n---\n\n# Fix a bug\n")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")
    monkeypatch.setattr(sys, "argv", ["release-creator", "validate-news", "--format", "knope", "--base", "main"])

    main()

    assert capsys.readouterr().out == "1\n"


def test_changed_changesets_requires_base(news_repository: Path) -> None:
    with pytest.raises(ValueError, match="news validation needs a PR base"):
        changed_changesets(news_repository / "knope.toml", "")


def test_changed_changesets_skips_directory_guide(news_repository: Path) -> None:
    (news_repository / ".changeset").mkdir()
    (news_repository / "knope.toml").write_text("[package]\n", encoding="utf-8")
    (news_repository / ".changeset" / "README.md").write_text("Changeset guide.\n")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    assert changed_changesets(news_repository / "knope.toml", "main") == 0
