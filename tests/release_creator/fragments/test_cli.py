"""Staged fragment deletion checks."""

import sys
lazy from pathlib import Path

import pytest

lazy from release_creator.cli import main
lazy from release_creator.process import run_text


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.towncrier]\ndirectory = "changelog.d"\nfilename = "CHANGELOG.md"\n'
        'type = [{ directory = "feature", name = "Added", showcontent = true }]\n'
    )
    (tmp_path / "changelog.d").mkdir()
    for name in ("+a.feature.md", "+b.feature.rst", "+c.other.md", "README.md"):
        (tmp_path / "changelog.d" / name).write_text("Text.\n")
    (tmp_path / "docs.md").write_text("Text.\n")
    _git("init", "-q")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "-qm", "Init")
    monkeypatch.setattr(sys, "argv", ["release-creator", "validate-fragment-deletions"])
    return tmp_path


def _git(*arguments: str) -> None:
    result = run_text(["git", *arguments])
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "paths", [pytest.param(["changelog.d/+a.feature.md"], id="fragment"), pytest.param(["docs.md"], id="outside")]
)
@pytest.mark.usefixtures("repository")
def test_deletions_accept_consumed_fragments(paths: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    _git("rm", "-q", *paths)

    main()

    assert not capsys.readouterr().err


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("changelog.d/+b.feature.rst", id="extension"),
        pytest.param("changelog.d/+c.other.md", id="category"),
        pytest.param("changelog.d/README.md", id="not-a-fragment"),
    ],
)
@pytest.mark.usefixtures("repository")
def test_deletions_reject_other_paths(path: str, capsys: pytest.CaptureFixture[str]) -> None:
    _git("rm", "-q", path)

    with pytest.raises(SystemExit, match="2"):
        main()

    assert f"unsupported release fragment: {Path(path)}" in capsys.readouterr().err


def test_deletions_read_towncrier_toml(repository: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repository / "towncrier.toml").write_text('[tool.towncrier]\ndirectory = "changelog.d"\nfilename = "NEWS.rst"\n')
    _git("rm", "-q", "changelog.d/+a.feature.md")

    with pytest.raises(SystemExit, match="2"):
        main()

    assert f"unsupported release fragment: {Path('changelog.d/+a.feature.md')}" in capsys.readouterr().err


def test_deletions_require_towncrier_config(repository: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repository / "pyproject.toml").write_text("[project]\n")

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "missing [tool.towncrier] in pyproject.toml" in capsys.readouterr().err


def test_deletions_report_git_failure(repository: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repository / ".git" / "index").write_text("broken")

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "index" in capsys.readouterr().err


@pytest.mark.parametrize(
    "categories",
    [
        pytest.param("[tool.towncrier.fragment.feature]\n", id="fragment-table"),
        pytest.param("", id="towncrier-defaults"),
    ],
)
def test_deletions_read_configured_categories(
    repository: Path, categories: str, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / "pyproject.toml").write_text(
        f'[tool.towncrier]\ndirectory = "changelog.d"\nfilename = "CHANGELOG.md"\n{categories}'
    )
    _git("rm", "-q", "changelog.d/+a.feature.md")

    main()

    assert not capsys.readouterr().err
