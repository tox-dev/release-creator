"""Render release notes from tagged changelogs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from textwrap import dedent
from typing import Final

lazy import mdformat

from release_creator.categories import RELEASE_CATEGORIES
from release_creator.github import MARKDOWN_AUTHOR, validate_repository

_RE_RELEASE_PULL: Final = re.compile(
    r"""
    https://github\.com/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(?P<number>\d+)  # PR link
    """,
    re.VERBOSE,
)
_RE_GITHUB_CREDIT: Final = re.compile(
    r"""
    \bby\s+                      # Author credit marker
    (?P<credits>.*)$              # GitHub mentions following the marker
    """,
    re.VERBOSE,
)
_RE_GITHUB_HANDLE: Final = re.compile(
    r"""
    @(?P<handle>[A-Za-z0-9-]+)   # GitHub mention
    """,
    re.VERBOSE,
)
_RE_GENERATED_PR_AUTHOR: Final = re.compile(
    r"""
    \bby\s+@(?P<handle>[A-Za-z0-9-]+)  # GitHub generated PR author
    (?P<bot>\[bot\])?                 # Bot accounts are not credited
    \s+in\s+https://github\.com/
    (?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)  # Repository in the generated link
    /pull/(?P<number>\d+)              # Pull request number
    """,
    re.VERBOSE,
)
_RE_RST_VERSION: Final = re.compile(
    r"""
    ^(?:
        (?P<tag>v?\d+(?:\.\d+){1,3}(?:(?:a|b|rc)\d*)?)\ \((?P<date>[^)]+)\)  # Version and date
        |
        `(?P<link_tag>v?\d+(?:\.\d+){1,3}(?:(?:a|b|rc)\d*)?)\ <https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/tree/
        (?P=link_tag)>`_(?:\ -\ (?P<link_date>\d{4}-\d{2}-\d{2}))?  # Linked version, with optional date
    )$
    """,
    re.VERBOSE,
)
_RE_RST_HEADING_UNDERLINE: Final = re.compile(
    r"""
    (?P<underline>[-*=~^]{3,})  # RST heading adornment
    """,
    re.VERBOSE,
)
_RE_MARKDOWN_VERSION: Final = re.compile(
    r"""
    ^(?P<level>\#{2,3})\          # Markdown version heading level
    (?P<open>\[)?                   # Optional Keep a Changelog link bracket
    (?P<tag>v?\d+(?:\.\d+){1,3}(?:(?:a|b|rc)\d*)?)  # Release version, including historical prereleases
    (?(open)\])                     # Close the optional bracket
    (?:\ \([^)]+\)|\ -\ [^\n]+)? # Parenthesized or dash-separated date
    $                               # End of heading
    """,
    re.VERBOSE,
)
_RE_MARKDOWN_VERSION_ANCHOR: Final = re.compile(
    r"""
    ^<a\ name="release-             # Version anchor prefix
    (?P<version>v?\d+(?:-\d+){1,3}(?:(?:a|b|rc)\d*)?)  # Version encoded for an anchor
    "></a>$                         # Anchor terminator
    """,
    re.VERBOSE,
)
_RE_MARKDOWN_LINK_DEFINITION: Final = re.compile(
    r"""
    ^\[(?P<version>v?\d+(?:\.\d+){1,3}(?:(?:a|b|rc)\d*)?|unreleased)\]:  # Version reference
    \s+https://github\.com/[^\s]+                    # GitHub destination
    $                                                   # End of definition
    """,
    re.VERBOSE | re.IGNORECASE,
)


@dataclass(frozen=True, kw_only=True)
class ReleaseContext:
    """Links and identity for one GitHub Release."""

    tag: str
    repository: str
    previous: str | None = None
    artifact_url: str | None = None
    artifact_label: str = "PyPI release"
    package: str | None = None


def render_markdown(changelog: str, context: ReleaseContext, generated_notes: str | None = None) -> str:
    """Render one Markdown release section for GitHub without wrapped list items.

    :param changelog: Tagged Markdown changelog.
    :param context: Repository and release links.
    :param generated_notes: GitHub-generated text used only for verified contributor credits.
    :returns: The complete GitHub Release body.

    """
    _validate_context(context)
    notes = mdformat.text(_extract_body(changelog, context), options={"wrap": "no"}, extensions={"gfm"}).strip()
    return _finish(notes, context, generated_notes)


def render_rst(
    changelog: str, context: ReleaseContext, issue_role: str = "issue", generated_notes: str | None = None
) -> str:
    """Render one reStructuredText release section for GitHub.

    :param changelog: Tagged reStructuredText changelog.
    :param context: Repository and release links.
    :param issue_role: Whether issue roles link to issues or pull requests.
    :param generated_notes: GitHub-generated text used only for verified contributor credits.
    :returns: The complete GitHub Release body.
    :raises ValueError: The issue role must name a GitHub issue or pull request.
    """
    _validate_context(context)
    if context.package is not None:
        msg = "package selection requires a Markdown changelog"
        raise ValueError(msg)
    if issue_role not in {"issue", "pull"}:
        msg = f"invalid issue role: {issue_role}"
        raise ValueError(msg)
    notes = mdformat.text(
        _extract_rst_body(changelog, context, issue_role), options={"wrap": "no"}, extensions={"gfm"}
    ).strip()
    return _finish(notes, context, generated_notes)


def _finish(notes: str, context: ReleaseContext, generated_notes: str | None) -> str:
    if generated_notes is not None:
        _verify_authors(notes, generated_notes, context)
        if contributors := _new_contributors(generated_notes, context):
            notes = f"{notes}\n\n{contributors}" if notes else contributors
    if context.artifact_url is not None:
        link = f"[{context.artifact_label}]({context.artifact_url})"
        notes = f"{notes}\n\n{link}" if notes else link
    comparison = (
        f"compare/{context.previous}...{context.tag}" if context.previous is not None else f"commits/{context.tag}"
    )
    if notes:
        notes += "\n\n"
    return f"{notes}**Full Changelog**: https://github.com/{context.repository}/{comparison}\n"


def _verify_authors(notes: str, generated_notes: str, context: ReleaseContext) -> None:
    generated_authors, generated_bots = _generated_pr_authors(generated_notes, context.repository)
    for number, entries in _release_entries(notes, context.repository).items():
        if number not in generated_authors:
            if any(not handles for handles, _ in entries):
                msg = f"generated notes have no author for pull request #{number}"
                raise ValueError(msg)
            continue
        if (bot := generated_bots.get(number)) is not None and any(bot in handles for handles, _ in entries):
            msg = f"changelog credit for pull request #{number} must not name bot @{bot}"
            raise ValueError(msg)
        if bot is None and generated_authors[number] is None and any(not attributed for _, attributed in entries):
            msg = f"changelog has no credit for pull request #{number} with an unavailable author"
            raise ValueError(msg)
        if (author := generated_authors[number]) is not None and any(author not in handles for handles, _ in entries):
            msg = f"changelog credit for pull request #{number} does not include @{author}"
            raise ValueError(msg)


def _generated_pr_authors(generated_notes: str, repository: str) -> tuple[dict[str, str | None], dict[str, str]]:
    authors: dict[str, str | None] = {}
    bots: dict[str, str] = {}
    in_new_contributors = False
    for line in generated_notes.splitlines():
        if line.startswith(("## ", "### ")):
            in_new_contributors = line.removeprefix("### ").removeprefix("## ") == "New Contributors"
        if in_new_contributors:
            continue
        match = _RE_GENERATED_PR_AUTHOR.search(line)
        if match is not None and match["repository"] != repository:
            match = None
        for link in _RE_RELEASE_PULL.finditer(line):
            if link["repository"] != repository:
                continue
            number = link["number"]
            author = None if match is None or match["bot"] is not None else match["handle"]
            if match is not None and match["bot"] is not None:
                bots[number] = match["handle"]
            if number in authors and authors[number] != author:
                msg = f"conflicting generated authors for pull request #{number}"
                raise ValueError(msg)
            authors[number] = author
    return authors, bots


def _release_entries(notes: str, repository: str) -> dict[str, list[tuple[set[str], bool]]]:
    entries: dict[str, list[tuple[set[str], bool]]] = {}
    for line in notes.splitlines():
        pull_requests = [
            match["number"] for match in _RE_RELEASE_PULL.finditer(line) if match["repository"] == repository
        ]
        if not pull_requests:
            continue
        credit_text = _RE_GITHUB_CREDIT.search(line)
        handles = (
            {match["handle"] for match in _RE_GITHUB_HANDLE.finditer(credit_text["credits"])}
            if credit_text is not None
            else set()
        )
        for number in pull_requests:
            entries.setdefault(number, []).append((
                handles,
                credit_text is not None and bool(credit_text["credits"].strip(" .,;")),
            ))
    return entries


def _new_contributors(generated_notes: str, context: ReleaseContext) -> str:
    if (
        section := re.search(
            r"""
            ^\#{2,3}\ New\ Contributors\s*\n  # GitHub uses H2 or H3 for this section
            (?P<entries>.*?)               # Contributor bullets
            (?=^\#{1,6}\ |\Z)              # Next heading or end of body
            """,
            generated_notes,
            re.MULTILINE | re.DOTALL | re.VERBOSE,
        )
    ) is None:
        return ""
    entries = [
        f"- @{match['handle']} made their first contribution in {_contributor_reference(match, context.repository)}"
        for line in section["entries"].splitlines()
        if (
            match := re.fullmatch(
                r"""
                [-*]\ @(?P<handle>[A-Za-z0-9-]+)  # Generated contributor bullet
                \ made\ their\ first\ contribution\ in\s+
                (?P<reference>
                    \#                            # Short PR reference
                    |https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+/pull/  # GitHub PR URL
                )
                (?P<number>\d+)                   # First PR number
                """,
                line.strip(),
                re.VERBOSE,
            )
        )
    ]
    if not entries:
        return ""
    anchor = f"release-{context.tag.replace('.', '-').replace('/', '-')}-new-contributors"
    return f'<a name="{anchor}"></a>\n\n### New Contributors\n\n{"\n".join(entries)}'


def _contributor_reference(match: re.Match[str], repository: str) -> str:
    prefix = match["reference"] if match["reference"] != "#" else f"https://github.com/{repository}/pull/"
    return f"[#{match['number']}]({prefix}{match['number']})"


def _extract_rst_body(changelog: str, context: ReleaseContext, issue_role: str) -> str:
    lines = [line for line in changelog.splitlines() if not _is_comparison_line(line)]
    headings = [
        index
        for index, line in enumerate(lines)
        if (match := _RE_RST_VERSION.fullmatch(line.strip()))
        and (match["tag"] or match["link_tag"]).removeprefix("v") == context.tag.removeprefix("v")
    ]
    if len(headings) != 1:
        msg = f"expected one changelog section for {context.tag}, found {len(headings)}"
        raise ValueError(msg)
    end = next(
        (index for index in range(headings[0] + 1, len(lines)) if _RE_RST_VERSION.fullmatch(lines[index].strip())),
        len(lines),
    )
    body: list[str] = []
    for block in _parse_rst_blocks(lines, headings[0] + 1, end, context.repository, issue_role):
        if isinstance(block, str):
            body.extend((block, ""))
            continue
        name, entries = block
        if entries:
            anchor = f"release-{context.tag.replace('.', '-')}-{name.lower().replace(' ', '-')}"
            body.extend((
                f'<a name="{anchor}"></a>',
                "",
                f"### {RELEASE_CATEGORIES[name]}",
                "",
                *(_convert_rst(entry, context.repository, issue_role) for entry in entries),
                "",
            ))
    return "\n".join(body).strip()


def _parse_rst_blocks(
    lines: list[str], start: int, end: int, repository: str, issue_role: str
) -> list[tuple[str, list[str]] | str]:
    blocks: list[tuple[str, list[str]] | str] = []
    entries: list[str] | None = None
    after_block = False
    nested = False
    index = start
    while index < end:
        line = lines[index].strip()
        if line and index + 1 < end and _RE_RST_HEADING_UNDERLINE.fullmatch(lines[index + 1].strip()):
            entries = []
            blocks.append((_require_category(line), entries))
            after_block = False
            nested = False
            index += 2
            continue
        if line.startswith(".. code-block:: "):
            if entries is None or not entries or lines[index].startswith(".."):
                msg = f"code block outside a release item: {line}"
                raise ValueError(msg)
            content, index = _rst_directive_content(lines, index, end)
            language = line.removeprefix(".. code-block:: ")
            entries[-1] += f"\n\n  ```{language}\n{'\n'.join(f'  {part}' for part in content.splitlines())}\n  ```"
            after_block = True
            nested = False
            continue
        if line == ".. warning::" and lines[index].startswith(".."):
            content, index = _rst_directive_content(lines, index, end)
            blocks.append(f"> **Warning:** {_convert_rst(' '.join(content.splitlines()), repository, issue_role)}")
            entries = None
            continue
        after_block, nested = _append_rst_entry(entries, lines[index], after_block=after_block, nested=nested)
        index += 1
    return blocks


def _append_rst_entry(entries: list[str] | None, raw: str, *, after_block: bool, nested: bool) -> tuple[bool, bool]:
    line = raw.strip()
    if raw.startswith("- "):
        if entries is None:
            msg = f"release item outside a category: {line}"
            raise ValueError(msg)
        entries.append(line)
        return False, False
    if line.startswith("- "):
        if entries is None or not entries:
            msg = f"release item outside a category: {line}"
            raise ValueError(msg)
        if line.startswith("- by "):
            credit = line.removeprefix("- ")
            entries[-1] += f"\n\n  {credit}" if nested or after_block else f" {credit}"
            return False, False
        entries[-1] += f"\n  {line}"
        return False, True
    if line and _RE_RST_HEADING_UNDERLINE.fullmatch(line) is None and not line.startswith(".. _"):
        if entries is None or not entries or line.startswith(".. "):
            msg = f"unexpected release text: {line}"
            raise ValueError(msg)
        entries[-1] += f"\n\n  {line}" if after_block else f" {line}"
        return False, False if after_block else nested
    return after_block or (nested and not line), nested


def _rst_directive_content(lines: list[str], index: int, end: int) -> tuple[str, int]:
    indent = len(lines[index]) - len(lines[index].lstrip())
    start = index + 1
    index = start
    while index < end and (not lines[index].strip() or len(lines[index]) - len(lines[index].lstrip()) > indent):
        index += 1
    content = dedent("\n".join(lines[start:index])).strip("\n")
    if not content.strip():
        msg = f"empty RST directive: {lines[start - 1].strip()}"
        raise ValueError(msg)
    return content, index


def _require_category(name: str) -> str:
    if name not in RELEASE_CATEGORIES:
        msg = f"unknown changelog category: {name}"
        raise ValueError(msg)
    return name


def _convert_rst(line: str, repository: str, issue_role: str) -> str:
    issue_target = "pull" if issue_role == "pull" else "issues"
    line = re.sub(
        r"""
        :PEP:`                   # Sphinx PEP role
        (?P<number>\d+)          # PEP number
        (?:\#(?P<anchor>[A-Za-z0-9_-]+))?  # Optional section anchor
        `                        # Role terminator
        """,
        lambda match: (
            f"[PEP {match['number']}](https://peps.python.org/pep-{int(match['number']):04d}/"
            f"{'#' + match['anchor'] if match['anchor'] else ''})"
        ),
        line,
        flags=re.VERBOSE | re.IGNORECASE,
    )
    line = re.sub(
        r"""
        :(?:pr|pull):`       # Pull request role
        (?P<number>\d+)       # Pull request number
        `                     # Role terminator
        """,
        lambda match: f"[#{match['number']}](https://github.com/{repository}/pull/{match['number']})",
        line,
        flags=re.VERBOSE,
    )
    line = re.sub(
        r"""
        :issue:`              # Issue role
        (?P<number>\d+)       # Issue number
        `                     # Role terminator
        """,
        lambda match: f"[#{match['number']}](https://github.com/{repository}/{issue_target}/{match['number']})",
        line,
        flags=re.VERBOSE,
    )
    line = re.sub(
        r"""
        :user:`               # GitHub user role
        (?P<handle>[A-Za-z0-9-]+)  # GitHub handle
        `                     # Role terminator
        """,
        lambda match: f"@{match['handle']}",
        line,
        flags=re.VERBOSE,
    )
    line = re.sub(
        r"""
        `@(?P<handle>[A-Za-z0-9-]+)  # Link text and GitHub handle
        \ <https://github\.com/(?P=handle)>`_  # Matching profile URL
        """,
        lambda match: f"@{match['handle']}",
        line,
        flags=re.VERBOSE,
    )
    line = re.sub(
        r"""
        `(?P<label>[^`<>]+)\ <       # RST link text and target separator
        (?P<url>https?://[^<>\s]+)  # External HTTP URL
        >`_{1,2}                    # Named or anonymous link suffix
        """,
        lambda match: f"[{match['label']}]({match['url']})",
        line,
        flags=re.VERBOSE,
    )
    line = re.sub(
        r"""
        (?<!`)               # Keep role-like text inside inline literals
        :(?:[a-z]+:)?[a-z]+:`  # RST role with optional domain
        (?:
            (?P<display>[^<>`]+)\s+<(?P<target>[^<>`]+)>  # Explicit display and target
            |
            ~?(?P<name>[^`]+)                             # Referenced name, optionally shortened
        )`
        """,
        lambda match: f"`{match['display'] or match['name'].split('.')[-1]}`",
        line,
        flags=re.VERBOSE,
    )
    line = re.sub(
        r"""
        (?<!`)``(?P<code>[^`]+)``(?!`)   # RST inline code outside Markdown fences
        """,
        r"`\g<code>`",
        line,
        flags=re.VERBOSE,
    )
    return line.replace(" - by ", " by ")


def _validate_context(context: ReleaseContext) -> None:
    if not re.fullmatch(
        r"""
        (?P<tag>[A-Za-z0-9][A-Za-z0-9_.-]*)     # Release tag or package prefix
        (?:/(?P<version>[A-Za-z0-9][A-Za-z0-9_.-]*))?  # Optional package version
        """,
        context.tag,
        re.VERBOSE,
    ):
        msg = f"invalid release tag: {context.tag}"
        raise ValueError(msg)
    if context.previous is not None and not re.fullmatch(
        r"""
        (?P<tag>[A-Za-z0-9][A-Za-z0-9_.-]*)     # Previous tag or package prefix
        (?:/(?P<version>[A-Za-z0-9][A-Za-z0-9_.-]*))?  # Optional package version
        """,
        context.previous,
        re.VERBOSE,
    ):
        msg = f"invalid previous tag: {context.previous}"
        raise ValueError(msg)
    if context.package is not None:
        if not re.fullmatch(r"(?P<package>[A-Za-z0-9][A-Za-z0-9_.-]*)", context.package, re.VERBOSE):
            msg = f"invalid package: {context.package}"
            raise ValueError(msg)
        if "/" in context.tag and not context.tag.startswith(f"{context.package}/"):
            msg = f"release tag does not match package: {context.tag}"
            raise ValueError(msg)
    validate_repository(context.repository)
    if context.artifact_url is not None and not context.artifact_url.startswith("https://"):
        msg = "artifact URL must use HTTPS"
        raise ValueError(msg)


def _extract_body(changelog: str, context: ReleaseContext) -> str:
    lines = [
        line
        for line in changelog.splitlines()
        if not _is_comparison_line(line) and not _RE_MARKDOWN_LINK_DEFINITION.fullmatch(line)
    ]
    heading_level = "###" if context.package is not None else "##"
    if context.package is not None:
        packages = [index for index, line in enumerate(lines) if line == f"## {context.package}"]
        if len(packages) != 1:
            msg = f"expected one changelog package section for {context.package}, found {len(packages)}"
            raise ValueError(msg)
        end = next(
            (index for index in range(packages[0] + 1, len(lines)) if lines[index].startswith("## ")), len(lines)
        )
        lines = lines[packages[0] + 1 : end]
    version = context.tag.rsplit("/", 1)[-1].removeprefix("v")
    headings = [
        index
        for index, line in enumerate(lines)
        if (match := _RE_MARKDOWN_VERSION.fullmatch(line))
        and match["level"] == heading_level
        and match["tag"].removeprefix("v") == version
    ]
    if len(headings) != 1:
        msg = f"expected one changelog section for {context.tag}, found {len(headings)}"
        raise ValueError(msg)

    body: list[str] = []
    for source_line in lines[headings[0] + 1 :]:
        if (
            (match := _RE_MARKDOWN_VERSION.fullmatch(source_line)) is not None and match["level"] == heading_level
        ) or _RE_MARKDOWN_VERSION_ANCHOR.fullmatch(source_line):
            break
        body.append(source_line)
    return _convert_markdown_body(body, "#### " if context.package is not None else "### ")


def _convert_markdown_body(lines: list[str], category_prefix: str) -> str:
    body: list[str] = []
    in_category = False
    in_item = False
    category_has_item = False
    for source_line in lines:
        line = source_line
        if source_line.startswith(category_prefix):
            if in_category and not category_has_item:
                msg = "empty changelog category"
                raise ValueError(msg)
            category = source_line[len(category_prefix) :]
            if category not in RELEASE_CATEGORIES:
                msg = f"unknown changelog category: {category}"
                raise ValueError(msg)
            line = f"### {RELEASE_CATEGORIES[category]}"
            in_category = True
            in_item = False
            category_has_item = False
        elif source_line.startswith("- "):
            if not in_category:
                msg = f"release item outside a category: {source_line}"
                raise ValueError(msg)
            in_item = True
            category_has_item = True
        elif (
            source_line.strip()
            and not (source_line.startswith('<a name="release-') and source_line.endswith('"></a>'))
            and (not in_item or not source_line[0].isspace())
        ):
            msg = f"release text outside an item: {source_line}"
            raise ValueError(msg)
        body.append(MARKDOWN_AUTHOR.sub(lambda match: f"@{match['handle']}", line))

    if in_category and not category_has_item:
        msg = "empty changelog category"
        raise ValueError(msg)

    return "\n".join(body).strip()


def _is_comparison_line(line: str) -> bool:
    return line.strip().startswith(("**Full Changelog**:", "Full Changelog:"))


__all__ = [
    "ReleaseContext",
    "render_markdown",
    "render_rst",
]
