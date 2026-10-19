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
