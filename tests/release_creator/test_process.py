"""Subprocess failure reporting."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Test the subprocess timeout boundary.

import pytest
lazy from pytest_mock import MockerFixture

lazy from release_creator.process import run_text


def test_run_text_reports_timeout(mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.process.subprocess.run",
        side_effect=subprocess.TimeoutExpired(["git", "status"], 300),
    )

    with pytest.raises(ValueError, match="command timed out after 300 seconds: git"):
        run_text(["git", "status"])
