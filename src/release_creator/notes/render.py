"""Render release notes from tagged changelogs."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # The dataclass decorator resolves during module load.
from __future__ import annotations

lazy import re
lazy from dataclasses import dataclass

lazy import mdformat
lazy from packaging.version import InvalidVersion, Version

lazy from release_creator.categories import RELEASE_CATEGORIES
lazy from release_creator.github import validate_repository
lazy from release_creator.notes.rst import TILDE_PLACEHOLDER, render_rst_section


@dataclass(frozen=True, kw_only=True)
class ReleaseContext:
    """Links and identity for one GitHub Release."""

    tag: str
    repository: str
    previous: str | None = None
    artifact_url: str | None = None
    artifact_label: str = "PyPI release"
    package: str | None = None


def render_markdown(changelog: str, context: ReleaseContext) -> str:
    """Render one Markdown release section for GitHub without wrapped list items.

    :param changelog: Tagged Markdown changelog.
    :param context: Repository and release links.
    :returns: The complete GitHub Release body.

    """
    _validate_context(context)
    notes = mdformat.text(_extract_body(changelog, context), options={"wrap": "no"}, extensions={"gfm"}).strip()
    return _finish(notes, context)


def render_rst(changelog: str, context: ReleaseContext) -> str:
    """Render one reStructuredText release section for GitHub.

    :param changelog: Tagged reStructuredText changelog.
    :param context: Repository and release links.
    :returns: The complete GitHub Release body.
    :raises ValueError: Package selection requires a Markdown changelog.
    """
    _validate_context(context)
    if context.package is not None:
        msg = "package selection requires a Markdown changelog"
        raise ValueError(msg)
    if TILDE_PLACEHOLDER in changelog:
        msg = "changelog contains a private-use character reserved for escaping"
        raise ValueError(msg)
    notes = mdformat.text(_extract_rst_body(changelog, context), options={"wrap": "no"}, extensions={"gfm"})
    return _finish(notes.strip().replace(TILDE_PLACEHOLDER, "\\~"), context)


def _finish(notes: str, context: ReleaseContext) -> str:
    if context.artifact_url is not None:
        link = f"[{context.artifact_label}]({context.artifact_url})"
        notes = f"{notes}\n\n{link}" if notes else link
    comparison = (
        f"compare/{context.previous}...{context.tag}" if context.previous is not None else f"commits/{context.tag}"
    )
    if notes:
        notes += "\n\n"
    return f"{notes}[Full Changelog](https://github.com/{context.repository}/{comparison})\n"


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
    start = headings[0] + 2
    if end < len(lines) and _is_rst_adornment(lines[end - 1]):
        end -= 1
    return render_rst_section("\n".join(lines[start:end]), context.tag, context.repository)


def _rst_version_at(lines: list[str], index: int) -> re.Match[str] | None:
    line = lines[index]
    if not any(map(_is_rst_adornment, lines[index + 1 : index + 2])):
        return None
    if line[:1].isspace() and not (
        line.startswith(" ") and not line.startswith("  ") and index > 0 and _is_rst_adornment(lines[index - 1])
    ):
        return None
    match = re.fullmatch(
        r"""
        ^(?:
            (?P<tag>v?[A-Za-z0-9.+-]+)\ \((?P<date>[^)]+)\)  # Version and date
            |
            `(?P<link_tag>v?[A-Za-z0-9.+-]+)\ <https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/tree/
            (?P=link_tag)>`_(?:\ -\ (?P<link_date>\d{4}-\d{2}-\d{2}))?  # Linked version, with optional date
        )$
        """,
        line.strip(),
        flags=re.VERBOSE,
    )
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
            (
                match := re.fullmatch(
                    r"""
                    ^\[(?P<version>v?[A-Za-z0-9.+-]+|unreleased)\]:  # Version reference
                    \s+https://github\.com/[^\s]+                    # GitHub destination
                    $                                                   # End of definition
                    """,
                    line,
                    flags=re.VERBOSE | re.IGNORECASE,
                )
            )
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
    markdown_version = re.compile(
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
    headings = [
        index
        for index, line in enumerate(lines)
        if (match := markdown_version.fullmatch(line))
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
            (match := markdown_version.fullmatch(source_line)) is not None
            and _is_version(match["tag"])
            and match["level"] == heading_level
        ) or _is_version_anchor(source_line, context.package):
            break
        body.append(source_line)
    return _convert_markdown_body(body, "#### " if context.package is not None else "### ")


def _is_version_anchor(line: str, package: str | None) -> bool:
    if (
        match := re.fullmatch(
            r"""
            ^<a\ name="release-             # Version anchor prefix
            (?P<version>v?[A-Za-z0-9_.-]+)  # Version encoded for an anchor
            "></a>$                         # Anchor terminator
            """,
            line,
            flags=re.VERBOSE,
        )
    ) is None:
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
            and re.fullmatch(
                r"""
                ^<a\ name="(?P<anchor>release-[A-Za-z0-9_-]+)"></a>$  # Complete release or category anchor
                """,
                source_line,
                flags=re.VERBOSE,
            )
            is None
            and (not in_item or not source_line[0].isspace())
        ):
            msg = f"release text outside an item: {source_line}"
            raise ValueError(msg)
        body.append(line)

    if in_category and not category_has_item:
        msg = "empty changelog category"
        raise ValueError(msg)

    return "\n".join(body).strip()


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
