"""Merged pull request lookup tests."""

from __future__ import annotations

import json
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Mock the GitHub CLI process boundary.
from typing import cast
from unittest.mock import MagicMock, create_autospec

import pytest

from release_creator import process
from release_creator.fragments import pull_requests
from release_creator.fragments.pull_requests import PullRequest, PullRequestAuthor


def test_fragment_pull_requests_deduplicates_commits_and_reads_numbered_stems(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        [
            {
                "number": 42,
                "merge_commit_sha": "a" * 40,
                "user": {"login": "alice", "type": "User"},
            }
        ],
        {"number": 6, "user": {"login": "dependabot[bot]", "type": "Bot"}},
    ]
    run: MagicMock = cast(
        "MagicMock",
        create_autospec(
            process.subprocess.run,
            side_effect=[subprocess.CompletedProcess([], 0, json.dumps(response), "") for response in responses],
        ),
    )
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value="gh"))
    monkeypatch.setattr(process.subprocess, "run", run)

    result = pull_requests.fragment_pull_requests(
        "tox-dev/example",
        {"+first.feature.md": "a" * 40, "+second.doc.md": "a" * 40, "6.bugfix.md": "b" * 40},
        numbered_prs=True,
    )

    assert result == {
        "+first.feature.md": PullRequest(number="42", author=PullRequestAuthor(handle="alice", is_bot=False)),
        "+second.doc.md": PullRequest(number="42", author=PullRequestAuthor(handle="alice", is_bot=False)),
        "6.bugfix.md": PullRequest(number="6", author=PullRequestAuthor(handle="dependabot", is_bot=True)),
    }
    assert [call.args[0][2] for call in run.call_args_list] == [
        f"repos/tox-dev/example/commits/{'a' * 40}/pulls?per_page=100",
        "repos/tox-dev/example/pulls/6",
    ]


@pytest.mark.parametrize(
    ("response", "error", "message"),
    [
        pytest.param([], ValueError, "expected one merged pull request", id="no-pull"),
        pytest.param(
            [{"number": 42, "merge_commit_sha": "b" * 40}],
            ValueError,
            "expected one merged pull request",
            id="other-commit",
        ),
        pytest.param(
            [{"number": 42, "merge_commit_sha": "a" * 40}] * 2,
            ValueError,
            "expected one merged pull request",
            id="two-pulls",
        ),
        pytest.param({}, TypeError, "invalid pull request response", id="not-an-array"),
        pytest.param(
            [{"number": 42, "merge_commit_sha": "a" * 40}],
            TypeError,
            "invalid pull request response",
            id="missing-user",
        ),
        pytest.param(
            [{"number": 42, "merge_commit_sha": "a" * 40, "user": {"login": "alice", "type": "Mannequin"}}],
            ValueError,
            "invalid GitHub author",
            id="unknown-account-type",
        ),
        pytest.param(
            [{"number": 42, "merge_commit_sha": "a" * 40, "user": {"login": "bad handle", "type": "User"}}],
            ValueError,
            "invalid GitHub author",
            id="bad-handle",
        ),
        pytest.param(
            [{"number": 0, "merge_commit_sha": "a" * 40, "user": {"login": "alice", "type": "User"}}],
            ValueError,
            "invalid pull request number",
            id="bad-number",
        ),
        pytest.param(
            [{"number": True, "merge_commit_sha": "a" * 40, "user": {"login": "alice", "type": "User"}}],
            TypeError,
            "invalid pull request response",
            id="boolean-number",
        ),
    ],
)
def test_fragment_pull_requests_rejects_bad_responses(
    monkeypatch: pytest.MonkeyPatch, response: object, error: type[Exception], message: str
) -> None:
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value="gh"))
    monkeypatch.setattr(
        process.subprocess,
        "run",
        create_autospec(
            process.subprocess.run, return_value=subprocess.CompletedProcess([], 0, json.dumps(response), "")
        ),
    )

    with pytest.raises(error, match=message):
        pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40})


@pytest.mark.parametrize(
    ("stdout", "stderr", "status", "message"),
    [
        pytest.param("not json", "", 0, "invalid GitHub response", id="invalid-json"),
        pytest.param("", "API failed", 1, "API failed", id="api-failure"),
    ],
)
def test_fragment_pull_requests_reports_api_failures(
    monkeypatch: pytest.MonkeyPatch, stdout: str, stderr: str, status: int, message: str
) -> None:
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value="gh"))
    monkeypatch.setattr(
        process.subprocess,
        "run",
        create_autospec(process.subprocess.run, return_value=subprocess.CompletedProcess([], status, stdout, stderr)),
    )

    with pytest.raises(ValueError, match=message):
        pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40})


def test_fragment_pull_requests_requires_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value=None))

    with pytest.raises(FileNotFoundError, match="GitHub CLI is required"):
        pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40})


def test_fragment_pull_requests_checks_repository_before_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    lookup = create_autospec(pull_requests.shutil.which)
    monkeypatch.setattr(pull_requests.shutil, "which", lookup)

    with pytest.raises(ValueError, match="invalid repository"):
        pull_requests.fragment_pull_requests("bad", {"+news.feature.md": "a" * 40})

    lookup.assert_not_called()
