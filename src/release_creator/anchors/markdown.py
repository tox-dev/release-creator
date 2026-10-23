"""Repair anchors after a changelog generator inserts a release section."""

import re
lazy from typing import Final, cast

lazy from packaging.version import InvalidVersion, Version

lazy from release_creator.anchors.names import release_anchor

_RE_VERSION: Final = re.compile(
    r"""
    ^\#\#\s+                             # Markdown version heading
    (?P<version>\S+)                      # Candidate release version
    (?:\s+\([^)]+\))?                     # Optional release date
    $                                      # End of heading
    """,
    re.VERBOSE,
)
_RE_CATEGORY: Final = re.compile(
    r"""
    ^\#\#\#\s+                        # Markdown category heading
    (?P<category>[A-Za-z][A-Za-z ]*)  # Category name
    $                                 # End of heading
    """,
    re.VERBOSE,
)
_RE_ANCHOR: Final = re.compile(
    r"""
    ^<a\s+name="(?P<anchor>release-[A-Za-z0-9-]+)"></a>$  # Release anchor
    """,
    re.VERBOSE,
)


def add_release_anchors(changelog: str) -> str:
    """Place stable anchors immediately before release headings.

    :param changelog: Markdown changelog to update.
    :returns: Markdown with version and category anchors in their current positions.
    :raises ValueError: The changelog has no release heading.
    """
    lines = changelog.splitlines()
    anchors = _collect_anchors(lines)
    if not anchors:
        msg = "no Markdown release headings found"
        raise ValueError(msg)
    return _insert_anchors(_strip_anchors(lines, anchors))


def _collect_anchors(lines: list[str]) -> set[str]:
    anchors: set[str] = set()
    version: str | None = None
    for line in lines:
        if (heading := _version_heading(line)) is not None:
            version = heading
            anchors.add(release_anchor(version))
        elif version is not None and (match := _RE_CATEGORY.fullmatch(line)) is not None:
            anchors.add(release_anchor(version, match["category"]))
    return anchors


def _strip_anchors(lines: list[str], anchors: set[str]) -> list[str]:
    cleaned: list[str] = []
    line_index = 0
    while line_index < len(lines):
        line = lines[line_index]
        if (match := _RE_ANCHOR.fullmatch(line)) is not None and match["anchor"] in anchors:
            line_index += 1
            if line_index < len(lines) and not lines[line_index]:
                line_index += 1
        else:
            cleaned.append(line)
            line_index += 1
    return cleaned


def _insert_anchors(lines: list[str]) -> str:
    result: list[str] = []
    version = None
    for line in lines:
        if (heading := _version_heading(line)) is not None:
            version = heading
            anchor = release_anchor(version)
        elif version is not None and (match := _RE_CATEGORY.fullmatch(line)) is not None:
            anchor = release_anchor(version, match["category"])
        else:
            result.append(line)
            continue
        if result and result[-1]:
            result.append("")
        result.extend((f'<a name="{anchor}"></a>', "", line))
    return f"{'\n'.join(result).rstrip('\n')}\n"


def _version_heading(line: str) -> str | None:
    if (match := _RE_VERSION.fullmatch(line)) is None:
        return None
    version = cast("str", match["version"])
    try:
        Version(version)
    except InvalidVersion:
        return None
    return version


__all__ = [
    "add_release_anchors",
]
