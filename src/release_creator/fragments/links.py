"""Associate named Towncrier fragments with merged pull requests."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # Shared regexes and dataclass decorators resolve during module load.
from __future__ import annotations

lazy import re
lazy from dataclasses import dataclass
lazy from pathlib import Path
lazy from typing import Final, Literal

lazy from markdown_it import MarkdownIt
lazy from markdown_it.token import Token

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
    \ <https://(?:www\.)?github\.com/(?P=link_handle)/?>`_  # Matching profile URL
    """,
    re.VERBOSE | re.IGNORECASE,
)
_RE_AUTHOR_SEPARATOR: Final = re.compile(
    r"""
    ^[ \t]*(?P<separator>,(?:[ \t]*and)?|and)[ \t]*  # Continue a shared author list
    """,
    re.VERBOSE,
)
_RE_HTML_TAG: Final = re.compile(
    r"""
    <\s*(?P<closing>/)?\s*(?P<name>code|kbd|pre|samp)\b[^>]*>  # Hidden HTML literal element
    """,
    re.VERBOSE | re.IGNORECASE,
)
_RE_HTML_LINK: Final = re.compile(
    r"""
    <a\b[^>]*\bhref\s*=\s*(?P<quote>["'])
    (?P<href>https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/\d+)
    (?P=quote)[^>]*>  # HTML pull request anchor
    """,
    re.VERBOSE | re.IGNORECASE,
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
    linked = _has_pull_request_link(content, target.repository, target.number, fragment.suffix)
    if not target.knope and fragment_number(fragment) is None and linked:
        msg = f"pull request already linked in {fragment}"
        raise ValueError(msg)
    if (match := _RE_AUTHOR_MARKER.search(_credit_prose(content, fragment.suffix))) is not None:
        handles = {handle.casefold() for handle in _credited_handles(content[match.end() :], fragment.suffix)}
        handle = target.author.handle.casefold()
        if target.author.handle == "ghost":
            msg = f"cannot verify explicit credit for deleted pull request author in {fragment}"
            raise ValueError(msg)
        if target.author.is_bot and handle in handles:
            msg = f"bot author @{target.author.handle} must not be credited in {fragment}"
            raise ValueError(msg)
        if not target.author.is_bot and handle not in handles:
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


def _has_pull_request_link(content: str, repository: str, number: str, extension: str) -> bool:
    return any(
        (match["repository"] == repository and match["number"] == number) or match["rst_number"] == number
        for text in (_markdown_prose(content) if extension == ".md" else _rst_prose(content))
        for match in _RE_PULL_REQUEST_LINK.finditer(text)
    )


def _markdown_prose(content: str) -> list[str]:
    prose: list[str] = []
    hidden = 0
    for token in MarkdownIt().parse(content):
        for child in token.children or ():
            if child.type == "html_inline":
                if match := _RE_HTML_TAG.fullmatch(child.content):
                    hidden = max(0, hidden - 1) if match["closing"] else hidden + 1
                elif not hidden and (match := _RE_HTML_LINK.fullmatch(child.content)):
                    prose.append(match["href"])
            elif child.type == "text" and not hidden:
                prose.append(child.content)
            elif child.type == "link_open" and not hidden and isinstance(destination := child.attrGet("href"), str):
                prose.append(destination)
            elif child.type == "code_inline" and not hidden and prose and prose[-1].endswith((":pr:", ":pull:")):
                prose.append(f":pr:`{child.content}`")
    return prose


def _rst_prose(content: str) -> list[str]:
    lines = content.splitlines()
    hidden = _rst_hidden_lines(lines)
    return [_without_rst_inline_literals(line) for index, line in enumerate(lines) if index not in hidden]


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
        if cursor >= len(lines) or _indent_width(lines[cursor]) <= _indent_width(line):
            continue
        while cursor < len(lines) and (not lines[cursor].strip() or _indent_width(lines[cursor]) > _indent_width(line)):
            hidden.add(cursor)
            cursor += 1
    return hidden


def _rst_comment(line: str) -> bool:
    if line.strip() == "..":
        return True
    if not line.startswith(".. "):
        return False
    first = line[3:].split(maxsplit=1)
    return not first or not first[0].endswith("::")


def _credit_prose(content: str, extension: str) -> str:
    lines = content.splitlines(keepends=True)
    if extension == ".md":
        return _markdown_credit_prose(content, lines)
    for index in _rst_hidden_lines(lines):
        lines[index] = "\0" * len(lines[index])
    return _mask_delimited("".join(lines), "``", "``")


def _markdown_credit_prose(content: str, lines: list[str]) -> str:
    tokens = MarkdownIt().parse(content)
    visible_lines = {
        index for token in tokens if token.type == "inline" and token.map is not None for index in range(*token.map)
    }
    for index in range(len(lines)):
        if index not in visible_lines:
            lines[index] = "\0" * len(lines[index])
    masked = list(_mask_delimited(_mask_markdown_code("".join(lines)), "<!--", "-->"))
    for start, end in _markdown_hidden_spans(content, "".join(masked), tokens):
        masked[start:end] = "\0" * (end - start)
    for start, end in _markdown_target_spans("".join(masked)):
        masked[start:end] = "\0" * (end - start)
    return "".join(masked)


def _markdown_hidden_spans(content: str, visible: str, tokens: list[Token]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    html_literal_start: int | None = None
    for token in tokens:
        for child in token.children or ():
            if child.type == "html_inline" and not child.content.startswith("<!--"):
                start = _visible_start(content, visible, child.content, cursor)
                spans.append((start, start + len(child.content)))
                html_literal_start = _html_literal_span(child.content, start, html_literal_start, spans)
                cursor = start + len(child.content)
            elif child.type == "image":
                marker = f"![{child.content}]"
                start = _visible_start(content, visible, marker, cursor)
                spans.append((start, start + len(marker)))
                cursor = start + len(marker)
    return spans


def _visible_start(content: str, visible: str, marker: str, cursor: int) -> int:
    start = content.index(marker, cursor)
    while visible[start] == "\0":
        start = content.index(marker, start + 1)
    return start


def _markdown_target_spans(content: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    while (opening := content.find("](", cursor)) >= 0:
        line_start = content.rfind("\n", 0, opening) + 1
        label_start = _markdown_label_start(content, line_start, opening)
        if (
            label_start >= 0
            and (end := _markdown_target_end(content, opening + 2)) is not None
            and any(
                token.type == "link_open"
                for block in MarkdownIt().parse(content[label_start : end + 1])
                for token in (block.children or ())[:1]
            )
        ):
            spans.append((opening + 2, end))
        cursor = opening + 2
    return spans


def _markdown_label_start(content: str, line_start: int, closing: int) -> int:
    depth = 1
    for index in range(closing - 1, line_start - 1, -1):
        if _escaped(content, index):
            continue
        if content[index] == "]":
            depth += 1
        elif content[index] == "[":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _markdown_target_end(content: str, start: int) -> int | None:
    depth = 1
    quote = ">" if content[start : start + 1] == "<" else ""
    escaped = False
    for index in range(start, len(content)):
        char = content[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif quote:
            quote = "" if char == quote else quote
        elif char in "\"'" and content[index - 1].isspace() and depth == 1:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _html_literal_span(content: str, start: int, opened: int | None, spans: list[tuple[int, int]]) -> int | None:
    if (match := _RE_HTML_TAG.fullmatch(content)) is None:
        return opened
    if match["closing"] and opened is not None:
        spans.append((opened, start))
        return None
    return opened if match["closing"] else start + len(content)


def _mask_delimited(content: str, opening: str, closing: str) -> str:
    masked = list(content)
    cursor = 0
    while (start := content.find(opening, cursor)) >= 0:
        if (end := content.find(closing, start + len(opening))) < 0:
            break
        end += len(closing)
        masked[start:end] = "\0" * (end - start)
        cursor = end
    return "".join(masked)


def _mask_markdown_code(content: str) -> str:
    masked = list(content)
    cursor = 0
    while (start := content.find("`", cursor)) >= 0:
        if _escaped(content, start):
            cursor = start + 1
            continue
        width = len(content[start:]) - len(content[start:].lstrip("`"))
        fence = "`" * width
        end = content.find(fence, start + width)
        while end >= 0 and (
            (end > 0 and content[end - 1] == "`") or (end + width < len(content) and content[end + width] == "`")
        ):
            end = content.find(fence, end + width)
        if end < 0:
            cursor = start + width
            continue
        end += width
        masked[start:end] = "\0" * (end - start)
        cursor = end
    return "".join(masked)


def _escaped(content: str, index: int) -> bool:
    return bool((index - len(content[:index].rstrip("\\"))) % 2)


def _without_rst_inline_literals(line: str) -> str:
    parts: list[str] = []
    start = 0
    while (opening := line.find("``", start)) >= 0:
        if (closing := line.find("``", opening + 2)) < 0:
            break
        parts.append(line[start:opening])
        start = closing + 2
    parts.append(line[start:])
    return "".join(parts)


def _append_pull_request_link(content: str, target: _LinkTarget, author: str | None) -> str:
    link = _pull_request_link(target.repository, target.number, target.fragment.suffix)
    before, after = _split_trailing_code(content, target.fragment.suffix)
    if not before:
        suffix = f"{link}"
        if author is not None:
            suffix += f" by {_author_credit(author, target.fragment.suffix)}"
        opening, _, body = after.partition("\n")
        if target.fragment.suffix == ".rst" and opening.endswith("::") and not opening.lstrip().startswith(".. "):
            return f"{opening[:-2]} {suffix}::\n{body.rstrip()}"
        return f"{after.rstrip()}\n\n{suffix}{'' if target.knope else '.'}"
    content = f"{before.removesuffix('.')} {link}"
    if author is not None:
        content += f" by {_author_credit(author, target.fragment.suffix)}"
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
        if not visible_ends and content.strip():
            return "", content
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
        if (body or _rst_comment(stripped)) and all(
            _indent_width(following) > _indent_width(line) for following in body
        ):
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


def _credited_handles(credit_text: str, extension: str) -> set[str]:
    pattern = _RE_RST_USER if extension == ".rst" else MARKDOWN_AUTHOR
    remaining = credit_text.lstrip()
    handles: set[str] = set()
    while (author := pattern.match(remaining)) is not None:
        handles.add(author["handle"] or author["link_handle"] if extension == ".rst" else author["handle"])
        remaining = remaining[author.end() :]
        if (separator := _RE_AUTHOR_SEPARATOR.match(remaining)) is None:
            break
        remaining = remaining[separator.end() :]
    return handles


def _pull_request_url(repository: str, number: str) -> str:
    return f"https://github.com/{repository}/pull/{number}"


__all__ = [
    "add_pull_request_links",
]
