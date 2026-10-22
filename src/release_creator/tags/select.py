"""Validate numeric tags and find their predecessors."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date


def next_tag(bump: str, tags: list[str], fragments: list[str], release_date: date, prefix: str = "") -> str:
    """Choose a release version from existing tags and pending fragments.

    :param bump: Automatic or explicit version bump type.
    :param tags: Existing repository tags.
    :param fragments: Pending fragment filenames.
    :param release_date: Date used for CalVer.
    :param prefix: Optional prefix for the new tag.
    :returns: The next major.minor.patch or year.month.patch version, with the requested prefix.
    :raises ValueError: The bump is unknown, no fragments exist, or the result is not newer.
    """
    if not fragments:
        msg = "no changelog fragments to release"
        raise ValueError(msg)
    versions: list[tuple[int, int, int]] = []
    for tag in tags:
        try:
            versions.append(parse_tag(tag))
        except ValueError:
            continue
    current = max(versions, default=(0, 0, 0))
    if bump == "auto":
        bump = (
            "major"
            if any(fragment.endswith((".breaking.md", ".breaking.rst")) for fragment in fragments)
            else "minor"
            if any(fragment.endswith((".feature.md", ".feature.rst")) for fragment in fragments)
            else "patch"
        )
    match bump:
        case "major":
            version = (current[0] + 1, 0, 0)
        case "minor":
            version = (current[0], current[1] + 1, 0)
        case "patch":
            version = (current[0], current[1], current[2] + 1)
        case "calver":
            year_month = release_date.year, release_date.month
            version = (*year_month, current[2] + 1 if current[:2] == year_month else 0)
        case _:
            msg = f"unknown version bump: {bump}"
            raise ValueError(msg)
    if version <= current:
        msg = f"calculated version must be newer than {'.'.join(map(str, current))}"
        raise ValueError(msg)
    return f"{prefix}{'.'.join(map(str, version))}"


def parse_tag(tag: str) -> tuple[int, int, int]:
    """Parse a major.minor.patch release tag with an optional v prefix.

    :param tag: Version tag to parse.
    :returns: The numeric major, minor, and patch components.
    :raises ValueError: The tag is not a numeric release version.
    """
    match tag.removeprefix("v").split("."):
        case [major, minor, patch] if all(part.isascii() and part.isdecimal() for part in (major, minor, patch)):
            return int(major), int(minor), int(patch)
        case _:
            msg = f"expected a major.minor.patch version with optional v prefix: {tag}"
            raise ValueError(msg)


def previous_tag(tag: str, tags: list[str]) -> str | None:
    """Select the greatest numeric release tag before ``tag``.

    :param tag: Release tag whose predecessor is needed.
    :param tags: Existing repository tags.
    :returns: The preceding tag, or ``None`` when this is the first release.
    """
    target = parse_tag(tag)
    candidates: list[tuple[tuple[int, int, int], str]] = []
    for candidate in tags:
        try:
            version = parse_tag(candidate)
        except ValueError:
            continue
        if version < target:
            candidates.append((version, candidate))
    return max(candidates, default=((), ""))[1] or None


def require_newer_tag(tag: str, tags: list[str]) -> None:
    """Require ``tag`` to follow every existing numeric release tag.

    :param tag: Candidate release tag.
    :param tags: Existing repository tags.
    :raises ValueError: A matching or newer release tag already exists.
    """
    target = parse_tag(tag)
    versions: list[tuple[int, int, int]] = []
    for candidate in tags:
        try:
            versions.append(parse_tag(candidate))
        except ValueError:
            continue
    if versions and target <= max(versions):
        msg = f"{tag} must be newer than the latest release tag"
        raise ValueError(msg)


__all__ = [
    "next_tag",
    "parse_tag",
    "previous_tag",
    "require_newer_tag",
]
