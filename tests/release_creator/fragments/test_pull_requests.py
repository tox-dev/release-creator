"""Merged pull request lookup tests."""

from __future__ import annotations

import json
import re
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Model the GitHub CLI boundary.
from typing import cast
from unittest.mock import MagicMock, create_autospec

import pytest
from graphql import parse

from release_creator import process
from release_creator.fragments import pull_requests
from release_creator.fragments.pull_requests import PullRequest, PullRequestCredit


def _graph_response(nodes: list[dict[str, object]]) -> dict[str, object]:
    return {"data": {"repository": {"c0": {"associatedPullRequests": {"nodes": nodes}}}}}


def _pull(sha: str, *, number: int = 42, login: str = "alice", account_type: str = "User") -> dict[str, object]:
    return {
        "number": number,
        "mergedAt": "2026-10-22T00:00:00Z",
        "mergeCommit": {"oid": sha, "authors": {"nodes": []}},
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
    monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value="gh"))
    monkeypatch.setattr(process.subprocess, "run", run)

    pull_requests.fragment_pull_requests(
        "tox-dev/example", {"+first.feature.md": "a" * 40, "+second.feature.md": "b" * 40}
    )

    assert run.call_args.args[0] == ["gh", "api", "graphql", "-F", "query=@-"]
    parse(run.call_args.kwargs["input"])


def test_fragment_pull_requests_reports_missing_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value=None))

    with pytest.raises(FileNotFoundError, match="gh is required"):
        pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40})


@pytest.mark.parametrize(
    ("nodes", "error", "message"),
    [
        pytest.param([], ValueError, "expected one squash-merged pull request", id="no-pull"),
        pytest.param([_pull("b" * 40)], ValueError, "expected one squash-merged pull request", id="other-commit"),
        pytest.param([_pull("a" * 40)] * 2, ValueError, "expected one squash-merged pull request", id="two-pulls"),
        pytest.param([{}], ValueError, "expected one squash-merged pull request", id="missing-merge"),
        pytest.param([_pull("a" * 40, account_type="Organization")], ValueError, "invalid GitHub author", id="type"),
        pytest.param([_pull("a" * 40, number=0)], ValueError, "invalid pull request number", id="number"),
        pytest.param([_pull("a" * 40, number=True)], TypeError, "invalid pull request response", id="boolean"),
    ],
)
def test_fragment_pull_requests_rejects_bad_responses(
    monkeypatch: pytest.MonkeyPatch, nodes: list[dict[str, object]], error: type[Exception], message: str
) -> None:
    monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value="gh"))
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
    monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value="gh"))
    monkeypatch.setattr(
        process.subprocess,
        "run",
        create_autospec(process.subprocess.run, return_value=subprocess.CompletedProcess([], status, stdout, stderr)),
    )

    with pytest.raises(ValueError, match=message):
        pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40})


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
    monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value="gh"))
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


@pytest.mark.parametrize(
    "author",
    [pytest.param(None, id="deleted"), pytest.param({"login": "old-user", "__typename": "Mannequin"}, id="mannequin")],
)
def test_fragment_pull_requests_credits_deleted_author(
    monkeypatch: pytest.MonkeyPatch, author: dict[str, str] | None
) -> None:
    pull = _pull("a" * 40)
    pull["author"] = author
    monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value="gh"))
    monkeypatch.setattr(
        process.subprocess,
        "run",
        create_autospec(
            process.subprocess.run,
            return_value=subprocess.CompletedProcess([], 0, json.dumps(_graph_response([pull])), ""),
        ),
    )

    assert pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40}) == {
        "+news.feature.md": PullRequest(
            number="42",
            credits=(PullRequestCredit(name="ghost", linked=True),),
        )
    }


def test_fragment_pull_requests_chunks_large_history(monkeypatch: pytest.MonkeyPatch) -> None:
    commits = {f"+news-{index}.feature.md": f"{index:040x}" for index in range(81)}
    batches = (range(40), range(40, 80), range(80, 81))
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
        for batch in batches
    ]
    run: MagicMock = cast("MagicMock", create_autospec(process.subprocess.run, side_effect=responses))
    monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value="gh"))
    monkeypatch.setattr(process.subprocess, "run", run)

    assert len(pull_requests.fragment_pull_requests("tox-dev/example", commits)) == len(commits)
    assert [re.findall(r"\bc(\d+): object", call.kwargs["input"]) for call in run.call_args_list] == [
        [str(index) for index in batch] for batch in batches
    ]


def test_fragment_pull_requests_accepts_empty_commit_map(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value="gh"))

    assert pull_requests.fragment_pull_requests("tox-dev/example", {}) == {}


def _commit_author(
    name: str = "Bob", email: str = "bob@example.com", login: str | None = "bob", account_type: str = "User"
) -> dict[str, object]:
    return {
        "name": name,
        "email": email,
        "user": None if login is None else {"login": login, "__typename": account_type},
    }


