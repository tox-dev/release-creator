"""Render release notes from tagged changelogs."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # Shared regexes and the dataclass decorator resolve during module load.
from __future__ import annotations

lazy import re
lazy from collections.abc import Iterator
lazy from dataclasses import dataclass
lazy from html.parser import HTMLParser
lazy from typing import Final, override
lazy from urllib.parse import urlsplit

lazy import mdformat
lazy from markdown_it import MarkdownIt
lazy from markdown_it.token import Token
lazy from packaging.version import InvalidVersion, Version

lazy from release_creator.anchors.names import release_anchor
lazy from release_creator.categories import RELEASE_CATEGORIES
lazy from release_creator.github import MARKDOWN_AUTHOR, validate_repository
lazy from release_creator.notes.rst import render_rst_section

_RE_RELEASE_PULL: Final = re.compile(
    r"""
    (?<![A-Za-z0-9_.#-])  # Ignore words and headings
    (?:
        \#|GH-  # GitHub's current-repository shorthand
        |
        (?P<short_repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\#  # Owner/repository shorthand
        |
        (?:https?://)?(?:www\.)?github\.com/
        (?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/
        (?P<kind>pull|issues)/  # GitHub also serves PRs at their issue URL
    )
    (?P<number>\d+)
    """,
    re.VERBOSE | re.IGNORECASE,
)
_RE_GITHUB_CREDIT: Final = re.compile(
    r"""
    \s(?:-\s)?by\s+  # Candidate author credit
    """,
    re.VERBOSE,
)
_RE_GITHUB_HANDLE: Final = re.compile(
    r"""
    @(?P<handle>[A-Za-z0-9-]+)   # GitHub mention
    """,
    re.VERBOSE,
)
_RE_PROFILE_LABEL: Final = re.compile(
    r"""
    @(?P<handle>[A-Za-z0-9-]+)  # Displayed GitHub handle
    """,
    re.VERBOSE,
)
_RE_GITHUB_PATH: Final = re.compile(
    r"""
    ^/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)  # Owner and repository
    /(?P<kind>pull|issues)/(?P<number>\d+)             # Pull request or issue route
    (?:/|$)                                             # Optional subpath
    """,
    re.VERBOSE,
)
_RE_PULL_LABEL: Final = re.compile(
    r"""
    (?:PR\ \#?|\#)(?P<number>\d+)  # Displayed pull request number
    """,
    re.VERBOSE | re.IGNORECASE,
)
_RE_CREDIT_HANDLES: Final = re.compile(
    r"""
    ^\s*(?P<handles>
        @[A-Za-z0-9-]+  # First credited author
        (?:(?:\s*,\s*|\s+and\s+)@[A-Za-z0-9-]+)*  # Additional authors
    )
    (?:[.,;)\s]|$)  # Credit ends before other prose
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
    \s*$                                # Actual credit follows the entire title
    """,
    re.VERBOSE,
)
_RE_GENERATED_PR_LINK: Final = re.compile(
    r"""
    \bin\s+https://github\.com/
    (?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)  # GitHub repository
    /pull/(?P<number>\d+)                            # Final PR on the generated line
    \s*$                                               # End of generated line
    """,
    re.VERBOSE,
)
_RE_RST_VERSION: Final = re.compile(
    r"""
    ^(?:
        (?P<tag>v?[A-Za-z0-9.+-]+)\ \((?P<date>[^)]+)\)  # Version and date
        |
        `(?P<link_tag>v?[A-Za-z0-9.+-]+)\ <https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/tree/
        (?P=link_tag)>`_(?:\ -\ (?P<link_date>\d{4}-\d{2}-\d{2}))?  # Linked version, with optional date
    )$
    """,
    re.VERBOSE,
)
_RE_MARKDOWN_VERSION: Final = re.compile(
    r"""
    ^(?P<level>\#{2,3})\          # Markdown version heading level
    (?P<open>\[)?                   # Optional Keep a Changelog link bracket
    (?P<tag>v?[A-Za-z0-9.+-]+)  # Release version; Version validates its syntax
    (?(open)\])                     # Close the optional bracket
    (?:\ \([^)]+\)|\ -\ [^\n]+)? # Parenthesized or dash-separated date
    $                               # End of heading
    """,
    re.VERBOSE,
)
_RE_MARKDOWN_VERSION_ANCHOR: Final = re.compile(
    r"""
    ^<a\ name="release-             # Version anchor prefix
    (?P<version>v?[A-Za-z0-9_.-]+)  # Version encoded for an anchor
    "></a>$                         # Anchor terminator
    """,
    re.VERBOSE,
)
_RE_MARKDOWN_ANCHOR: Final = re.compile(
    r"""
    ^<a\ name="(?P<anchor>release-[A-Za-z0-9_-]+)"></a>$  # Complete release or category anchor
    """,
    re.VERBOSE,
)
_RE_MARKDOWN_LINK_DEFINITION: Final = re.compile(
    r"""
    ^\[(?P<version>v?[A-Za-z0-9.+-]+|unreleased)\]:  # Version reference
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


def render_rst(changelog: str, context: ReleaseContext, generated_notes: str | None = None) -> str:
    """Render one reStructuredText release section for GitHub.

    :param changelog: Tagged reStructuredText changelog.
    :param context: Repository and release links.
    :param generated_notes: GitHub-generated text used only for verified contributor credits.
    :returns: The complete GitHub Release body.
    :raises ValueError: Package selection requires a Markdown changelog.
    """
    _validate_context(context)
    if context.package is not None:
        msg = "package selection requires a Markdown changelog"
        raise ValueError(msg)
    notes = mdformat.text(_extract_rst_body(changelog, context), options={"wrap": "no"}, extensions={"gfm"}).strip()
    return _finish(notes, context, generated_notes)


def _finish(notes: str, context: ReleaseContext, generated_notes: str | None) -> str:
    visible_lines = list(_visible_lines(notes, context.repository))
    if generated_notes is not None:
        _verify_authors(visible_lines, generated_notes, context)
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
    return f"{notes}[Full Changelog](https://github.com/{context.repository}/{comparison})\n"


def _verify_authors(visible_lines: list[str], generated_notes: str, context: ReleaseContext) -> None:
    generated_authors, generated_bots = _generated_pr_authors(generated_notes, context.repository)
    for number, entries in _release_entries(visible_lines, context.repository, set(generated_authors)).items():
        if number not in generated_authors:
            if any(not handles for handles, _ in entries):
                msg = f"generated notes have no author for pull request #{number}"
                raise ValueError(msg)
            continue
        if (bot := generated_bots.get(number)) is not None and any(bot.casefold() in handles for handles, _ in entries):
            msg = f"changelog credit for pull request #{number} must not name bot @{bot}"
            raise ValueError(msg)
        if bot is None and generated_authors[number] is None and any(not attributed for _, attributed in entries):
            msg = f"changelog has no credit for pull request #{number} with an unavailable author"
            raise ValueError(msg)
        if (author := generated_authors[number]) is not None and any(
            author.casefold() not in handles for handles, _ in entries
        ):
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
        if (link := _RE_GENERATED_PR_LINK.search(line)) is None or link[
            "repository"
        ].casefold() != repository.casefold():
            continue
        match = _RE_GENERATED_PR_AUTHOR.search(line)
        number = link["number"]
        author = None if match is None or match["bot"] is not None else match["handle"]
        if match is not None and match["bot"] is not None:
            bots[number] = match["handle"]
        if number in authors and authors[number] != author:
            msg = f"conflicting generated authors for pull request #{number}"
            raise ValueError(msg)
        authors[number] = author
    return authors, bots


def _release_entries(
    visible_lines: list[str], repository: str, known_numbers: set[str]
) -> dict[str, list[tuple[set[str], bool]]]:
    entries: dict[str, list[tuple[set[str], bool]]] = {}
    for line in visible_lines:
        references = _pull_references(line, repository, known_numbers)
        if not references:
            continue
        initial_credit = _entry_credit(line[: references[0].start()], named=False)
        pending: list[re.Match[str]] = []
        for index, reference in enumerate(references):
            pending.append(reference)
            following = line[reference.end() : references[index + 1].start() if index + 1 < len(references) else None]
            if (credit := _entry_credit(following, named=True)) is not None:
                for item in pending:
                    entries.setdefault(item["number"], []).append(credit)
                pending.clear()
            elif index + 1 < len(references) and not _shared_credit_group(line, reference, references[index + 1]):
                for item in pending:
                    entries.setdefault(item["number"], []).append(initial_credit or (set(), False))
                pending.clear()
        for item in pending:
            entries.setdefault(item["number"], []).append(
                initial_credit if len(pending) == len(references) and initial_credit is not None else (set(), False)
            )
    return entries


def _shared_credit_group(line: str, first: re.Match[str], second: re.Match[str]) -> bool:
    between = line[first.end() : second.start()]
    return between.strip(" (),;") in {"", "and"}


def _visible_lines(notes: str, repository: str) -> Iterator[str]:
    parser = _RawHtmlLinkParser()
    for token in MarkdownIt().parse(notes):
        if token.type == "html_block":
            parser.feed(token.content)
            yield from parser.take_text().splitlines()
        elif token.type == "inline":
            yield from _visible_inline(token.children or [], parser, repository).splitlines()


def _visible_inline(children: list[Token], parser: _RawHtmlLinkParser, repository: str) -> str:
    parts: list[str] = []
    index = 0
    while index < len(children):
        child = children[index]
        if child.type == "html_inline":
            parser.feed(child.content)
            parts.append(parser.take_text())
        elif parser.in_literal():
            pass
        elif child.type == "link_open":
            end = next(
                position for position in range(index + 1, len(children)) if children[position].type == "link_close"
            )
            label = "".join(item.content for item in children[index + 1 : end] if item.type in {"text", "code_inline"})
            parts.append(_visible_link(label, str(child.attrGet("href") or ""), repository))
            index = end
        elif child.type == "text":
            parts.append(child.content)
        elif child.type in {"softbreak", "hardbreak"}:
            parts.append(" " if child.type == "softbreak" else "\n")
        elif child.type == "code_inline":
            parts.append(" ")
        index += 1
    return "".join(parts)


def _visible_link(label: str, url: str, repository: str) -> str:
    if (profile := _RE_PROFILE_LABEL.fullmatch(label)) is not None:
        parsed = urlsplit(url)
        handle = profile["handle"].casefold()
        if (
            parsed.scheme != "https"
            or parsed.netloc.casefold() not in {"github.com", "www.github.com"}
            or parsed.path.casefold() not in {f"/{handle}", f"/{handle}/"}
            or parsed.query
            or parsed.fragment
        ):
            msg = f"GitHub credit link for @{profile['handle']} points to another profile"
            raise ValueError(msg)
        return label
    parsed = urlsplit(url)
    path = _RE_GITHUB_PATH.match(parsed.path)
    github_pull = (
        parsed.scheme == "https" and parsed.netloc.casefold() in {"github.com", "www.github.com"} and path is not None
    )
    current_pull = github_pull and path is not None and path["repository"].casefold() == repository.casefold()
    number = _RE_PULL_LABEL.fullmatch(label)
    if (
        number is not None
        and not (github_pull and not current_pull)
        and (not current_pull or number["number"] != path["number"])
    ):
        destination = path["number"] if current_pull else "another URL"
        msg = f"pull request label #{number['number']} points to #{destination}"
        raise ValueError(msg)
    if not current_pull:
        return " "
    return f" https://github.com/{repository}/{path['kind']}/{path['number']} "


def _pull_references(line: str, repository: str, known_numbers: set[str]) -> list[re.Match[str]]:
    candidates = [
        match
        for match in _RE_RELEASE_PULL.finditer(line)
        if (match["repository"] is None or match["repository"].casefold() == repository.casefold())
        and (match["short_repository"] is None or match["short_repository"].casefold() == repository.casefold())
        and not _reference_in_url(line, match)
    ]
    known = known_numbers | {match["number"] for match in candidates if match["kind"] == "pull"}
    relevant = [match for match in candidates if match["kind"] == "pull" or match["number"] in known]
    sources: list[re.Match[str]] = []
    for index, match in enumerate(relevant):
        following = line[match.end() : relevant[index + 1].start() if index + 1 < len(relevant) else None]
        if not _contextual_pull_url(line[: match.start()], match, sources, following):
            sources.append(match)
    return sources


def _contextual_pull_url(prefix: str, match: re.Match[str], sources: list[re.Match[str]], following: str) -> bool:
    return (
        match["repository"] is not None
        and bool(sources)
        and re.search(
            r"""
            (?<![A-Za-z0-9_])(?P<verb>see|compare)\s+$  # Reference introduced by a separate source link
            """,
            prefix,
            re.VERBOSE | re.IGNORECASE,
        )
        is not None
        and not _has_contextual_credit(following)
    )


def _has_contextual_credit(text: str) -> bool:
    return any(
        (credit := _entry_credit(f" {text[marker.start() :]}", named=True)) is not None and credit[1]
        for marker in re.finditer(
            r"""
            (?<![A-Za-z0-9_])(?P<credit>by)\s+  # Candidate credit after punctuation
            """,
            text,
            re.VERBOSE | re.IGNORECASE,
        )
    )


def _reference_in_url(line: str, match: re.Match[str]) -> bool:
    prefix = line[: match.start()]
    if not prefix or prefix[-1].isspace():
        return False
    before = prefix.split()
    return bool(before and before[-1].lstrip("(").startswith(("https://", "http://")))


def _entry_credit(text: str, *, named: bool) -> tuple[set[str], bool] | None:
    for marker in _RE_GITHUB_CREDIT.finditer(text):
        prefix = text[: marker.start()].strip()
        if named and prefix.strip("(),;.-"):
            continue
        if not named and prefix.rsplit(" ", 1)[-1].casefold() in {"reviewed", "tested", "approved", "verified"}:
            continue
        credit_text = text[marker.end() :]
        handles = (
            {str(item.group("handle")).casefold() for item in _RE_GITHUB_HANDLE.finditer(match["handles"])}
            if (match := _RE_CREDIT_HANDLES.match(credit_text)) is not None
            else set[str]()
        )
        plain_name = credit_text.strip(" .()")
        return handles, bool(handles) or (named and len(plain_name.split()) > 1 and plain_name.istitle())
    return None


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
    anchor = release_anchor(context.tag, "New Contributors")
    return f'<a name="{anchor}"></a>\n\n### New Contributors\n\n{"\n".join(entries)}'


def _contributor_reference(match: re.Match[str], repository: str) -> str:
    prefix = match["reference"] if match["reference"] != "#" else f"https://github.com/{repository}/pull/"
    return f"[#{match['number']}]({prefix}{match['number']})"


def _extract_rst_body(changelog: str, context: ReleaseContext) -> str:
    lines = [line for line in changelog.splitlines() if not _is_comparison_line(line)]
    headings = [
        index
        for index in range(len(lines))
        if (match := _rst_version_at(lines, index))
        and (match["tag"] or match["link_tag"]).removeprefix("v") == context.tag.removeprefix("v")
    ]
    if len(headings) != 1:
        msg = f"expected one changelog section for {context.tag}, found {len(headings)}"
        raise ValueError(msg)
    end = next(
        (index for index in range(headings[0] + 1, len(lines)) if _rst_version_at(lines, index) is not None),
        len(lines),
    )
    start = headings[0] + 1
    if start < end and _is_rst_adornment(lines[start]):
        start += 1
    if end < len(lines) and _is_rst_adornment(lines[end - 1]):
        end -= 1
    return render_rst_section("\n".join(lines[start:end]), context.tag, context.repository)


def _rst_version_at(lines: list[str], index: int) -> re.Match[str] | None:
    line = lines[index]
    if line[:1].isspace() and not (
        line.startswith(" ")
        and not line.startswith("  ")
        and index > 0
        and index + 1 < len(lines)
        and _is_rst_adornment(lines[index - 1])
        and _is_rst_adornment(lines[index + 1])
    ):
        return None
    match = _RE_RST_VERSION.fullmatch(line.strip())
    return match if match is not None and _is_version(match["tag"] or match["link_tag"]) else None


def _is_rst_adornment(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped[2:]) and len(set(stripped)) == 1 and stripped[0] in "=-*~^"


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
    if context.package is not None and "/" in context.tag and not context.tag.startswith(f"{context.package}/"):
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
        if not _is_comparison_line(line)
        and not (
            (match := _RE_MARKDOWN_LINK_DEFINITION.fullmatch(line))
            and (match["version"].lower() == "unreleased" or _is_version(match["version"]))
        )
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
        and _is_version(match["tag"])
        and match["level"] == heading_level
        and match["tag"].removeprefix("v") == version
    ]
    if len(headings) != 1:
        msg = f"expected one changelog section for {context.tag}, found {len(headings)}"
        raise ValueError(msg)

    body: list[str] = []
    for source_line in lines[headings[0] + 1 :]:
        if (
            (match := _RE_MARKDOWN_VERSION.fullmatch(source_line)) is not None
            and _is_version(match["tag"])
            and match["level"] == heading_level
        ) or _is_version_anchor(source_line, context.package):
            break
        body.append(source_line)
    return _convert_markdown_body(body, "#### " if context.package is not None else "### ")


def _is_version_anchor(line: str, package: str | None) -> bool:
    if (match := _RE_MARKDOWN_VERSION_ANCHOR.fullmatch(line)) is None:
        return False
    version = match["version"]
    if package is not None:
        prefix = f"{package.replace('.', '-')}-"
        if not version.startswith(prefix):
            return False
        version = version.removeprefix(prefix)
    return _is_version(version.replace("-", "."))


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
            and _RE_MARKDOWN_ANCHOR.fullmatch(source_line) is None
            and (not in_item or not source_line[0].isspace())
        ):
            msg = f"release text outside an item: {source_line}"
            raise ValueError(msg)
        body.append(MARKDOWN_AUTHOR.sub(lambda match: f"@{match['handle']}", line))

    if in_category and not category_has_item:
        msg = "empty changelog category"
        raise ValueError(msg)

    return "\n".join(body).strip()


class _RawHtmlLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._text: list[str] = []
        self._literal_tags: list[str] = []

    def in_literal(self) -> bool:
        return bool(self._literal_tags)

    def take_text(self) -> str:
        content = "".join(self._text)
        self._text.clear()
        return content

    @override
    def handle_data(self, data: str) -> None:
        if not self.in_literal():
            self._text.append(data)

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"code", "kbd", "pre", "samp", "script", "style", "textarea", "template", "noscript"}:
            self._literal_tags.append(tag)
        elif not self.in_literal() and tag == "a" and any(name == "href" for name, _ in attrs):
            msg = "raw HTML links are unsupported in release notes"
            raise ValueError(msg)

    @override
    def handle_endtag(self, tag: str) -> None:
        if self._literal_tags and self._literal_tags[-1] == tag:
            self._literal_tags.pop()


def _is_comparison_line(line: str) -> bool:
    return line.strip().startswith(("**Full Changelog**:", "Full Changelog:", "[Full Changelog](", "`Full Changelog <"))


def _is_version(tag: str) -> bool:
    try:
        Version(tag.removeprefix("v"))
    except InvalidVersion:
        return False
    return True


__all__ = [
    "ReleaseContext",
    "render_markdown",
    "render_rst",
]
