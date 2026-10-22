"""Read pull request authors from merged squash commits."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from release_creator.fragments.names import fragment_number
from release_creator.github import validate_repository
from release_creator.process import run_text

_RE_PULL_REQUEST: Final = re.compile(
    r"""
    \(\#                         # Squash merge pull request marker
    (?P<number>\d+)             # Pull request number
    \)$                          # Marker ends the commit subject
    """,
    re.VERBOSE,
)
_RE_HANDLE: Final = re.compile(
    r"""
    (?P<handle>[A-Za-z0-9-]+)   # GitHub account handle
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, kw_only=True)
class PullRequestAuthor:
    """GitHub account attached to a merged pull request."""

    handle: str
    is_bot: bool


def pull_request_number(subject: str) -> str:
    """Return the pull request number from a squash commit subject.

    :param subject: Squash commit subject.
    :returns: Pull request number from the squash commit subject.
    :raises ValueError: The commit subject does not end in a squash pull request number.
    """
    if (match := _RE_PULL_REQUEST.search(subject)) is None:
        msg = f"no squash pull request number in commit subject: {subject}"
        raise ValueError(msg)
    return cast("str", match["number"])


def fragment_pull_request_number(name: str, subject: str, *, numbered_prs: bool = False) -> str:
    """Use a numbered stem as its PR only where the repository declares that convention.

    :param name: Fragment filename.
    :param subject: Introducing squash commit subject.
    :param numbered_prs: Treat a numeric fragment stem as the original PR number.
    :returns: Original PR number for opted-in numeric fragments; otherwise the squash PR number.
    """
    if numbered_prs and (number := fragment_number(Path(name))) is not None:
        return number
    return pull_request_number(subject)


def pull_request_authors(
    repository: str, commit_subjects: dict[str, str], *, numbered_prs: bool = False
) -> dict[str, PullRequestAuthor]:
    """Read human pull request authors with the GitHub CLI.

    :param repository: GitHub owner and repository.
    :param commit_subjects: Fragment names mapped to introducing squash subjects.
    :param numbered_prs: Treat numeric fragment stems as original PR numbers.
    :returns: Pull request numbers mapped to GitHub author accounts.
    :raises FileNotFoundError: GitHub CLI is not installed.
    :raises ValueError: GitHub could not return a valid pull request author.
    """
    validate_repository(repository)
    if (gh := shutil.which("gh")) is None:
        msg = "GitHub CLI is required to resolve pull request authors"
        raise FileNotFoundError(msg)
    authors: dict[str, PullRequestAuthor] = {}
    for number in dict.fromkeys(
        fragment_pull_request_number(name, subject, numbered_prs=numbered_prs)
        for name, subject in commit_subjects.items()
    ):
        result = run_text(
            [
                gh,
                "api",
                f"repos/{repository}/pulls/{number}",
                "--jq",
                '.user | [(.login // ""), (.type // "")] | @tsv',
            ],
        )
        if result.returncode:
            msg = result.stderr.strip() or f"could not read author for pull request #{number}"
            raise ValueError(msg)
        try:
            login, account_type = result.stdout.rstrip("\n").split("\t")
        except ValueError as error:
            msg = f"invalid GitHub author response for pull request #{number}"
            raise ValueError(msg) from error
        if account_type not in {"User", "Bot"}:
            msg = f"unknown GitHub author type for pull request #{number}: {account_type or 'missing'}"
            raise ValueError(msg)
        bot = account_type == "Bot"
        handle = login.removesuffix("[bot]") if bot else login
        if _RE_HANDLE.fullmatch(handle) is None:
            msg = f"invalid GitHub author for pull request #{number}: {login}"
            raise ValueError(msg)
        authors[number] = PullRequestAuthor(handle=handle, is_bot=bot)
    return authors


__all__ = [
    "PullRequestAuthor",
    "fragment_pull_request_number",
    "pull_request_authors",
    "pull_request_number",
]
