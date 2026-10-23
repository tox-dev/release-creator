"""Associate named Towncrier fragments with merged pull requests."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # Shared regexes and dataclass decorators resolve during module load.
from __future__ import annotations

lazy import re
lazy from dataclasses import dataclass
lazy from pathlib import Path
lazy from typing import Final, Literal

lazy from release_creator.fragments.knope import changeset_parts
lazy from release_creator.fragments.names import fragment_number, pending_changesets, pending_fragments
lazy from release_creator.fragments.pull_requests import PullRequest, PullRequestAuthor
lazy from release_creator.github import MARKDOWN_AUTHOR

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
type _LinkMode = Literal["towncrier", "knope"]


def add_pull_request_links(
    directory: Path,
    repository: str,
    pull_requests: dict[str, PullRequest],
    *,
    mode: _LinkMode = "towncrier",
) -> None:
    """Keep fragment links and credits tied to their introducing pull requests."""
    updates: list[tuple[Path, str]] = [
        (
            fragment,
            _link_fragment(fragment, repository, pull_requests, mode=mode),
        )
        for fragment in (pending_changesets(directory) if mode == "knope" else pending_fragments(directory))
    ]
    for fragment, content in updates:
        fragment.write_text(content, encoding="utf-8")


def _link_fragment(
    fragment: Path,
    repository: str,
    pull_requests: dict[str, PullRequest],
    *,
    mode: _LinkMode,
) -> str:
    if (pull_request := pull_requests.get(fragment.name)) is None:
        msg = f"no pull request data for {fragment}"
        raise ValueError(msg)
    content = fragment.read_text(encoding="utf-8")
    target = _LinkTarget(
        fragment=fragment,
        repository=repository,
        number=pull_request.number,
        author=pull_request.author,
        knope=mode == "knope",
    )
    if mode == "knope":
        frontmatter, heading, remainder = changeset_parts(fragment, content)
        return f"{frontmatter}# {_link_text(heading, target)}{remainder}"
    return f"{_link_text(content.rstrip(), target)}\n"


@dataclass(frozen=True, kw_only=True)
class _LinkTarget:
    fragment: Path
    repository: str
    number: str
    author: PullRequestAuthor
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
        if target.author.handle == "ghost":
            msg = f"cannot verify explicit credit for deleted pull request author in {fragment}"
            raise ValueError(msg)
        if target.author.is_bot and target.author.handle in handles:
            msg = f"bot author @{target.author.handle} must not be credited in {fragment}"
            raise ValueError(msg)
        if not target.author.is_bot and target.author.handle not in handles:
            msg = f"pull request author @{target.author.handle} is missing from the explicit credit in {fragment}"
            raise ValueError(msg)
        if linked:
            return content
        return (
            f"{content[: match.start()]} {_pull_request_link(target.repository, target.number, fragment.suffix)} "
            f"by {content[match.end() :]}"
        )
    handle = target.author.handle if not target.author.is_bot else None
    if linked:
        before, after = _split_trailing_code(content, fragment.suffix)
        if handle is None:
            return content
        suffix = "" if target.knope else "."
        return f"{before.removesuffix('.')} by {_author_credit(handle, fragment.suffix)}{suffix}{after}"
    return _append_pull_request_link(content, target, handle)


def _has_pull_request_link(content: str, repository: str, number: str) -> bool:
    return any(
        (match["repository"] == repository and match["number"] == number) or match["rst_number"] == number
        for match in _RE_PULL_REQUEST_LINK.finditer(content)
    )


def _append_pull_request_link(content: str, target: _LinkTarget, author: str | None) -> str:
    link = _pull_request_link(target.repository, target.number, target.fragment.suffix)
    before, after = _split_trailing_code(content, target.fragment.suffix)
    content = f"{before.removesuffix('.')} {link}"
    if author is not None:
        content += f" by {_author_credit(author, target.fragment.suffix)}"
    return f"{content}{'' if target.knope else '.'}{after}"


def _split_trailing_code(content: str, suffix: str) -> tuple[str, str]:
    lines = content.splitlines(keepends=True)
    if suffix == ".md" and lines and (closing := lines[-1].strip()).startswith(("```", "~~~")):
        minimum_fence_length: Final = 3
        fence = closing[0] * minimum_fence_length
        if closing == closing[0] * len(closing) and len(closing) >= minimum_fence_length:
            opening = next(
                (index for index in range(len(lines) - 2, -1, -1) if lines[index].strip().startswith(fence)),
                None,
            )
            if opening is not None:
                position = sum(map(len, lines[:opening]))
                before = content[:position].rstrip()
                return before, content[len(before) :]
    if suffix == ".rst":
        opening = next(
            (index for index in range(len(lines) - 1, -1, -1) if lines[index].lstrip().startswith(".. code-block::")),
            None,
        )
        if opening is not None and all(not line.strip() or line.startswith(" ") for line in lines[opening + 1 :]):
            position = sum(map(len, lines[:opening]))
            before = content[:position].rstrip()
            return before, content[len(before) :]
    return content, ""


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
