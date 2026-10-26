"""Find pull request authors whose first merged pull request is in a release."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # The dataclass decorator resolves during module load.
from __future__ import annotations

lazy import json
lazy from dataclasses import dataclass
lazy from typing import Final

lazy from release_creator.fragments.pull_requests import AI_ASSISTANT_LOGINS, github_account
lazy from release_creator.process import run_text

_BATCH_SIZE: Final = 100


def first_contributions(repository: str, numbers: list[str]) -> list[FirstContribution]:
    """Return the release pull requests that are their author's first merged pull request.

    :param repository: GitHub owner and repository.
    :param numbers: Pull request numbers referenced by the release section.
    :returns: First contributions, ordered by merge time.
    """
    earliest: dict[str, FirstContribution] = {}
    for contribution in _merged_pulls(repository, numbers):
        key = contribution.login.casefold()
        if key not in earliest or contribution.merged_at < earliest[key].merged_at:
            earliest[key] = contribution
    candidates = sorted(earliest.values(), key=lambda contribution: contribution.merged_at)
    counts = _graphql(
        [
            (
                f"s{index}",
                (
                    f"s{index}: search(query: {json.dumps(_search(repository, candidate))}, type: ISSUE, first: 1) "
                    "{ issueCount }"
                ),
            )
            for index, candidate in enumerate(candidates)
        ],
        "",
    )
    return [candidate for index, candidate in enumerate(candidates) if _issue_count(counts, f"s{index}") == 0]


def _search(repository: str, candidate: FirstContribution) -> str:
    return f"repo:{repository} is:pr is:merged author:{candidate.login} merged:<{candidate.merged_at}"


def _merged_pulls(repository: str, numbers: list[str]) -> list[FirstContribution]:
    owner, name = repository.split("/", 1)
    pulls = _graphql(
        [
            (
                f"p{number}",
                f"p{number}: pullRequest(number: {number}) {{ number mergedAt author {{ login __typename }} }}",
            )
            for number in numbers
        ],
        f"repository(owner: {json.dumps(owner)}, name: {json.dumps(name)})",
    )
    contributions: list[FirstContribution] = []
    for number in numbers:
        pull = pulls.get(f"p{number}")
        if not isinstance(pull, dict) or not isinstance(author := pull.get("author"), dict | None):
            msg = f"invalid pull request response for #{number}"
            raise TypeError(msg)
        if (merged_at := pull.get("mergedAt")) is None:
            continue
        if not isinstance(merged_at, str):
            msg = f"invalid merge time for pull request #{number}"
            raise TypeError(msg)
        account = github_account(author, int(number))
        if not account.is_bot and account.handle.casefold() not in AI_ASSISTANT_LOGINS:
            contributions.append(FirstContribution(login=account.handle, number=number, merged_at=merged_at))
    return contributions


def _graphql(aliases: list[tuple[str, str]], scope: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for offset in range(0, len(aliases), _BATCH_SIZE):
        fields = " ".join(expression for _, expression in aliases[offset : offset + _BATCH_SIZE])
        query = f"query {{ {scope} {{ {fields} }} }}" if scope else f"query {{ {fields} }}"
        output = run_text(["gh", "api", "graphql", "-F", "query=@-"], stdin=query)
        if output.returncode:
            msg = output.stderr.strip() or "could not query GitHub"
            raise ValueError(msg)
        try:
            data = json.loads(output.stdout)["data"]
            if scope:
                data = data["repository"]
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            msg = "invalid GitHub GraphQL response"
            raise ValueError(msg) from error
        if not isinstance(data, dict):
            msg = "invalid GitHub GraphQL response"
            raise TypeError(msg)
        result.update(data)
    return result


def _issue_count(response: dict[str, object], alias: str) -> int:
    search = response.get(alias)
    if not isinstance(search, dict) or not isinstance(count := search.get("issueCount"), int):
        msg = f"invalid GitHub search response for {alias}"
        raise TypeError(msg)
    return count


@dataclass(frozen=True, kw_only=True)
class FirstContribution:
    """Pull request that is its author's first merged contribution."""

    login: str
    number: str
    merged_at: str


__all__ = [
    "FirstContribution",
    "first_contributions",
]
