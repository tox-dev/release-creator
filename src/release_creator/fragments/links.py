"""Associate named Towncrier fragments with merged pull requests."""

from __future__ import annotations

import re
from typing import Final
lazy from pathlib import Path

from release_creator.fragments.pull_requests import PullRequestAuthor, pull_request_number, validate_repository

_RE_PULL_REQUEST_LINK: Final = re.compile(
    r"""
    https://github\.com/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(?P<number>\d+)  # Markdown PR link
    |                                                                                       # Or
    :(?:pr|pull):`(?P<rst_number>\d+)`                                                     # RST PR role
    """,
    re.VERBOSE,
)
_RE_AUTHOR_MARKER: Final = re.compile(
    r"""
    (?:,?\s+)                     # Optional comma and whitespace before the credit
    by\s+                         # Credit marker and following whitespace
    (?=\[@|:user:`|`@)            # Supported Markdown or RST author syntax
    """,
    re.VERBOSE,
)
_RE_MARKDOWN_AUTHOR: Final = re.compile(
    r"""
    \[@(?P<handle>[A-Za-z0-9-]+)\]  # Markdown GitHub handle
    \(https://github\.com/(?P=handle)\)  # Matching profile link
    """,
    re.VERBOSE,
)
_RE_RST_USER: Final = re.compile(
    r"""
    :user:`(?P<handle>[A-Za-z0-9-]+)`  # RST GitHub user role
    |                                 # Or
    `@(?P<link_handle>[A-Za-z0-9-]+)  # Explicit profile link text
    \ <https://github\.com/(?P=link_handle)>`_  # Matching profile URL
    """,
    re.VERBOSE,
)


def add_pull_request_links(
    directory: Path,
    repository: str,
    commit_subjects: dict[str, str],
    authors: dict[str, PullRequestAuthor] | None = None,
) -> None:
    """Link each named fragment and add its verified author when available."""
    validate_repository(repository)
    updates: list[tuple[Path, str]] = [
        (fragment, _link_fragment(fragment, repository, commit_subjects, authors))
        for fragment in sorted(directory.glob("+*.*"))
    ]
    for fragment, content in updates:
        fragment.write_text(content, encoding="utf-8")


def _link_fragment(
    fragment: Path,
    repository: str,
    commit_subjects: dict[str, str],
    authors: dict[str, PullRequestAuthor] | None,
) -> str:
    number = pull_request_number(commit_subjects.get(fragment.name, ""))
    content = fragment.read_text(encoding="utf-8").rstrip()
    if _has_pull_request_link(content, repository, number):
        msg = f"pull request already linked in {fragment}"
        raise ValueError(msg)
    if authors is not None and number not in authors:
        msg = f"no author data for pull request #{number}"
        raise ValueError(msg)
    author = authors[number] if authors is not None else None
    if (match := _RE_AUTHOR_MARKER.search(content)) is not None:
        handles = _credited_handles(content[match.end() :], fragment.suffix)
        if author is not None and author.is_bot and author.handle in handles:
            msg = f"bot author @{author.handle} must not be credited in {fragment}"
            raise ValueError(msg)
        if author is not None and not author.is_bot and author.handle not in handles:
            msg = f"pull request author @{author.handle} is missing from the explicit credit in {fragment}"
            raise ValueError(msg)
        link = _pull_request_link(repository, number, fragment.suffix)
        return f"{content[: match.start()]} {link} by {content[match.end() :]}\n"
    handle = author.handle if author is not None and not author.is_bot else None
    return _append_pull_request_link(content, repository, number, fragment.suffix, handle)


def _has_pull_request_link(content: str, repository: str, number: str) -> bool:
    return any(
        (match["repository"] == repository and match["number"] == number) or match["rst_number"] == number
        for match in _RE_PULL_REQUEST_LINK.finditer(content)
    )


def _pull_request_link(repository: str, number: str, extension: str) -> str:
    return f"(:pr:`{number}`)" if extension == ".rst" else f"([#{number}]({_pull_request_url(repository, number)}))"


def _append_pull_request_link(content: str, repository: str, number: str, extension: str, author: str | None) -> str:
    content = content.removesuffix(".") + f" {_pull_request_link(repository, number, extension)}"
    if author is not None:
        content += f" by {_author_credit(author, extension)}"
    return f"{content}.\n"


def _author_credit(author: str, extension: str) -> str:
    return f":user:`{author}`" if extension == ".rst" else f"[@{author}](https://github.com/{author})"


def _credited_handles(credit_text: str, extension: str) -> set[str]:
    if extension == ".rst":
        return {author["handle"] or author["link_handle"] for author in _RE_RST_USER.finditer(credit_text)}
    return {author["handle"] for author in _RE_MARKDOWN_AUTHOR.finditer(credit_text)}


def _pull_request_url(repository: str, number: str) -> str:
    return f"https://github.com/{repository}/pull/{number}"


__all__ = [
    "add_pull_request_links",
]
