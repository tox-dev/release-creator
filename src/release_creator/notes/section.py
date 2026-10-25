"""Extract one version's section from a Markdown or reStructuredText changelog."""

lazy import itertools
lazy import re
lazy from collections.abc import Callable, Iterator

type _Heading = tuple[int, int, int, str]
"""First line, first body line, nesting level, and title text of a heading."""


def release_section(changelog: str, tag: str, package: str | None = None, *, rst: bool = False) -> str:
    """Return the body under the heading of ``tag``'s version, without the heading itself.

    :param changelog: Changelog text.
    :param tag: Release tag; a ``package/`` prefix and a ``v`` prefix are ignored when matching.
    :param package: Title of the heading that holds the package's versions in a shared changelog.
    :param rst: Parse reStructuredText headings instead of Markdown ones.
    :returns: The section text in the changelog's own format, or an empty string for an empty section.
    :raises ValueError: The package or version heading is missing or appears more than once.
    """
    if package is not None and "/" in tag and tag.partition("/")[0] != package:
        msg = f"release tag {tag} does not belong to package {package}"
        raise ValueError(msg)
    lines = changelog.splitlines()
    headings = list((_rst_headings if rst else _markdown_headings)(lines))
    end = len(lines)
    if package is not None:
        start, end = _section(headings, end, lambda title: title == package, f"package {package}")
        headings = [heading for heading in headings if start <= heading[0] < end]
    version = tag.rpartition("/")[2].removeprefix("v")
    start, end = _section(headings, end, lambda title: _title_version(title) == version, tag)
    section = [line for line in lines[start:end] if not _version_reference(line)]
    # The anchor or label of the next release sits above its heading, so it ends up at the bottom of this one.
    while section and re.fullmatch(r"\s*|\.\. _[^:]+:|<a name=\"[^\"]*\"></a>", section[-1]):
        section.pop()
    return f"{text}\n" if (text := "\n".join(section).strip("\n")) else ""


def _markdown_headings(lines: list[str]) -> Iterator[_Heading]:
    fence: str | None = None
    for index, line in enumerate(lines):
        if opening := re.match(r" {0,3}(```|~~~)", line):
            fence = None if fence == (marker := str(opening[1])) else fence or marker
        elif fence is None and (heading := re.fullmatch(r" {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*", line)):
            yield index, index + 1, len(heading[1]), str(heading[2])


def _rst_headings(lines: list[str]) -> Iterator[_Heading]:
    # reStructuredText ranks heading styles by first appearance rather than by a fixed character order.
    styles: dict[tuple[str, bool], int] = {}
    for index, (title, underline) in enumerate(itertools.pairwise(lines)):
        if not title.strip() or not _adornment(underline) or len(underline.rstrip()) < len(title.rstrip()):
            continue
        overline = index > 0 and lines[index - 1] == underline
        if title[:1].isspace() and not overline:
            continue
        level = styles.setdefault((underline[0], overline), len(styles))
        yield index - overline, index + 2, level, title.strip()


def _adornment(line: str) -> bool:
    return re.fullmatch(r"([!-/:-@\[-`{-~])\1{2,}", line.rstrip()) is not None


def _section(headings: list[_Heading], end: int, matches: Callable[[str], bool], name: str) -> tuple[int, int]:
    if len(found := [heading for heading in headings if matches(heading[3])]) != 1:
        msg = f"expected one changelog section for {name}, found {len(found)}"
        raise ValueError(msg)
    first, body, level, _ = found[0]
    return body, next((other[0] for other in headings if other[0] > first and other[2] <= level), end)


def _title_version(title: str) -> str | None:
    return str(version[1]) if (version := re.match(r"[\[`]?v?(\d[\w.+!-]*)", title)) else None


def _version_reference(line: str) -> bool:
    return re.fullmatch(r"\[(?:v?\d[\w.+!-]*|unreleased)\]:\s+\S+", line, re.IGNORECASE) is not None


__all__ = [
    "release_section",
]
