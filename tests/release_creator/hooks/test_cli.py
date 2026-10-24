"""Command line behavior for hook dependency refreshes."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # CompletedProcess models the uv boundary.
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
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: format\n"
        "        language: python\n        additional_dependencies: [black==1]\n"
    )
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    resolve = mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "black==2\n", ""),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "hooks"],
    )

    main()

    assert "black==2" in config.read_text()
    command = resolve.call_args.args[0]
    assert command[command.index("--exclude-newer") + 1] == "7 days"
    assert command[command.index("--python-version") + 1] == "3.15"
