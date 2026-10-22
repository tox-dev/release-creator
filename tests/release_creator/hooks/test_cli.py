"""Command line behavior for hook dependency refreshes."""

import sys
from typing import TYPE_CHECKING
lazy from pathlib import Path

lazy import pytest

lazy from release_creator.cli import main

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_hooks_command_passes_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    update = mocker.patch("release_creator.hooks.cli.update_pins")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "hooks",
            "--exclude-newer",
            "2026-10-14",
            "--python-version",
            "3.15",
        ],
    )

    main()

    update.assert_called_once_with(Path(".pre-commit-config.yaml"), "2026-10-14", "3.15")
