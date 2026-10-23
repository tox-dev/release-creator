"""Read the pull requests associated with fragment commits."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # The shared regex and dataclass decorators resolve during module load.
from __future__ import annotations

lazy import json
lazy import re
lazy import shutil
lazy from dataclasses import dataclass
lazy from pathlib import Path
lazy from typing import Final

lazy from release_creator.fragments.names import fragment_number
lazy from release_creator.github import validate_repository
lazy from release_creator.process import run_text

_RE_HANDLE: Final = re.compile(
    r"""
    (?P<handle>[A-Za-z0-9-]+)   # GitHub account handle
    """,
    re.VERBOSE,
)


def fragment_pull_requests(
    repository: str, commits: dict[str, str], *, numbered_prs: bool = False
) -> dict[str, PullRequest]:
    """Resolve each fragment through GitHub's commit-to-pull-request API.

    :param repository: GitHub owner and repository.
    :param commits: Fragment names mapped to introducing commit hashes.
    :param numbered_prs: Treat numeric fragment stems as original PR numbers.
    :returns: Fragment names mapped to the merged pull request and its author.
    :raises FileNotFoundError: GitHub CLI is not installed.
    """
    validate_repository(repository)
    if (gh := shutil.which("gh")) is None:
        msg = "GitHub CLI is required to resolve pull request authors"
        raise FileNotFoundError(msg)
    by_commit, by_number = _pulls(
        gh,
        repository,
        list(
            dict.fromkeys(
                sha for name, sha in commits.items() if not (numbered_prs and fragment_number(Path(name)) is not None)
            )
        ),
        list(
            dict.fromkeys(
                number
                for name in commits
                if numbered_prs
                for number in [fragment_number(Path(name))]
                if number is not None
            )
        ),
    )
    return {
        name: by_number[number]
        if numbered_prs and (number := fragment_number(Path(name))) is not None
        else by_commit[sha]
        for name, sha in commits.items()
    }


def _pulls(
    gh: str, repository: str, shas: list[str], numbers: list[str]
) -> tuple[dict[str, PullRequest], dict[str, PullRequest]]:
    if not shas and not numbers:
        return {}, {}
    sha_length: Final = 40
    if any(len(sha) != sha_length or any(character not in "0123456789abcdef" for character in sha) for sha in shas):
        msg = "fragment commits must be 40-character lowercase Git object IDs"
        raise ValueError(msg)
    if any(int(number) < 1 for number in numbers):
        msg = "numbered fragments need a positive pull request number"
        raise ValueError(msg)
    owner, name = repository.split("/", 1)
    pulls: dict[str, PullRequest] = {}
    numbered: dict[str, PullRequest] = {}
    aliases = [
        (
            f"c{index}",
            sha,
            (
                f'c{index}: object(oid: "{sha}") {{ ... on Commit {{ associatedPullRequests(first: 100) '
                "{ nodes { number mergedAt author { login __typename } mergeCommit { oid } } } } }"
            ),
        )
        for index, sha in enumerate(shas)
    ] + [
        (
            f"p{index}",
            number,
            f"p{index}: pullRequest(number: {int(number)}) {{ number mergedAt author {{ login __typename }} }}",
        )
        for index, number in enumerate(numbers)
    ]
    batch_size: Final = 100
    for offset in range(0, len(aliases), batch_size):
        batch = aliases[offset : offset + batch_size]
        query = (
            f"query {{ repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
            f"{{ {' '.join(expression for _, _, expression in batch)} }} }}"
        )
        result = run_text([gh, "api", "graphql", "-F", "query=@-"], stdin=query)
        if result.returncode:
            msg = result.stderr.strip() or "could not read GitHub pull requests"
            raise ValueError(msg)
        try:
            response = json.loads(result.stdout)["data"]["repository"]
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            msg = "invalid GitHub associated pull requests response"
            raise ValueError(msg) from error
        for alias, identifier, _ in batch:
            (pulls if alias.startswith("c") else numbered)[identifier] = _read_alias(response, alias, identifier)
    return pulls, numbered


def _read_alias(response: object, alias: str, identifier: str) -> PullRequest:
    if not isinstance(response, dict):
        msg = f"invalid pull request response for {identifier}"
        raise TypeError(msg)
    if (pull := response.get(alias)) is None:
        msg = f"missing pull request response for {identifier}"
        raise ValueError(msg)
    if not isinstance(pull, dict):
        msg = f"invalid pull request response for {identifier}"
        raise TypeError(msg)
    if alias.startswith("c"):
        associated = pull.get("associatedPullRequests")
        if not isinstance(associated, dict) or not isinstance(nodes := associated.get("nodes"), list):
            msg = f"invalid pull request response for commit {identifier}"
            raise ValueError(msg)
        merged = [item for item in nodes if _is_squash_pull(item, identifier)]
        if len(merged) != 1:
            msg = f"expected one squash-merged pull request for commit {identifier}, found {len(merged)}"
            raise ValueError(msg)
        return _pull_request(merged[0], f"commit {identifier}")
    if pull.get("mergedAt") is None:
        msg = f"pull request #{identifier} is not merged"
        raise ValueError(msg)
    return _pull_request(pull, f"pull request #{identifier}")


def _is_squash_pull(pull: object, sha: str) -> bool:
    if not isinstance(pull, dict) or pull.get("mergedAt") is None:
        return False
    return bool(isinstance(commit := pull.get("mergeCommit"), dict) and commit.get("oid") == sha)


def _pull_request(response: dict[str, object], source: str) -> PullRequest:
    number, author = response.get("number"), response.get("author")
    if not isinstance(number, int) or isinstance(number, bool) or not isinstance(author, dict | None):
        msg = f"invalid pull request response for {source}"
        raise TypeError(msg)
    if number < 1:
        msg = f"invalid pull request number for {source}: {number}"
        raise ValueError(msg)
    login, account_type = ("ghost", "User") if author is None else (author.get("login"), author.get("__typename"))
    if not isinstance(login, str) or account_type not in {"User", "Bot"}:
        msg = f"invalid GitHub author for pull request #{number}"
        raise ValueError(msg)
    bot = account_type == "Bot"
    handle = login.removesuffix("[bot]") if bot else login
    if _RE_HANDLE.fullmatch(handle) is None:
        msg = f"invalid GitHub author for pull request #{number}: {login}"
        raise ValueError(msg)
    return PullRequest(number=str(number), author=PullRequestAuthor(handle=handle, is_bot=bot))


@dataclass(frozen=True, kw_only=True)
class PullRequestAuthor:
    """GitHub account attached to a merged pull request."""

    handle: str
    is_bot: bool


@dataclass(frozen=True, kw_only=True)
class PullRequest:
    """Merged pull request associated with a fragment."""

    number: str
    author: PullRequestAuthor


__all__ = [
    "PullRequest",
    "PullRequestAuthor",
    "fragment_pull_requests",
]
