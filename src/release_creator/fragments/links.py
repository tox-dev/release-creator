"""Associate named Towncrier fragments with merged pull requests."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # Shared regexes and dataclass decorators resolve during module load.
from __future__ import annotations

lazy import re
lazy from collections.abc import Iterator
lazy from dataclasses import dataclass
lazy from itertools import accumulate
lazy from pathlib import Path
lazy from typing import Final, Literal

lazy from markdown_it import MarkdownIt
lazy from markdown_it.token import Token

lazy from release_creator.fragments.knope import changeset_parts
lazy from release_creator.fragments.names import fragment_number, pending_changesets, pending_fragments
lazy from release_creator.fragments.pull_requests import PullRequest, PullRequestCredit
lazy from release_creator.fragments.shape import markdown_visible_children, validate_towncrier_fragment

_RE_AUTHOR_MARKER: Final = re.compile(
    r"""
    (?:,?\s+)                     # Optional comma and whitespace before the credit
    by\s+                         # Credit marker and following whitespace
    (?=(?:\*{1,2})?(?:\[@|:user:`|`@|@[A-Za-z0-9-]))  # Supported author syntax, optionally emphasized in RST
    """,
    re.VERBOSE,
)
_RE_USER_ROLE: Final = re.compile(
    r"""
    :user:`(?P<handle>[A-Za-z0-9-]+)`  # GitHub user role, with or without a credit marker
    """,
    re.VERBOSE | re.IGNORECASE,
)
_RE_RST_INLINE_LITERAL: Final = re.compile(
    r"""
    ``(?P<text>.*?)``  # RST inline literal, including escaped role syntax
    """,
    re.DOTALL | re.VERBOSE,
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
    if mode == "towncrier":
        validate_towncrier_fragment(content, fragment)
    target = _LinkTarget(
        fragment=fragment,
        repository=repository,
        number=pull_request.number,
        credits=pull_request.credits,
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
    credits: tuple[PullRequestCredit, ...]
    knope: bool


def _link_text(
    content: str,
    target: _LinkTarget,
) -> str:
    fragment = target.fragment
    linked = _has_pull_request_link(content, target.repository, target.number, fragment.suffix)
    if not target.knope and fragment_number(fragment) is None and linked:
        msg = f"pull request already linked in {fragment}"
        raise ValueError(msg)
    credit_prose = _credit_prose(content, fragment.suffix)
    match = _RE_AUTHOR_MARKER.search(credit_prose)
    if match is not None or _RE_USER_ROLE.search(credit_prose) is not None:
        return _keep_explicit_credit(content, target, match, linked=linked)
    credit = _credit_list(target.credits, fragment.suffix)
    if linked:
        before, after = _split_trailing_code(content, fragment.suffix)
        suffix = "" if target.knope else "."
        return f"{before.removesuffix('.')} by {credit}{suffix}{after}"
    return _append_pull_request_link(content, target, credit)


def _credit_list(credited: tuple[PullRequestCredit, ...], extension: str) -> str:
    names = [_author_credit(credit.name, extension) if credit.linked else credit.name for credit in credited]
    return f"{', '.join(names[:-1])} and {names[-1]}" if len(names) > 1 else names[0]


def _keep_explicit_credit(content: str, target: _LinkTarget, match: re.Match[str] | None, *, linked: bool) -> str:
    fragment = target.fragment
    if linked:
        return content
    if match is None:
        return _append_pull_request_link(content, target, None)
    if fragment.suffix == ".md":
        return _append_pull_request_link(content, target, None, anchor=_markdown_credit_anchor(content))
    return (
        f"{content[: match.start()]} {_pull_request_link(target.repository, target.number, fragment.suffix)} "
        f"by {content[match.end() :]}"
    )


def has_hand_written_credit(content: str, extension: str) -> bool:
    """Detect an author credit the way the linker does before it adds one.

    :param content: Fragment text.
    :param extension: Fragment suffix, ``.md`` or ``.rst``.
    :returns: Whether the visible prose already credits an author.
    """
    prose = _credit_prose(content, extension)
    return _RE_AUTHOR_MARKER.search(prose) is not None or _RE_USER_ROLE.search(prose) is not None


def has_hand_written_pull_request_link(content: str, extension: str) -> bool:
    """Detect a pull request link the way the linker does before it adds one.

    :param content: Fragment text.
    :param extension: Fragment suffix, ``.md`` or ``.rst``.
    :returns: Whether the visible prose links any pull request.
    """
    return any(_pull_request_links(content, extension))


def _has_pull_request_link(content: str, repository: str, number: str, extension: str) -> bool:
    return any(
        (match["repository"] == repository and match["number"] == number)
        or number in {match["rst_number"], match["bare_number"]}
        for match in _pull_request_links(content, extension)
    )


def _pull_request_links(content: str, extension: str) -> Iterator[re.Match[str]]:
    return (
        match
        for text in (_markdown_prose(content) if extension == ".md" else _rst_prose(content))
        for match in re.finditer(
            r"""
            https://github\.com/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(?P<number>\d+)  # Markdown PR link
            |                                                                                       # Or
            :(?:pr|pull):`(?P<rst_number>\d+)`                                                     # RST PR role
            |                                                                                       # Or
            \B\#(?P<bare_number>\d+)\b                                                             # Bare reference
            """,
            text,
            flags=re.VERBOSE,
        )
    )


def _markdown_prose(content: str) -> list[str]:
    prose: list[str] = []
    for child, _ in markdown_visible_children(MarkdownIt().parse(content)):
        if child is None:
            continue
        if child.type == "text":
            prose.append(child.content)
        elif child.type == "link_open" and isinstance(destination := child.attrGet("href"), str):
            prose.append(destination)
        elif child.type == "code_inline" and prose and prose[-1].endswith((":pr:", ":pull:")):
            prose.append(f":pr:`{child.content}`")
    return prose


def _rst_prose(content: str) -> list[str]:
    lines = content.splitlines()
    hidden = _rst_hidden_lines(lines)
    return [_RE_RST_INLINE_LITERAL.sub("", line) for index, line in enumerate(lines) if index not in hidden]


def _rst_hidden_lines(lines: list[str]) -> set[int]:
    hidden: set[int] = set()
    for index, line in enumerate(lines):
        if index in hidden:
            continue
        stripped = line.lstrip()
        directive = stripped.startswith((".. code-block::", ".. code::", ".. sourcecode::"))
        comment = _rst_comment(stripped)
        if directive or comment:
            hidden.add(index)
        if not (directive or comment or stripped.rstrip().endswith("::")):
            continue
        cursor = index + 1
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        while cursor < len(lines) and (not lines[cursor].strip() or _indent_width(lines[cursor]) > _indent_width(line)):
            hidden.add(cursor)
            cursor += 1
    return hidden


def _rst_comment(line: str) -> bool:
    if not line.startswith(".. "):
        return False
    first = line[3:].split(maxsplit=1)
    return not first or not first[0].endswith("::")


def _credit_prose(content: str, extension: str) -> str:
    if extension == ".md":
        return _markdown_credit_prose(content)
    lines = content.splitlines(keepends=True)
    for index in _rst_hidden_lines(lines):
        lines[index] = "\0" * len(lines[index])
    return _RE_RST_INLINE_LITERAL.sub(lambda match: "\0" * len(match.group()), "".join(lines))


def _markdown_credit_prose(content: str) -> str:
    return " ".join(block for block, _ in _markdown_credit_blocks(content))


def _markdown_credit_anchor(content: str) -> int:
    blocks = _markdown_credit_blocks(content)
    markers = list(_RE_AUTHOR_MARKER.finditer(" ".join(block for block, _ in blocks)))
    if len(markers) > 1:
        msg = "split multiple credited changes into separate fragments"
        raise ValueError(msg)
    limits = accumulate(len(block) + 1 for block, _ in blocks)
    end_line = next(end for limit, (_, end) in zip(limits, blocks, strict=True) if markers[0].end() < limit)
    return sum(map(len, content.splitlines(keepends=True)[:end_line]))


def _markdown_credit_blocks(content: str) -> list[tuple[str, int]]:
    blocks: list[tuple[str, int]] = []
    children: list[Token] = []
    end_line = 0
    for child, line in markdown_visible_children(MarkdownIt().parse(content)):
        if child is None:
            blocks.append((_markdown_credit_children(children), end_line))
            children = []
        else:
            children.append(child)
            end_line = line
    blocks.append((_markdown_credit_children(children), end_line))
    return blocks


def _markdown_credit_children(children: list[Token]) -> str:
    prose: list[str] = []
    link_destination: str | None = None
    link_text: list[str] = []
    link_plain = True
    for child in children:
        if child.type == "link_open" and isinstance(destination := child.attrGet("href"), str):
            link_destination = destination
            link_text = []
            link_plain = True
        elif child.type == "link_close" and link_destination is not None:
            if link_plain and link_text:
                prose.append(f"[{''.join(link_text)}]({link_destination})")
            link_destination = None
        elif child.type == "text":
            (link_text if link_destination is not None else prose).append(
                child.content if link_destination is not None else child.content.replace("[", "\0")
            )
        elif link_destination is not None and child.type not in {"em_open", "em_close", "strong_open", "strong_close"}:
            link_plain = False
        elif child.type == "code_inline" and prose and prose[-1].endswith(":user:"):
            prose.append(f"`{child.content}`")
        elif child.type in {"softbreak", "hardbreak"} or (
            child.type == "html_inline"
            and re.fullmatch(
                r"""
                <(?P<name>br|hr)  # HTML line or horizontal break
                (?P<attributes>(?:[^>"']|"[^"]*"|'[^']*')*)>  # Attributes may contain quoted >
                """,
                child.content,
                flags=re.VERBOSE | re.IGNORECASE,
            )
            is not None
        ):
            prose.append(" ")
    return "".join(prose)


def _append_pull_request_link(
    content: str, target: _LinkTarget, credit: str | None, *, anchor: int | None = None
) -> str:
    link = _pull_request_link(target.repository, target.number, target.fragment.suffix)
    if anchor is None:
        before, after = _split_trailing_code(content, target.fragment.suffix)
    else:
        before = content[:anchor].rstrip()
        after = content[len(before) :]
    if not before:
        opening, _, body = after.partition("\n")
        suffix = f"{link} by {credit}" if credit is not None else link
        return f"{opening[:-2]} {suffix}::\n{body.rstrip()}"
    content = f"{before.removesuffix('.')} {link}"
    if credit is not None:
        content += f" by {credit}"
    return f"{content}{'' if target.knope else '.'}{after}"


def _split_trailing_code(content: str, suffix: str) -> tuple[str, str]:
    lines = content.splitlines(keepends=True)
    if suffix == ".md" and (opening := _final_fence_opening(lines)) is not None:
        position = sum(map(len, lines[:opening]))
        before = content[:position].rstrip()
        return before, content[len(before) :]
    if suffix == ".md":
        visible_ends = [
            token.map[1] for token in MarkdownIt().parse(content) if token.type == "inline" and token.map is not None
        ]
        if visible_ends and any(line.strip() for line in lines[visible_ends[-1] :]):
            position = sum(map(len, lines[: visible_ends[-1]]))
            before = content[:position].rstrip()
            return before, content[len(before) :]
    if suffix == ".rst" and (opening := _trailing_rst_code_opening(lines)) is not None:
        position = sum(map(len, lines[:opening]))
        before = content[:position].rstrip()
        return before, content[len(before) :]
    return content, ""


def _trailing_rst_code_opening(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not (
            stripped.startswith((".. code-block::", ".. code::", ".. sourcecode::"))
            or stripped.rstrip().endswith("::")
            or _rst_comment(stripped)
        ):
            continue
        body = [following for following in lines[index + 1 :] if following.strip()]
        if all(_indent_width(following) > _indent_width(line) for following in body):
            return index
    return None


def _indent_width(line: str) -> int:
    expanded = line.expandtabs()
    return len(expanded) - len(expanded.lstrip())


def _final_fence_opening(lines: list[str]) -> int | None:
    fence: tuple[int, str, int] | None = None
    max_fence_indent: Final = 3
    for index, line in enumerate(lines):
        if len(line) - len(line.lstrip(" ")) > max_fence_indent:
            continue
        stripped = line.strip()
        if not stripped.startswith(("```", "~~~")):
            continue
        width = len(stripped) - len(stripped.lstrip(stripped[0]))
        if fence is None:
            fence = index, stripped[0], width
        elif stripped == fence[1] * len(stripped) and width >= fence[2]:
            if index == len(lines) - 1:
                return fence[0]
            fence = None
    if fence is not None:
        msg = "unclosed Markdown code fence in changelog fragment"
        raise ValueError(msg)
    return None


def _pull_request_link(repository: str, number: str, extension: str) -> str:
    return f"(:pr:`{number}`)" if extension == ".rst" else f"([#{number}]({_pull_request_url(repository, number)}))"


def _author_credit(author: str, extension: str) -> str:
    return f":user:`{author}`" if extension == ".rst" else f"[@{author}](https://github.com/{author})"


def _pull_request_url(repository: str, number: str) -> str:
    return f"https://github.com/{repository}/pull/{number}"


__all__ = [
    "add_pull_request_links",
    "has_hand_written_credit",
    "has_hand_written_pull_request_link",
]
