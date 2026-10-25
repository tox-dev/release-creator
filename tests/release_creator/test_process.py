"""Subprocess failure reporting."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Test the subprocess timeout boundary.
from typing import Final

import pytest
lazy from pytest_mock import MockerFixture

lazy from release_creator.process import isolated_uv_env, run_text


def test_run_text_reports_timeout(mocker: MockerFixture) -> None:
    timeout: Final = 300
    execute = mocker.patch(
        "release_creator.process.subprocess.run",
        side_effect=subprocess.TimeoutExpired(["git", "status"], timeout),
    )

    with pytest.raises(ValueError, match="command timed out after 300 seconds: git status"):
        run_text(["git", "status"])
    assert execute.call_args.kwargs["timeout"] == timeout
    assert execute.call_args.kwargs["stdin"] == subprocess.DEVNULL


def test_run_text_sends_input_to_child(mocker: MockerFixture) -> None:
    execute = mocker.patch(
        "release_creator.process.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, "", ""),
    )

    run_text(["gh", "api", "graphql"], stdin="query")

    assert execute.call_args.kwargs["input"] == "query"
    assert execute.call_args.kwargs["stdin"] is None


def test_isolated_uv_env_drops_resolver_and_trust_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "UV_INDEX_URL",
        "UV_NO_CONFIG",
        "PIP_INDEX_URL",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "SSL_CLIENT_CERT",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
    ):
        monkeypatch.setenv(name, "https://evil.invalid/")
    monkeypatch.setenv("RELEASE_CREATOR_KEPT", "1")

    environment = isolated_uv_env()

    assert "evil.invalid" not in "".join(environment.values())
    assert environment["RELEASE_CREATOR_KEPT"] == "1"
