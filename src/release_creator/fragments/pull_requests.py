"""Read the pull requests associated with fragment commits."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from release_creator.fragments.names import fragment_number
from release_creator.github import validate_repository
from release_creator.process import run_text

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
    by_commit = {
        sha: _pull_for_commit(gh, repository, sha)
        for sha in dict.fromkeys(
            sha for name, sha in commits.items() if not (numbered_prs and fragment_number(Path(name)) is not None)
        )
    }
    numbers = (
        number for name in commits if numbered_prs for number in [fragment_number(Path(name))] if number is not None
    )
    by_number = {
        number: _pull_request(_api(gh, f"repos/{repository}/pulls/{number}"), f"pull request #{number}")
        for number in dict.fromkeys(numbers)
    }
    return {
        name: by_number[number]
        if numbered_prs and (number := fragment_number(Path(name))) is not None
        else by_commit[sha]
        for name, sha in commits.items()
    }


def _pull_for_commit(gh: str, repository: str, sha: str) -> PullRequest:
    response = _api(gh, f"repos/{repository}/commits/{sha}/pulls?per_page=100")
    if not isinstance(response, list):
        msg = f"invalid pull request response for commit {sha}"
        raise TypeError(msg)
    merged = [item for item in response if isinstance(item, dict) and item.get("merge_commit_sha") == sha]
    if len(merged) != 1:
        msg = f"expected one merged pull request for commit {sha}, found {len(merged)}"
        raise ValueError(msg)
    return _pull_request(merged[0], f"commit {sha}")


def _api(gh: str, path: str) -> object:
    result = run_text([gh, "api", path])
    if result.returncode:
        msg = result.stderr.strip() or f"could not read GitHub {path}"
        raise ValueError(msg)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        msg = f"invalid GitHub response for {path}"
        raise ValueError(msg) from error


def _pull_request(response: object, source: str) -> PullRequest:
    if not isinstance(response, dict) or not isinstance(response.get("user"), dict):
        msg = f"invalid pull request response for {source}"
        raise TypeError(msg)
    number, user = response.get("number"), response["user"]
    if not isinstance(number, int) or isinstance(number, bool) or not isinstance(user, dict):
        msg = f"invalid pull request response for {source}"
        raise TypeError(msg)
    if number < 1:
        msg = f"invalid pull request number for {source}: {number}"
        raise ValueError(msg)
    login, account_type = user.get("login"), user.get("type")
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
