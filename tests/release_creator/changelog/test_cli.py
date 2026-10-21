"""Changelog preview command."""

import sys
from typing import TYPE_CHECKING

import pytest

from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path


def test_changelog_cli_writes_package_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## example\n\n### 1.0.0\n", encoding="utf-8")
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    fragment = fragments / "+next.feature.md"
    fragment.write_text("Support Python 3.15.\n", encoding="utf-8")
    output = tmp_path / "page.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "changelog",
            "--format",
            "package",
            "--changelog",
            str(changelog),
            "--package",
            "example",
            "--fragments",
            str(fragments),
            "--output",
            str(output),
        ],
    )

    main()

    assert (
        '### Draft\n\n<a name="draft-example-added"></a>\n\n#### Added\n\n- Support Python 3.15.'
        in output.read_text(encoding="utf-8")
    )
    assert changelog.read_text(encoding="utf-8") == "# Changelog\n\n## example\n\n### 1.0.0\n"
    assert fragment.read_text(encoding="utf-8") == "Support Python 3.15.\n"


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param(["--format", "package"], "package format requires --package", id="package-without-name"),
        pytest.param(
            ["--format", "package", "--config", "config.toml", "--package", "example"],
            "package format requires --package",
            id="package-with-config",
        ),
        pytest.param(["--format", "knope"], "knope format requires --config", id="knope-without-config"),
        pytest.param(
            ["--format", "knope", "--config", "config.toml", "--package", "example"],
            "knope format requires --config",
            id="knope-with-package",
        ),
    ],
)
def test_changelog_cli_rejects_incompatible_options(
    options: list[str],
    expected: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "release-creator",
        "changelog",
        *options,
        "--changelog",
        str(tmp_path / "CHANGELOG.md"),
        "--fragments",
        str(tmp_path / "fragments"),
        "--output",
        str(tmp_path / "page.md"),
    ]
    monkeypatch.setattr(sys, "argv", args)

    with pytest.raises(SystemExit) as error:
        main()

    expected_usage_error = 2
    assert error.value.code == expected_usage_error
    assert expected in capsys.readouterr().err


def test_changelog_cli_rejects_source_output_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text("# Changelog\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "changelog",
            "--format",
            "package",
            "--package",
            "example",
            "--changelog",
            str(path),
            "--fragments",
            str(tmp_path / "fragments"),
            "--output",
            str(path),
        ],
    )

    with pytest.raises(SystemExit) as error:
        main()

    expected_usage_error = 2
    assert error.value.code == expected_usage_error
    assert "output must differ" in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == "# Changelog\n"


def test_changelog_cli_rejects_symlink_to_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text("# Changelog\n", encoding="utf-8")
    alias = tmp_path / "page.md"
    alias.symlink_to(path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "changelog",
            "--format",
            "package",
            "--package",
            "example",
            "--changelog",
            str(path),
            "--fragments",
            str(tmp_path / "fragments"),
            "--output",
            str(alias),
        ],
    )

    with pytest.raises(SystemExit) as error:
        main()

    expected_usage_error = 2
    assert error.value.code == expected_usage_error
    assert "output must differ" in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == "# Changelog\n"


def test_changelog_cli_writes_knope_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text('# Changelog\n\n<a name="release-1-0-0"></a>\n\n## 1.0.0\n', encoding="utf-8")
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[package]\nextra_changelog_sections = [{ name = "Security", types = ["security"] }]\n', encoding="utf-8"
    )
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    (fragments / "security.md").write_text("---\ndefault: security\n---\n\n# Remove a bad root\n", encoding="utf-8")
    output = tmp_path / "page.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "changelog",
            "--format",
            "knope",
            "--config",
            str(config_path),
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


def test_changelog_cli_rejects_missing_fragment_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## example\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "changelog",
            "--format",
            "package",
            "--package",
            "example",
            "--changelog",
            str(changelog),
            "--fragments",
            str(tmp_path / "missing"),
            "--output",
            str(tmp_path / "page.md"),
        ],
    )

    with pytest.raises(SystemExit) as error:
        main()

    expected_usage_error = 2
    assert error.value.code == expected_usage_error
    assert "fragment directory does not exist" in capsys.readouterr().err
