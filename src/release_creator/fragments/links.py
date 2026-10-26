"""Associate named Towncrier fragments with merged pull requests."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # Shared regexes and dataclass decorators resolve during module load.
from __future__ import annotations

lazy import re
lazy from collections.abc import Iterator, Mapping
lazy from dataclasses import dataclass
lazy from pathlib import Path
lazy from string import punctuation
lazy from typing import Final, Literal

lazy from markdown_it import MarkdownIt
lazy from markdown_it.token import Token

lazy from release_creator.explain import counted, explain
lazy from release_creator.fragments.git import FragmentCommit
lazy from release_creator.fragments.knope import changeset_parts
lazy from release_creator.fragments.names import pending_changesets, pending_fragments
lazy from release_creator.fragments.pull_requests import PullRequest, PullRequestCredit
lazy from release_creator.fragments.shape import markdown_visible_children

_RE_AUTHOR_MARKER: Final = re.compile(
    r"""
    (?<!\w)by\s+                 # Credit marker after the start or a non-word character, and following whitespace
    (?=(?:\*{1,2})?(?:\[@|:user:`|`@|@[A-Za-z0-9-]))  # Supported author syntax, optionally emphasized in RST
    """,
    re.VERBOSE | re.IGNORECASE,
)
_RE_USER_ROLE: Final = re.compile(
    r"""
    :user:`[^`]+`  # GitHub user role with any content, with or without a credit marker
    """,
    re.VERBOSE | re.IGNORECASE,
)
_RE_HTML_ANCHOR: Final = re.compile(
    r"""
    <a\s(?:[^>"']|"[^"]*"|'[^']*')*?                 # Anchor tag; attributes may contain quoted >
    (?<=\s)href\s*=\s*(?P<href>"[^"]*"|'[^']*'|[^\s"'>]+)  # Quoted or bare link target
    """,
    re.VERBOSE | re.IGNORECASE,
)
_RE_TRAILING_CREDIT: Final = re.compile(
    r"""
    (?:^|\s)by\s+                     # Credit marker at a word boundary
    (?:\\.|[^\s.!?\\])(?:\\.|[^.!?\\])*  # Credited text; escaped punctuation does not end the sentence
    [.!?]?$                            # Up to the end of the entry
    """,
    re.VERBOSE,
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
    pull_requests: Mapping[str, PullRequest],
    *,
    commits: Mapping[str, FragmentCommit],
    mode: _LinkMode = "towncrier",
) -> None:
    """Keep fragment links and credits tied to their introducing pull requests.

    A fragment without a pull request is credited to its introducing commit's author, and one without either, or whose
    author gets no credit, is left unchanged.
    """
    fragments = pending_changesets(directory) if mode == "knope" else pending_fragments(directory)
    if not fragments:
        explain(f"No pending fragments in {directory.as_posix()}, nothing to link")
        return
    explain(
        f"Linking {counted(len(fragments), 'pending fragment')} in {directory.as_posix()} to {repository} pull requests"
    )
    updates: list[tuple[Path, str]] = [
        (fragment, _link_fragment(fragment, repository, pull_requests, commits, mode=mode)) for fragment in fragments
    ]
    for fragment, content in updates:
        fragment.write_text(content, encoding="utf-8")


def _link_fragment(
    fragment: Path,
    repository: str,
    pull_requests: Mapping[str, PullRequest],
    commits: Mapping[str, FragmentCommit],
    *,
    mode: _LinkMode,
) -> str:
    content = fragment.read_text(encoding="utf-8")
    commit = commits.get(fragment.name)
    if (pull_request := pull_requests.get(fragment.name)) is not None:
        number, credited = pull_request.number, pull_request.credits
    elif commit is not None and commit.credits:
        number, credited = None, commit.credits
        explain(
            f"Credited {fragment.name} to {_credit_names(credited)} "
            f"(commit {commit.sha[:7]} has no merged pull request)"
        )
    else:
        explain(
            f"Kept {fragment.name}: no introducing commit found"
            if commit is None
            else f"Kept {fragment.name}: commit {commit.sha[:7]} has no merged pull request and an uncredited author"
        )
        return content
    target = _LinkTarget(
        fragment=fragment,
        repository=repository,
        number=number,
        credits=credited,
        knope=mode == "knope",
    )
    if mode == "knope":
        frontmatter, heading, remainder = changeset_parts(fragment, content)
        linked = f"{frontmatter}# {_link_text(heading, target)}{remainder}"
    else:
        linked = f"{_link_text(content.rstrip(), target)}\n"
    if number is not None:
        explain(_pull_request_outcome(fragment.name, number, credited, changed=linked != content))
    return linked


def _pull_request_outcome(name: str, number: str, credited: tuple[PullRequestCredit, ...], *, changed: bool) -> str:
    if not changed:
        return f"Kept {name}: already links #{number}"
    if not credited:
        return f"Linked {name} -> #{number} (no credit: only AI assistants authored it)"
    return f"Linked {name} -> #{number} (credit {_credit_names(credited)})"


def _credit_names(credited: tuple[PullRequestCredit, ...]) -> str:
    return ", ".join(f"@{credit.name}" if credit.linked else credit.name for credit in credited)


@dataclass(frozen=True, kw_only=True)
class _LinkTarget:
    fragment: Path
    repository: str
    number: str | None
    credits: tuple[PullRequestCredit, ...]
    knope: bool


def _link_text(
    content: str,
    target: _LinkTarget,
) -> str:
    fragment = target.fragment
    if (number := target.number) is None:
        return _append_pull_request_link(content, target, _credit_list(target.credits, fragment.suffix))
    linked = _has_pull_request_link(content, target.repository, number, fragment.suffix)
    if not target.credits:
        return content if linked else _append_pull_request_link(content, target, None)
    credit = _credit_list(target.credits, fragment.suffix)
    if linked:
        before, after = _split_trailing_code(content, fragment.suffix)
        if _RE_TRAILING_CREDIT.search(before) is not None:
            return content
        suffix = "" if target.knope else "."
        return f"{before.removesuffix('.')} by {credit}{suffix}{after}"
    return _append_pull_request_link(content, target, credit)


def _credit_list(credited: tuple[PullRequestCredit, ...], extension: str) -> str:
    names = [
        _author_credit(credit.name, extension) if credit.linked else _escape_name(credit.name) for credit in credited
    ]
    return f"{', '.join(names[:-1])} and {names[-1]}" if len(names) > 1 else names[0]


def _escape_name(name: str) -> str:
    # Markdown and reStructuredText both render a backslash-escaped ASCII punctuation character literally.
    return "".join(f"\\{character}" if character in punctuation else character for character in name)


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
            flags=re.VERBOSE | re.IGNORECASE,
        )
    )


def _markdown_prose(content: str) -> list[str]:
    prose: list[str] = []
    anchor = ""
    for child in _markdown_prose_children(content):
        if anchor and child.type in {"text", "code_inline"} and child.content.strip():
            prose.append(anchor)
            anchor = ""
        if child.type == "text":
            prose.append(child.content)
        elif child.type == "link_open" and isinstance(destination := child.attrGet("href"), str):
            prose.append(destination)
        elif child.type == "html_inline" and (match := _RE_HTML_ANCHOR.match(child.content)) is not None:
            anchor = match["href"].strip("\"'")
        elif child.type == "html_inline" and re.fullmatch(r"</a\s*>", child.content, re.IGNORECASE) is not None:
            anchor = ""
        elif child.type == "code_inline" and prose and prose[-1].casefold().endswith((":pr:", ":pull:")):
            prose.append(f":pr:`{child.content}`")
    return prose


def _markdown_prose_children(content: str) -> Iterator[Token]:
    for child, _ in markdown_visible_children(MarkdownIt().parse(content)):
        if child is not None and child.type == "html_block":
            yield from child.children or ()
        elif child is not None:
            yield child


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
    return " ".join(_markdown_credit_blocks(content))


def _markdown_credit_blocks(content: str) -> list[str]:
    blocks: list[str] = []
    children: list[Token] = []
    for child, _ in markdown_visible_children(MarkdownIt().parse(content)):
        if child is None:
            blocks.append(_markdown_credit_children(children))
            children = []
        elif child.type != "html_block":
            children.append(child)
    blocks.append(_markdown_credit_children(children))
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
        elif child.type == "code_inline" and link_destination is not None:
            link_text.append(child.content)
        elif link_destination is not None and child.type not in {"em_open", "em_close", "strong_open", "strong_close"}:
            link_plain = False
        elif child.type == "code_inline" and prose and prose[-1].casefold().endswith(":user:"):
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


def _append_pull_request_link(content: str, target: _LinkTarget, credit: str | None) -> str:
    link = (
        None if target.number is None else _pull_request_link(target.repository, target.number, target.fragment.suffix)
    )
    addition = " ".join(part for part in (link, None if credit is None else f"by {credit}") if part is not None)
    before, after = _split_trailing_code(content, target.fragment.suffix)
    if not before:
        opening, _, body = after.partition("\n")
        return f"{opening[:-2]} {addition}::\n{body.rstrip()}"
    return f"{before.removesuffix('.')} {addition}{'' if target.knope else '.'}{after}"


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


def has_unclosed_code_fence(content: str) -> bool:
    """Detect a Markdown code fence that would swallow the link and credit appended after it.

    :param content: Markdown fragment text.
    :returns: Whether a fence opens without a matching close.
    """
    return _scan_fences(content.splitlines(keepends=True))[1]


def _final_fence_opening(lines: list[str]) -> int | None:
    return _scan_fences(lines)[0]


def _scan_fences(lines: list[str]) -> tuple[int | None, bool]:
    fence: tuple[int, str, int] | None = None
    final: int | None = None
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
                final = fence[0]
            fence = None
    return final, fence is not None


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
    "has_unclosed_code_fence",
]
