"""Pull request metadata tests."""

from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Mock the GitHub CLI process boundary.
from typing import cast
from unittest.mock import MagicMock, call, create_autospec

import pytest

from release_creator.fragments import pull_requests
from release_creator.fragments.pull_requests import PullRequestAuthor


@pytest.mark.parametrize(
    ("subject", "expected", "error"),
    [
        pytest.param("Improve output (#42)", "42", None, id="number"),
        pytest.param("Improve output (fixes #42)", None, "no squash pull request number", id="no-squash-marker"),
    ],
)
def test_pull_request_number(subject: str, expected: str | None, error: str | None) -> None:
    if error is None:
        assert pull_requests.pull_request_number(subject) == expected
    else:
        with pytest.raises(ValueError, match=error):
            pull_requests.pull_request_number(subject)


def test_pull_request_authors_deduplicates_numbers_and_skips_bots(monkeypatch: pytest.MonkeyPatch) -> None:
    gh_lookup = create_autospec(pull_requests.shutil.which, return_value="/usr/bin/gh")
    run: MagicMock = cast(
        "MagicMock",
        create_autospec(
            pull_requests.subprocess.run,
            side_effect=[
                subprocess.CompletedProcess([], 0, "alice\tUser\n", ""),
                subprocess.CompletedProcess([], 0, "dependabot[bot]\tBot\n", ""),
            ],
        ),
    )
    monkeypatch.setattr(pull_requests.shutil, "which", gh_lookup)
    monkeypatch.setattr(pull_requests.subprocess, "run", run)

    authors = pull_requests.pull_request_authors(
        "tox-dev/example",
        {
            "+first.feature.md": "First change (#42)",
            "+second.feature.md": "Second change (#42)",
            "+bot.doc.md": "Bot change (#43)",
        },
    )

    assert authors == {
        "42": PullRequestAuthor(handle="alice", is_bot=False),
        "43": PullRequestAuthor(handle="dependabot", is_bot=True),
    }
    assert run.call_args_list == [
        call(
            [
                "/usr/bin/gh",
                "api",
                "repos/tox-dev/example/pulls/42",
                "--jq",
                '.user | [(.login // ""), (.type // "")] | @tsv',
            ],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
        ),
        call(
            [
                "/usr/bin/gh",
                "api",
                "repos/tox-dev/example/pulls/43",
                "--jq",
                '.user | [(.login // ""), (.type // "")] | @tsv',
            ],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
        ),
    ]


def test_pull_request_authors_uses_numbered_pr_stems(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value="gh"))
    run = create_autospec(
        pull_requests.subprocess.run,
        side_effect=[
            subprocess.CompletedProcess([], 0, "gaborbernat\tUser\n", ""),
            subprocess.CompletedProcess([], 0, "alice\tUser\n", ""),
        ],
    )
    monkeypatch.setattr(pull_requests.subprocess, "run", run)

    authors = pull_requests.pull_request_authors(
        "quotaline/quotaline",
        {"6.feature.md": "Backfill history (#12)", "+new.feature.md": "Add feature (#13)"},
        numbered_prs=True,
    )

    assert authors == {
        "6": PullRequestAuthor(handle="gaborbernat", is_bot=False),
        "13": PullRequestAuthor(handle="alice", is_bot=False),
    }
    assert [call.args[0][2] for call in run.call_args_list] == [
        "repos/quotaline/quotaline/pulls/6",
        "repos/quotaline/quotaline/pulls/13",
    ]


def test_pull_request_authors_requires_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value=None))

    with pytest.raises(FileNotFoundError, match="GitHub CLI is required"):
        pull_requests.pull_request_authors("tox-dev/example", {"+first.feature.md": "Change (#42)"})


@pytest.mark.parametrize(
    ("result", "message"),
    [
        pytest.param(subprocess.CompletedProcess([], 1, "", "not found"), "not found", id="api-error"),
        pytest.param(
            subprocess.CompletedProcess([], 0, "not a handle\tUser\n", ""),
            "invalid GitHub author",
            id="bad-handle",
        ),
        pytest.param(
            subprocess.CompletedProcess([], 0, "malformed\n", ""),
            "invalid GitHub author response",
            id="bad-response",
        ),
        pytest.param(
            subprocess.CompletedProcess([], 0, "alice\tUnknown\n", ""),
            "unknown GitHub author type",
            id="unknown-account-type",
        ),
    ],
)
def test_pull_request_authors_rejects_bad_api_responses(
    monkeypatch: pytest.MonkeyPatch, result: subprocess.CompletedProcess[str], message: str
) -> None:
    monkeypatch.setattr(
        pull_requests.shutil,
        "which",
        create_autospec(pull_requests.shutil.which, return_value="/usr/bin/gh"),
    )
    monkeypatch.setattr(
        pull_requests.subprocess,
        "run",
        create_autospec(pull_requests.subprocess.run, return_value=result),
    )

    with pytest.raises(ValueError, match=message):
        pull_requests.pull_request_authors("tox-dev/example", {"+first.feature.md": "Change (#42)"})


def test_pull_request_authors_validates_repository_before_looking_up_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    gh_lookup = create_autospec(pull_requests.shutil.which)
    monkeypatch.setattr(pull_requests.shutil, "which", gh_lookup)

    with pytest.raises(ValueError, match="invalid repository"):
        pull_requests.pull_request_authors("bad", {"+first.feature.md": "Change (#42)"})

    gh_lookup.assert_not_called()
