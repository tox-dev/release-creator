"""Command line behavior for hook dependency refreshes."""

import sys
from typing import TYPE_CHECKING

lazy import pytest

lazy from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_hooks_command_passes_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    update = mocker.patch("release_creator.hooks.cli.update_pins")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "hooks",
            "--config",
            str(config),
            "--exclude-newer",
            "2026-10-14",
            "--python-version",
            "3.15",
        ],
    )

    main()

    update.assert_called_once_with(config, "2026-10-14", "3.15")
