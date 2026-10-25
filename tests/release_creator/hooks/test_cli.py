"""Command line behavior for hook dependency pins."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # CompletedProcess models the uv boundary.
import sys
from typing import TYPE_CHECKING, cast
lazy from pathlib import Path

import pytest

lazy from release_creator.cli import main

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (config := tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: lint\n        language: python\n"
        "        additional_dependencies: [packaging==24.1]\n",
        encoding="utf-8",
    )
    return config


@pytest.fixture
def uv(mocker: MockerFixture) -> MagicMock:
    return cast(
        "MagicMock",
        mocker.patch(
            "release_creator.process.subprocess.run",
            autospec=True,
            return_value=subprocess.CompletedProcess([], 0, "packaging==24.2\n", ""),
        ),
    )


@pytest.mark.parametrize(
    ("arguments", "cutoff"),
    [pytest.param([], "7 days", id="default"), pytest.param(["--minimum-days", "9"], "9 days", id="longer")],
)
def test_hooks_updates_pins_with_cutoff(
    config: Path, uv: MagicMock, monkeypatch: pytest.MonkeyPatch, arguments: list[str], cutoff: str
) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", *arguments])

    main()

    command = uv.call_args.args[0]
    assert (
        config.read_text(encoding="utf-8").count("packaging==24.2"),
        command[command.index("--exclude-newer") + 1],
    ) == (
        1,
        cutoff,
    )


@pytest.mark.usefixtures("config")
def test_hooks_check_reports_stale_pins(
    uv: MagicMock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--check"])

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "hook dependency pins do not match the resolved closure: lint" in capsys.readouterr().err
    assert uv.call_count == 1


@pytest.mark.usefixtures("config")
def test_hooks_rejects_short_minimum_days(
    uv: MagicMock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--minimum-days", "6"])

    with pytest.raises(SystemExit, match="2"):
        main()

    assert ("minimum hook dependency age must be at least seven days" in capsys.readouterr().err, uv.call_count) == (
        True,
        0,
    )
