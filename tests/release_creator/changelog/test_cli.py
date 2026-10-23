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


def test_changelog_cli_writes_package_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        '# Changelog\n\n## pyproject-fmt\n\n### 2.30.3\n\n<a name="release-pyproject-fmt-2-30-3"></a>\n\n'
        "## tox-toml-fmt\n\n### 1.11.1\n",
        encoding="utf-8",
    )
    fragments = tmp_path / "changelog.d" / "pyproject-fmt"
    fragments.mkdir(parents=True)
    (fragments / "+next.feature.md").write_text("Support Python 3.15.\n", encoding="utf-8")
    output = tmp_path / "page.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "changelog",
            "--format",
            "package",
            "--package",
            "pyproject-fmt",
            "--changelog",
            str(changelog),
            "--fragments",
            str(fragments),
            "--output",
            str(output),
        ],
    )

    main()

    assert output.read_text(encoding="utf-8") == (
        '# Changelog\n\n## pyproject-fmt\n\n<a name="draft-pyproject-fmt"></a>\n\n### Draft\n\n'
        '<a name="draft-pyproject-fmt-added"></a>\n\n#### Added\n\n- Support Python 3.15.\n\n'
        '### 2.30.3\n\n<a name="release-pyproject-fmt-2-30-3"></a>\n'
    )


@pytest.mark.parametrize(
    "case",
    [
        pytest.param((["--format", "package"], "package format requires --package"), id="package-without-name"),
        pytest.param(
            (
                ["--format", "package", "--package", "example", "--config", "config.toml"],
                "package format requires --package",
            ),
            id="package-with-config",
        ),
        pytest.param((["--package", "example"], "knope format requires --config"), id="knope-with-package"),
    ],
)
def test_changelog_cli_rejects_mismatched_options(
    preview_input: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case: tuple[list[str], str],
) -> None:
    options, error = case
    changelog, _, fragments = preview_input
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "changelog",
            *options,
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

    assert error in capsys.readouterr().err


@pytest.mark.parametrize("alias", [False, True], ids=["same-path", "symlink"])
def test_changelog_cli_rejects_source_output_alias(
    preview_input: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    alias: bool,
) -> None:
    changelog, config, fragments = preview_input
    output = tmp_path / "page.md" if alias else changelog
    if alias:
        output.symlink_to(changelog)
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

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "output must differ" in capsys.readouterr().err


def test_changelog_cli_rejects_missing_fragment_directory(
    preview_input: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    changelog, config, _ = preview_input
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
            str(tmp_path / "missing"),
            "--output",
            str(tmp_path / "page.md"),
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "fragment directory does not exist" in capsys.readouterr().err