def _credits(
    monkeypatch: pytest.MonkeyPatch,
    authors: list[object],
    *,
    login: str = "alice",
    account_type: str = "User",
) -> tuple[PullRequestCredit, ...]:
    pull = _pull("a" * 40, login=login, account_type=account_type)
    pull["mergeCommit"] = {"oid": "a" * 40, "authors": {"nodes": authors}}
    monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value="gh"))
    monkeypatch.setattr(
        process.subprocess,
        "run",
        create_autospec(
            process.subprocess.run,
            return_value=subprocess.CompletedProcess([], 0, json.dumps(_graph_response([pull])), ""),
        ),
    )
    return pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40})[
        "+news.feature.md"
    ].credits


def test_fragment_pull_requests_queries_merge_commit_authors(monkeypatch: pytest.MonkeyPatch) -> None:
    run: MagicMock = cast(
        "MagicMock",
        create_autospec(
            process.subprocess.run,
            return_value=subprocess.CompletedProcess([], 0, json.dumps(_graph_response([_pull("a" * 40)])), ""),
        ),
    )
    monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value="gh"))
    monkeypatch.setattr(process.subprocess, "run", run)

    pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40})

    assert (
        "mergeCommit { oid authors(first: 100) { nodes { name email user { login __typename } } } }"
        in run.call_args.kwargs["input"]
    )


@pytest.mark.parametrize(
    "email",
    [
        pytest.param("noreply@anthropic.com", id="anthropic"),
        pytest.param("codex@openai.com", id="openai"),
        pytest.param("agent@commandcode.ai", id="commandcode"),
        pytest.param("agent@zo.computer", id="zo"),
        pytest.param("198982749+Copilot@users.noreply.github.com", id="copilot"),
        pytest.param("NoReply@Anthropic.COM", id="case-insensitive"),
        pytest.param("198982749+copilot@USERS.noreply.github.com", id="copilot-case-insensitive"),
    ],
)
def test_fragment_pull_requests_drops_ai_assistant_authors(monkeypatch: pytest.MonkeyPatch, email: str) -> None:
    assert _credits(monkeypatch, [_commit_author(name="Claude", email=email, login="claude")]) == (
        PullRequestCredit(name="alice", linked=True),
    )


@pytest.mark.parametrize(
    "login",
    [
        pytest.param("claude", id="claude"),
        pytest.param("codex", id="codex"),
        pytest.param("CommandCodeBot", id="commandcode"),
        pytest.param("COPILOT", id="copilot-case-insensitive"),
    ],
)
def test_fragment_pull_requests_drops_ai_assistant_commit_logins(monkeypatch: pytest.MonkeyPatch, login: str) -> None:
    assert _credits(monkeypatch, [_commit_author(name="Agent", email="agent@example.com", login=login)]) == (
        PullRequestCredit(name="alice", linked=True),
    )


