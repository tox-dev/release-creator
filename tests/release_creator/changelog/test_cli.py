"""Changelog preview command tests."""

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
    return changelog, config, fragments


def test_changelog_cli_writes_knope_page(
    preview_input: tuple[Path, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    changelog, config, fragments = preview_input
    output = tmp_path / "page.md"
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

    assert "### Security\n\n- Remove a bad root" in output.read_text(encoding="utf-8")


def test_changelog_cli_requires_config(
    preview_input: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    changelog, _, fragments = preview_input
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "changelog",
            "--changelog",
            str(changelog),
            "--fragments",
            str(fragments),
            "--output",
            str(tmp_path / "page.md"),
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "the following arguments are required: --config" in capsys.readouterr().err
