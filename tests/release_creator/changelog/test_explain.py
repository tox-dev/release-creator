"""What the changelog command reports on stderr about its choices."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def preview_input(tmp_path: Path) -> tuple[Path, Path, Path]:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text('# Changelog\n\n<a name="release-1-0-0"></a>\n\n## 1.0.0\n', encoding="utf-8")
    config = tmp_path / "knope.toml"
    config.write_text('[package]\nextra_changelog_sections = [{ name = "Security", types = ["security"] }]\n')
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    (fragments / "security.md").write_text("---\ndefault: security\n---\n\n# Remove a bad root\n")
    (fragments / "fix.md").write_text("---\ndefault: patch\n---\n\n# Fix a bug\n")
    return changelog, config, fragments


def _render(monkeypatch: pytest.MonkeyPatch, changelog: Path, config: Path, fragments: Path, output: Path) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "changelog",
            "--config",
            str(config),
            "--changelog",
            str(changelog),
            "--fragments",
            str(fragments),
            "--output",
            str(output),
        ],
    )
    main()


def test_changelog_explains_on_stderr(
    preview_input: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    changelog, config, fragments = preview_input
    output = tmp_path / "page.md"

    _render(monkeypatch, changelog, config, fragments, output)

    assert capsys.readouterr().err == (
        f"Draft section: 2 changesets from {fragments} under 2 categories (Fixed, Security)\n"
        f"Wrote {output} from {changelog}\n"
    )


def test_changelog_keeps_stdout_empty(
    preview_input: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _render(monkeypatch, *preview_input, tmp_path / "page.md")

    assert not capsys.readouterr().out


def test_changelog_explains_missing_changesets(
    preview_input: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    changelog, config, _ = preview_input
    empty = tmp_path / "empty"
    empty.mkdir()

    _render(monkeypatch, changelog, config, empty, tmp_path / "page.md")

    assert capsys.readouterr().err.splitlines()[0] == f"Draft section: none (no pending changesets in {empty})"
