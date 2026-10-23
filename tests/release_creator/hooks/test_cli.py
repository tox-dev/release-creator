"""Command line behavior for hook dependency refreshes."""

import sys
from typing import TYPE_CHECKING
lazy from pathlib import Path

lazy import pytest

lazy from release_creator.cli import main

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_hooks_command_uses_reviewed_cutoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    update = mocker.patch("release_creator.hooks.cli.update_pins")
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "hooks"],
    )

    main()

    update.assert_called_once_with(Path(".pre-commit-config.yaml"), "7 days", "3.15")
