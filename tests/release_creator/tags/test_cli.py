"""Numeric tag command tests."""

import sys
from io import StringIO
from typing import TYPE_CHECKING

import pytest

lazy from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path


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
        StringIO(f"{package}/{latest}\nother-package/99.99.99\n99.0.0\n"),
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
def test_tags_next_bumps_patch_for_unsupported_fragment_name(
    filename: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / filename).write_text("Add a feature.\n")
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "--next", "auto", "--directory", str(tmp_path)])
    monkeypatch.setattr(sys, "stdin", StringIO("0.1.0\n"))

    main()

    assert capsys.readouterr().out == "0.1.1\n"


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
        StringIO("pyproject-fmt/2.30.2\npyproject-fmt/2.30.3\ntox-toml-fmt/99.0.0\n2.30.4rc1\n"),
    )

    main()

    assert capsys.readouterr().out == "pyproject-fmt/2.30.3\n"


def test_tags_previous_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "tags", "1.2.3", "--previous"])
    monkeypatch.setattr(sys, "stdin", StringIO("1.2.3\n"))
    main()
    assert not capsys.readouterr().out
