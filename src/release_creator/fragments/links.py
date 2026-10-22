"""Associate named Towncrier fragments with merged pull requests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal
lazy from pathlib import Path

from release_creator.fragments.knope import changeset_parts
from release_creator.fragments.names import fragment_number, pending_changesets, pending_fragments
from release_creator.fragments.pull_requests import PullRequestAuthor, fragment_pull_request_number
from release_creator.github import MARKDOWN_AUTHOR, validate_repository

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
_RE_RST_USER: Final = re.compile(
    r"""
    :user:`(?P<handle>[A-Za-z0-9-]+)`  # RST GitHub user role
    |                                 # Or
    `@(?P<link_handle>[A-Za-z0-9-]+)  # Explicit profile link text
    \ <https://github\.com/(?P=link_handle)>`_  # Matching profile URL
    """,
    re.VERBOSE,
)
type _LinkMode = Literal["towncrier", "knope", "numbered-prs"]


def add_pull_request_links(
    directory: Path,
    repository: str,
    commit_subjects: dict[str, str],
    authors: dict[str, PullRequestAuthor] | None = None,
    *,
    mode: _LinkMode = "towncrier",
) -> None:
    """Keep fragment links and credits tied to their introducing pull requests."""
    validate_repository(repository)
    updates: list[tuple[Path, str]] = [
        (
            fragment,
            _link_fragment(fragment, repository, commit_subjects, authors, mode=mode),
        )
        for fragment in (pending_changesets(directory) if mode == "knope" else pending_fragments(directory))
    ]
    for fragment, content in updates:
        fragment.write_text(content, encoding="utf-8")


def _link_fragment(
    fragment: Path,
    repository: str,
    commit_subjects: dict[str, str],
    authors: dict[str, PullRequestAuthor] | None,
    *,
    mode: _LinkMode,
) -> str:
    number = fragment_pull_request_number(
        fragment.name, commit_subjects.get(fragment.name, ""), numbered_prs=mode == "numbered-prs"
    )
    content = fragment.read_text(encoding="utf-8")
    author = None
    if authors is not None:
        if number not in authors:
            msg = f"no author data for pull request #{number}"
            raise ValueError(msg)
        author = authors[number]
    target = _LinkTarget(fragment=fragment, repository=repository, number=number, author=author, knope=mode == "knope")
    if mode == "knope":
        frontmatter, heading, remainder = changeset_parts(fragment, content)
        return f"{frontmatter}# {_link_text(heading, target)}{remainder}"
    return f"{_link_text(content.rstrip(), target)}\n"


@dataclass(frozen=True, kw_only=True)
class _LinkTarget:
    fragment: Path
    repository: str
    number: str
    author: PullRequestAuthor | None
    knope: bool


def _link_text(
    content: str,
    target: _LinkTarget,
) -> str:
    fragment = target.fragment
    linked = _has_pull_request_link(content, target.repository, target.number)
    if not target.knope and fragment_number(fragment) is None and linked:
        msg = f"pull request already linked in {fragment}"
        raise ValueError(msg)
    if (match := _RE_AUTHOR_MARKER.search(content)) is not None:
        handles = _credited_handles(content[match.end() :], fragment.suffix)
        if target.author is not None and target.author.is_bot and target.author.handle in handles:
            msg = f"bot author @{target.author.handle} must not be credited in {fragment}"
            raise ValueError(msg)
        if target.author is not None and not target.author.is_bot and target.author.handle not in handles:
            msg = f"pull request author @{target.author.handle} is missing from the explicit credit in {fragment}"
            raise ValueError(msg)
        if linked:
            return content
        return (
            f"{content[: match.start()]} {_pull_request_link(target.repository, target.number, fragment.suffix)} "
            f"by {content[match.end() :]}"
        )
    handle = target.author.handle if target.author is not None and not target.author.is_bot else None
    if linked:
        return (
            f"{content.removesuffix('.')} by {_author_credit(handle, fragment.suffix)}{'' if target.knope else '.'}"
            if handle is not None
            else content
        )
    return _append_pull_request_link(content, target, handle)


def _has_pull_request_link(content: str, repository: str, number: str) -> bool:
    return any(
        (match["repository"] == repository and match["number"] == number) or match["rst_number"] == number
        for match in _RE_PULL_REQUEST_LINK.finditer(content)
    )


def _append_pull_request_link(content: str, target: _LinkTarget, author: str | None) -> str:
    link = _pull_request_link(target.repository, target.number, target.fragment.suffix)
    content = f"{content.removesuffix('.')} {link}"
    if author is not None:
        content += f" by {_author_credit(author, target.fragment.suffix)}"
    return f"{content}{'' if target.knope else '.'}"


def _pull_request_link(repository: str, number: str, extension: str) -> str:
    return f"(:pr:`{number}`)" if extension == ".rst" else f"([#{number}]({_pull_request_url(repository, number)}))"


def _author_credit(author: str, extension: str) -> str:
    return f":user:`{author}`" if extension == ".rst" else f"[@{author}](https://github.com/{author})"


def _credited_handles(credit_text: str, extension: str) -> set[str]:
    if extension == ".rst":
        return {author["handle"] or author["link_handle"] for author in _RE_RST_USER.finditer(credit_text)}
    return {author["handle"] for author in MARKDOWN_AUTHOR.finditer(credit_text)}


def _pull_request_url(repository: str, number: str) -> str:
    return f"https://github.com/{repository}/pull/{number}"


__all__ = [
    "add_pull_request_links",
]