def test_fragment_pull_requests_drops_ai_assistant_pull_request_author(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _credits(monkeypatch, [_commit_author(login="bob")], login="Claude") == (
        PullRequestCredit(name="bob", linked=True),
    )


def test_fragment_pull_requests_credits_nobody_when_only_ai_assistants_remain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _credits(monkeypatch, [_commit_author(login="claude")], login="claude") == ()


@pytest.mark.parametrize(
    "email",
    [
        pytest.param("claude@example.com", id="ai-name-human-email"),
        pytest.param("noreply@anthropic.com.example", id="domain-not-at-end"),
        pytest.param("x+Copilot@users.noreply.github.com", id="copilot-without-id"),
    ],
)
def test_fragment_pull_requests_keeps_authors_outside_ai_list(monkeypatch: pytest.MonkeyPatch, email: str) -> None:
    assert _credits(monkeypatch, [_commit_author(name="Claude", email=email, login="carol")]) == (
        PullRequestCredit(name="alice", linked=True),
        PullRequestCredit(name="carol", linked=True),
    )


def test_fragment_pull_requests_credits_unlinked_author_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _credits(monkeypatch, [_commit_author(name="Bob Builder", login=None)]) == (
        PullRequestCredit(name="alice", linked=True),
        PullRequestCredit(name="Bob Builder", linked=False),
    )


@pytest.mark.parametrize(
    "author",
    [
        pytest.param({"name": " ", "email": "bob@example.com", "user": None}, id="blank-name"),
        pytest.param({"name": "", "email": "bob@example.com", "user": None}, id="empty-name"),
        pytest.param({"email": None, "user": None}, id="missing-name"),
    ],
)
def test_fragment_pull_requests_skips_unnamed_unlinked_author(
    monkeypatch: pytest.MonkeyPatch, author: dict[str, object]
) -> None:
    assert _credits(monkeypatch, [author, _commit_author(login="bob")]) == (
        PullRequestCredit(name="alice", linked=True),
        PullRequestCredit(name="bob", linked=True),
    )


def test_fragment_pull_requests_orders_pull_request_author_first(monkeypatch: pytest.MonkeyPatch) -> None:
    authors: list[object] = [
        _commit_author(name="Carol", login="carol"),
        _commit_author(name="Alice", login="Alice"),
        _commit_author(name="Bob", login="bob"),
    ]

    assert _credits(monkeypatch, authors) == (
        PullRequestCredit(name="alice", linked=True),
        PullRequestCredit(name="carol", linked=True),
        PullRequestCredit(name="bob", linked=True),
    )


@pytest.mark.parametrize(
    ("authors", "expected"),
    [
        pytest.param(
            [_commit_author(login="bob"), _commit_author(login="BOB")],
            (PullRequestCredit(name="alice", linked=True), PullRequestCredit(name="bob", linked=True)),
            id="login-case",
        ),
        pytest.param(
            [_commit_author(name="Dan", login=None), _commit_author(name="dan", login=None)],
            (PullRequestCredit(name="alice", linked=True), PullRequestCredit(name="Dan", linked=False)),
            id="unlinked-name-case",
        ),
        pytest.param(
            [_commit_author(name="bob", login=None), _commit_author(name="Bob", login="bob")],
            (
                PullRequestCredit(name="alice", linked=True),
                PullRequestCredit(name="bob", linked=False),
                PullRequestCredit(name="bob", linked=True),
            ),
            id="unlinked-name-and-login-differ",
        ),
    ],
)
def test_fragment_pull_requests_deduplicates_authors(
    monkeypatch: pytest.MonkeyPatch, authors: list[object], expected: tuple[PullRequestCredit, ...]
) -> None:
    assert _credits(monkeypatch, authors) == expected


@pytest.mark.parametrize(
    "bot",
    [
        pytest.param(_commit_author(login="dependabot[bot]"), id="login-suffix"),
        pytest.param(_commit_author(login="renovate", account_type="Bot"), id="bot-type"),
    ],
)
def test_fragment_pull_requests_drops_bots_beside_humans(monkeypatch: pytest.MonkeyPatch, bot: object) -> None:
    assert _credits(monkeypatch, [bot]) == (PullRequestCredit(name="alice", linked=True),)


def test_fragment_pull_requests_drops_bot_author_beside_human_co_author(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _credits(monkeypatch, [_commit_author(login="bob")], login="dependabot", account_type="Bot") == (
        PullRequestCredit(name="bob", linked=True),
    )


def test_fragment_pull_requests_credits_bots_when_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    authors: list[object] = [
        _commit_author(login="dependabot[bot]"),
        _commit_author(login="pre-commit-ci[bot]"),
        _commit_author(name="Claude", email="noreply@anthropic.com", login="claude"),
    ]

    assert _credits(monkeypatch, authors, login="dependabot", account_type="Bot") == (
        PullRequestCredit(name="dependabot", linked=True),
        PullRequestCredit(name="pre-commit-ci", linked=True),
    )


def test_fragment_pull_requests_credits_mannequin_co_author_as_ghost(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _credits(monkeypatch, [_commit_author(login="old-user", account_type="Mannequin")]) == (
        PullRequestCredit(name="alice", linked=True),
        PullRequestCredit(name="ghost", linked=True),
    )


@pytest.mark.parametrize(
    ("merge_commit", "error", "message"),
    [
        pytest.param({"oid": "a" * 40}, TypeError, "invalid merge commit authors", id="missing-authors"),
        pytest.param({"oid": "a" * 40, "authors": {}}, TypeError, "invalid merge commit authors", id="missing-nodes"),
        pytest.param(
            {"oid": "a" * 40, "authors": {"nodes": [[]]}}, TypeError, "invalid merge commit author ", id="node-type"
        ),
        pytest.param(
            {"oid": "a" * 40, "authors": {"nodes": [{"name": "Bob", "email": "bob@example.com", "user": []}]}},
            TypeError,
            "invalid merge commit author ",
            id="user-type",
        ),
        pytest.param(
            {"oid": "a" * 40, "authors": {"nodes": [_commit_author(account_type="Organization")]}},
            ValueError,
            "invalid GitHub author",
            id="account-type",
        ),
    ],
)
def test_fragment_pull_requests_rejects_bad_merge_commit_authors(
    monkeypatch: pytest.MonkeyPatch, merge_commit: dict[str, object], error: type[Exception], message: str
) -> None:
    pull = _pull("a" * 40)
    pull["mergeCommit"] = merge_commit
    monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value="gh"))
    monkeypatch.setattr(
        process.subprocess,
        "run",
        create_autospec(
            process.subprocess.run,
            return_value=subprocess.CompletedProcess([], 0, json.dumps(_graph_response([pull])), ""),
        ),
    )

    with pytest.raises(error, match=message):
        pull_requests.fragment_pull_requests("tox-dev/example", {"+news.feature.md": "a" * 40})
