"""Merged pull request lookup tests."""

from __future__ import annotations

import json
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Model the GitHub CLI boundary.
from typing import cast
from unittest.mock import MagicMock, create_autospec

import pytest
from graphql import parse

from release_creator import process
from release_creator.fragments import pull_requests
from release_creator.fragments.pull_requests import PullRequest, PullRequestAuthor


def _graph_response(nodes: list[dict[str, object]]) -> dict[str, object]:
    return {"data": {"repository": {"c0": {"associatedPullRequests": {"nodes": nodes}}}}}


def _pull(sha: str, *, number: int = 42, login: str = "alice", account_type: str = "User") -> dict[str, object]:
    return {
        "number": number,
        "mergedAt": "2026-10-22T00:00:00Z",
        "mergeCommit": {"oid": sha},
        "author": {"login": login, "__typename": account_type},
    }


def test_fragment_pull_requests_sends_valid_graphql(monkeypatch: pytest.MonkeyPatch) -> None:
    response = {
        "data": {
            "repository": {
                f"c{index}": {"associatedPullRequests": {"nodes": [_pull(sha)]}}
                for index, sha in enumerate(("a" * 40, "b" * 40))
            }
        }
    }
    run: MagicMock = cast(
        "MagicMock",
        create_autospec(
            process.subprocess.run,
            return_value=subprocess.CompletedProcess([], 0, json.dumps(response), ""),
        ),
    )
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value="gh"))
    monkeypatch.setattr(process.subprocess, "run", run)

    pull_requests.fragment_pull_requests(
        "tox-dev/example", {"+first.feature.md": "a" * 40, "+second.feature.md": "b" * 40}
    )

    assert run.call_args.args[0] == ["gh", "api", "graphql", "-F", "query=@-"]
    parse(run.call_args.kwargs["input"])


@pytest.mark.parametrize(
    ("nodes", "error", "message"),
    [
        pytest.param([], ValueError, "expected one squash-merged pull request", id="no-pull"),
        pytest.param([_pull("b" * 40)], ValueError, "expected one squash-merged pull request", id="other-commit"),
        pytest.param([_pull("a" * 40)] * 2, ValueError, "expected one squash-merged pull request", id="two-pulls"),
        pytest.param([{}], ValueError, "expected one squash-merged pull request", id="missing-merge"),
        pytest.param([_pull("a" * 40, account_type="Mannequin")], ValueError, "invalid GitHub author", id="type"),
        pytest.param([_pull("a" * 40, login="bad handle")], ValueError, "invalid GitHub author", id="handle"),
        pytest.param([_pull("a" * 40, number=0)], ValueError, "invalid pull request number", id="number"),
        pytest.param([_pull("a" * 40, number=True)], TypeError, "invalid pull request response", id="boolean"),
    ],
)
def test_fragment_pull_requests_rejects_bad_responses(
    monkeypatch: pytest.MonkeyPatch, nodes: list[dict[str, object]], error: type[Exception], message: str
) -> None:
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value="gh"))
    monkeypatch.setattr(
        process.subprocess,
        "run",
        create_autospec(
            process.subprocess.run,
            return_value=subprocess.CompletedProcess([], 0, json.dumps(_graph_response(nodes)), ""),
        ),
    )

    with pytest.raises(error, match=message):
        pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40})


@pytest.mark.parametrize(
    ("stdout", "stderr", "status", "message"),
    [
        pytest.param("not json", "", 0, "invalid GitHub associated pull requests response", id="invalid-json"),
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


@pytest.mark.parametrize(
    ("sha", "message"),
    [
        pytest.param("short", "40-character lowercase", id="short"),
        pytest.param("A" * 40, "40-character lowercase", id="uppercase"),
    ],
)
def test_fragment_pull_requests_rejects_invalid_commit(monkeypatch: pytest.MonkeyPatch, sha: str, message: str) -> None:
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value="gh"))

    with pytest.raises(ValueError, match=message):
        pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": sha})


@pytest.mark.parametrize(
    ("response", "error", "message"),
    [
        pytest.param({"data": {}}, ValueError, "invalid GitHub associated", id="missing-repository"),
        pytest.param({"data": {"repository": []}}, TypeError, "invalid pull request response", id="repository-type"),
        pytest.param({"data": {"repository": {}}}, ValueError, "missing pull request response", id="missing-commit"),
        pytest.param(
            {"data": {"repository": {"c0": []}}}, TypeError, "invalid pull request response", id="commit-type"
        ),
        pytest.param(
            {"data": {"repository": {"c0": {}}}},
            TypeError,
            "invalid pull request response for commit",
            id="missing-nodes",
        ),
    ],
)
def test_fragment_pull_requests_rejects_incomplete_graphql_response(
    monkeypatch: pytest.MonkeyPatch, response: dict[str, object], error: type[Exception], message: str
) -> None:
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value="gh"))
    monkeypatch.setattr(
        process.subprocess,
        "run",
        create_autospec(
            process.subprocess.run,
            return_value=subprocess.CompletedProcess([], 0, json.dumps(response), ""),
        ),
    )

    with pytest.raises(error, match=message):
        pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40})


def test_fragment_pull_requests_credits_deleted_author(monkeypatch: pytest.MonkeyPatch) -> None:
    pull = _pull("a" * 40)
    pull["author"] = None
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value="gh"))
    monkeypatch.setattr(
        process.subprocess,
        "run",
        create_autospec(
            process.subprocess.run,
            return_value=subprocess.CompletedProcess([], 0, json.dumps(_graph_response([pull])), ""),
        ),
    )

    assert pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40}) == {
        "+news.feature.md": PullRequest(number="42", author=PullRequestAuthor(handle="ghost", is_bot=False))
    }


def test_fragment_pull_requests_chunks_large_history(monkeypatch: pytest.MonkeyPatch) -> None:
    commits = {f"+news-{index}.feature.md": f"{index:040x}" for index in range(101)}
    responses = [
        subprocess.CompletedProcess(
            [],
            0,
            json.dumps({
                "data": {
                    "repository": {
                        f"c{index}": {"associatedPullRequests": {"nodes": [_pull(f"{index:040x}")]}} for index in batch
                    }
                }
            }),
            "",
        )
        for batch in (range(100), range(100, 101))
    ]
    run: MagicMock = cast("MagicMock", create_autospec(process.subprocess.run, side_effect=responses))
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value="gh"))
    monkeypatch.setattr(process.subprocess, "run", run)

    assert len(pull_requests.fragment_pull_requests("tox-dev/example", commits)) == len(commits)
    assert run.call_count == len(responses)
    assert "c99: object" in run.call_args_list[0].kwargs["input"]
    assert "c100: object" in run.call_args_list[1].kwargs["input"]


def test_fragment_pull_requests_accepts_empty_commit_map(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull_requests.shutil, "which", create_autospec(pull_requests.shutil.which, return_value="gh"))

    assert pull_requests.fragment_pull_requests("tox-dev/example", {}) == {}


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
