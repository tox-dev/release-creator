"""Repair anchors after a changelog generator inserts a release section."""

import re
from typing import Final, cast

_RE_VERSION: Final = re.compile(
    r"""
    ^\#\#\s+                             # Markdown version heading
    (?P<version>v?\d+(?:\.\d+){1,3}(?:(?:a|b|rc)\d*)?)  # Release version
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

    Returns:
        Markdown with version and category anchors in their current positions.

    Raises:
        ValueError: The changelog has no release heading.

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
        if (match := _RE_VERSION.fullmatch(line)) is not None:
            version = cast("str", match["version"]).replace(".", "-")
            anchors.add(f"release-{version}")
        elif version is not None and (match := _RE_CATEGORY.fullmatch(line)) is not None:
            anchors.add(f"release-{version}-{match['category'].lower().replace(' ', '-')}")
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
        if (match := _RE_VERSION.fullmatch(line)) is not None:
            version = cast("str", match["version"]).replace(".", "-")
            anchor = f"release-{version}"
        elif version is not None and (match := _RE_CATEGORY.fullmatch(line)) is not None:
            anchor = f"release-{version}-{match['category'].lower().replace(' ', '-')}"
        else:
            result.append(line)
            continue
        if result and result[-1]:
            result.append("")
        result.extend((f'<a name="{anchor}"></a>', "", line))
    return "\n".join(result).rstrip("\n") + "\n"


__all__ = [
    "add_release_anchors",
]
