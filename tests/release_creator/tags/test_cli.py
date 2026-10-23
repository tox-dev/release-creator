"""Numeric tag command tests."""

import sys
from io import StringIO
from typing import TYPE_CHECKING

import pytest

lazy from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path


def test_tags_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "1.2.3"])
    main()


@pytest.mark.parametrize("extension", [pytest.param("md", id="markdown"), pytest.param("rst", id="rst")])
def test_tags_next(
    extension: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / f"+one.feature.{extension}").write_text("Add a feature.\n")
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "--next", "auto", "--directory", str(tmp_path)])
    monkeypatch.setattr(sys, "stdin", StringIO("0.1.0\njunk\n"))

    main()

    assert capsys.readouterr().out == "0.2.0\n"


def test_tags_next_accepts_numbered_fragment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "42.feature.md").write_text("Add a feature.\n")
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "--next", "auto", "--directory", str(tmp_path)])
    monkeypatch.setattr(sys, "stdin", StringIO("0.1.0\n"))

    main()

    assert capsys.readouterr().out == "0.2.0\n"


def test_tags_next_with_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "+one.feature.md").write_text("Add a feature.\n")
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "tags", "--next", "auto", "--prefix", "v", "--directory", str(tmp_path)],
    )
    monkeypatch.setattr(sys, "stdin", StringIO("1.0.3\nv1.1.0\nv1\n"))

    main()

    assert capsys.readouterr().out == "v1.2.0\n"


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(("pyproject-fmt", "2.30.3", "pyproject-fmt/2.30.4"), id="pyproject-fmt"),
        pytest.param(("tox-toml-fmt", "1.11.1", "tox-toml-fmt/1.11.2"), id="tox-toml-fmt"),
        pytest.param(("toml-fmt-common", "1.3.5", "toml-fmt-common/1.3.6"), id="common"),
    ],
)
def test_tags_next_scopes_package(
    case: tuple[str, str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package, latest, expected = case
    directory = tmp_path / "changelog.d" / package
    directory.mkdir(parents=True)
    (directory / "+fix.bugfix.md").write_text("Fix a bug.\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "--next", "auto", "--package", package])
    monkeypatch.setattr(
        sys,
        "stdin",
        StringIO(f"{package}/{latest}\nother-package/99.99.99\n1.0.0\n"),
    )

    main()

    assert capsys.readouterr().out == f"{expected}\n"


@pytest.mark.parametrize(
    "filename",
    [
        pytest.param("topic.feature.md", id="missing-plus"),
        pytest.param("+.feature.md", id="empty-name"),
        pytest.param("\N{ARABIC-INDIC DIGIT ONE}.feature.md", id="non-ascii-number"),
    ],
)
def test_tags_next_rejects_unsupported_fragment_name(
    filename: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / filename).write_text("Add a feature.\n")
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "--next", "auto", "--directory", str(tmp_path)])
    monkeypatch.setattr(sys, "stdin", StringIO("0.1.0\n"))

    with pytest.raises(SystemExit, match="2"):
        main()

    assert filename in capsys.readouterr().err


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        pytest.param(["tags"], "provide a tag or --next", id="missing"),
        pytest.param(["tags", "1.2.3", "--next", "auto"], "omit the tag", id="both"),
    ],
)
def test_tags_next_rejects_conflicting_input(
    arguments: list[str], message: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", *arguments])

    with pytest.raises(SystemExit, match="2"):
        main()

    assert message in capsys.readouterr().err


def test_tags_previous(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "1.2.3", "--previous"])
    monkeypatch.setattr(sys, "stdin", StringIO("1.0.0\n1.2.2\n1.2.3\n"))
    main()
    assert capsys.readouterr().out == "1.2.2\n"


@pytest.mark.parametrize("tag", [pytest.param("2.30.4", id="bare"), pytest.param("pyproject-fmt/2.30.4", id="full")])
def test_tags_previous_scopes_package(
    tag: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", tag, "--previous", "--package", "pyproject-fmt"])
    monkeypatch.setattr(
        sys,
        "stdin",
        StringIO("pyproject-fmt/2.30.2\npyproject-fmt/2.30.3\ntox-toml-fmt/99.0.0\n2.30.3\n"),
    )

    main()

    assert capsys.readouterr().out == "pyproject-fmt/2.30.3\n"


def test_tags_require_newer_scopes_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "tags", "tox-toml-fmt/1.11.2", "--require-newer", "--package", "tox-toml-fmt"],
    )
    monkeypatch.setattr(sys, "stdin", StringIO("tox-toml-fmt/1.11.1\npyproject-fmt/99.0.0\n"))

    main()


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        pytest.param(["tags", "1.0.0", "--package", "../other"], "invalid package name", id="package"),
        pytest.param(["tags", "1.0.0", "--package", ".."], "invalid package name", id="parent-directory"),
        pytest.param(
            ["tags", "other/1.0.0", "--package", "pyproject-fmt"],
            "does not belong to package",
            id="target-namespace",
        ),
    ],
)
def test_tags_rejects_invalid_package(
    arguments: list[str], message: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", *arguments])

    with pytest.raises(SystemExit, match="2"):
        main()

    assert message in capsys.readouterr().err


def test_tags_previous_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "1.2.3", "--previous"])
    monkeypatch.setattr(sys, "stdin", StringIO("1.2.3\n"))
    main()
    assert not capsys.readouterr().out


def test_tags_require_newer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "1.2.3", "--require-newer"])
    monkeypatch.setattr(sys, "stdin", StringIO("1.2.2\n"))
    main()


def test_tags_require_newer_rejects_existing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "1.2.3", "--require-newer"])
    monkeypatch.setattr(sys, "stdin", StringIO("1.2.3\n"))
    with pytest.raises(SystemExit, match="2"):
        main()
    assert "must be newer" in capsys.readouterr().err
