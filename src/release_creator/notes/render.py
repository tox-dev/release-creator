"""Render release notes from tagged changelogs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

lazy import mdformat

_CATEGORIES: Final = {
    "Added": "Features",
    "Changes": "Changes",
    "Fixed": "Bug fixes",
    "Documentation": "Documentation",
    "Breaking changes": "Breaking changes",
    "Security": "Security",
    "Performance": "Performance",
    "Deprecated": "Deprecations",
    "Removed": "Removals",
    "Packaging": "Packaging",
}
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
        v?(?P<tag>\d+\.\d+\.\d+)\ \((?P<date>[^)]+)\)  # Plain version with parenthesized date
        |
        `(?P<link_tag>\d+\.\d+\.\d+)\ <https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/tree/
        (?P=link_tag)>`_\ -\ (?P<link_date>\d{4}-\d{2}-\d{2})  # Linked version with date
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
    (?P<tag>v?\d+\.\d+\.\d+)     # Release tag
    (?(open)\])                     # Close the optional bracket
    (?:\ \([^)]+\)|\ -\ [^\n]+)? # Parenthesized or dash-separated date
    $                               # End of heading
    """,
    re.VERBOSE,
)
_RE_MARKDOWN_VERSION_ANCHOR: Final = re.compile(
    r"""
    ^<a\ name="release-             # Version anchor prefix
    (?P<version>v?\d+(?:-\d+){2})  # Dotted version encoded for an anchor
    "></a>$                         # Anchor terminator
    """,
    re.VERBOSE,
)
_RE_MARKDOWN_AUTHOR: Final = re.compile(
    r"""
    \[@(?P<handle>[A-Za-z0-9-]+)\]  # GitHub handle in link text
    \(https://github\.com/(?P=handle)\)  # Matching profile URL
    """,
    re.VERBOSE,
)
_RE_MARKDOWN_LINK_DEFINITION: Final = re.compile(
    r"""
    ^\[(?P<version>v?\d+\.\d+\.\d+|unreleased)\]:  # Version comparison reference
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

    Returns:
        The complete GitHub Release body.


    """
    _validate_context(context)
    notes = mdformat.text(_extract_body(changelog, context), options={"wrap": "no"}, extensions={"gfm"}).strip()
    return _finish(notes, context, generated_notes)


def render_rst(
    changelog: str, context: ReleaseContext, issue_role: str = "issue", generated_notes: str | None = None
) -> str:
    """Render one reStructuredText release section for GitHub.

    Returns:
        The complete GitHub Release body.

    Raises:
        ValueError: The issue role must name a GitHub issue or pull request.

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
        if contributors := _new_contributors(notes, generated_notes, context.tag):
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
            msg = f"generated notes have no author for pull request #{number}"
            raise ValueError(msg)
        if (bot := generated_bots.get(number)) is not None and any(bot in handles for handles in entries):
            msg = f"changelog credit for pull request #{number} must not name bot @{bot}"
            raise ValueError(msg)
        if (author := generated_authors[number]) is not None and any(author not in handles for handles in entries):
            msg = f"changelog credit for pull request #{number} does not include @{author}"
            raise ValueError(msg)


def _generated_pr_authors(generated_notes: str, repository: str) -> tuple[dict[str, str | None], dict[str, str]]:
    authors: dict[str, str | None] = {}
    bots: dict[str, str] = {}
    for line in generated_notes.splitlines():
        if (match := _RE_GENERATED_PR_AUTHOR.search(line)) is None or match["repository"] != repository:
            continue
        number = match["number"]
        author = None if match["bot"] is not None else match["handle"]
        if match["bot"] is not None:
            bots[number] = match["handle"]
        if number in authors and authors[number] != author:
            msg = f"conflicting generated authors for pull request #{number}"
            raise ValueError(msg)
        authors[number] = author
    return authors, bots


def _release_entries(notes: str, repository: str) -> dict[str, list[set[str]]]:
    entries: dict[str, list[set[str]]] = {}
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
            entries.setdefault(number, []).append(handles)
    return entries


def _new_contributors(notes: str, generated_notes: str, tag: str) -> str:
    if (
        section := re.search(
            r"""
            ^\#\#\ New\ Contributors\s*\n  # Generated contributor heading
            (?P<entries>.*?)            # Lines until the next heading
            (?=^\#\#\ |\Z)              # Next section or end of body
            """,
            generated_notes,
            re.MULTILINE | re.DOTALL | re.VERBOSE,
        )
    ) is None:
        return ""
    credited = {
        match["handle"]
        for match in re.finditer(
            r"""
            @(?P<handle>[A-Za-z0-9-]+)  # Credited GitHub handle
            """,
            notes,
            re.VERBOSE,
        )
    }
    entries = [
        f"- @{match['handle']} made their first contribution in #{match['number']}"
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
        and match["handle"] in credited
    ]
    if not entries:
        return ""
    anchor = f"release-{tag.replace('.', '-').replace('/', '-')}-new-contributors"
    return f'<a name="{anchor}"></a>\n\n### New Contributors\n\n' + "\n".join(entries)


def _extract_rst_body(changelog: str, context: ReleaseContext, issue_role: str) -> str:
    lines = [line for line in changelog.splitlines() if not _is_comparison_line(line)]
    headings = [
        index
        for index, line in enumerate(lines)
        if (match := _RE_RST_VERSION.fullmatch(line.strip()))
        and (match["tag"] or match["link_tag"]) == context.tag.removeprefix("v")
    ]
    if len(headings) != 1:
        msg = f"expected one changelog section for {context.tag}, found {len(headings)}"
        raise ValueError(msg)
    end = next(
        (index for index in range(headings[0] + 1, len(lines)) if _RE_RST_VERSION.fullmatch(lines[index].strip())),
        len(lines),
    )
    sections: dict[str, list[str]] = {}
    category: str | None = None
    index = headings[0] + 1
    while index < end:
        line = lines[index].strip()
        if line and index + 1 < end and _RE_RST_HEADING_UNDERLINE.fullmatch(lines[index + 1].strip()):
            category = _require_category(line)
            sections.setdefault(category, [])
            index += 2
            continue
        if line.startswith("- "):
            if category is None:
                msg = f"release item outside a category: {line}"
                raise ValueError(msg)
            sections[category].append(_convert_rst(line, context.repository, issue_role))
        elif line and _RE_RST_HEADING_UNDERLINE.fullmatch(line) is None and not line.startswith(".. _"):
            if category is None or not sections[category]:
                msg = f"unexpected release text: {line}"
                raise ValueError(msg)
            sections[category][-1] += f" {_convert_rst(line, context.repository, issue_role)}"
        index += 1
    body: list[str] = []
    for name, entries in sections.items():
        if entries:
            anchor = f"release-{context.tag.replace('.', '-')}-{name.lower().replace(' ', '-')}"
            body.extend((f'<a name="{anchor}"></a>', "", f"### {_CATEGORIES[name]}", "", *entries, ""))
    return "\n".join(body).strip()


def _require_category(name: str) -> str:
    if name not in _CATEGORIES:
        msg = f"unknown changelog category: {name}"
        raise ValueError(msg)
    return name


def _convert_rst(line: str, repository: str, issue_role: str) -> str:
    issue_target = "pull" if issue_role == "pull" else "issues"
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
        ``(?P<code>[^`]+)``   # RST inline code
        """,
        r"`\g<code>`",
        line,
        flags=re.VERBOSE,
    )
    line = re.sub(
        r"""
        :(?:[a-z]+:)?[a-z]+:`  # RST role with optional domain
        ~?(?P<name>[^`]+)`     # Referenced name, with optional short display
        """,
        lambda match: f"`{match['name'].split('.')[-1]}`",
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
    if not re.fullmatch(
        r"""
        (?P<owner>[A-Za-z0-9_.-]+)  # GitHub owner
        /                            # Repository separator
        (?P<name>[A-Za-z0-9_.-]+)   # GitHub repository
        """,
        context.repository,
        re.VERBOSE,
    ):
        msg = f"invalid repository: {context.repository}"
        raise ValueError(msg)
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
            if category not in _CATEGORIES:
                msg = f"unknown changelog category: {category}"
                raise ValueError(msg)
            line = f"### {_CATEGORIES[category]}"
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
        body.append(_RE_MARKDOWN_AUTHOR.sub(lambda match: f"@{match['handle']}", line))

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
