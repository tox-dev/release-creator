"""Subprocess failure reporting."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Test the subprocess timeout boundary.
from typing import Final

import pytest
lazy from pytest_mock import MockerFixture

lazy from release_creator.process import run_text


def test_run_text_reports_timeout(mocker: MockerFixture) -> None:
    timeout: Final = 300
    execute = mocker.patch(
        "release_creator.process.subprocess.run",
        side_effect=subprocess.TimeoutExpired(["git", "status"], timeout),
    )

    with pytest.raises(ValueError, match="command timed out after 300 seconds: git status"):
        run_text(["git", "status"])
    assert execute.call_args.kwargs["timeout"] == timeout
