"""Validate numeric tags and find their predecessors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from packaging.version import InvalidVersion, Version

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
    versions: list[Version] = []
    for tag in tags:
        try:
            versions.append(parse_tag(tag))
        except ValueError:
            continue
    current = max(versions, default=Version("0.0.0"))
    major, minor, patch = current.release
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
            version = (major + 1, 0, 0)
        case "minor":
            version = (major, minor + 1, 0)
        case "patch":
            version = (major, minor, patch + 1)
        case "calver":
            year_month = release_date.year, release_date.month
            version = (*year_month, patch + 1 if (major, minor) == year_month else 0)
        case _:
            msg = f"unknown version bump: {bump}"
            raise ValueError(msg)
    if Version(".".join(map(str, version))) <= current:
        msg = f"calculated version must be newer than {current}"
        raise ValueError(msg)
    return f"{prefix}{'.'.join(map(str, version))}"


def previous_tag(tag: str, tags: list[str]) -> str | None:
    """Select the greatest numeric release tag before ``tag``.

    :param tag: Release tag whose predecessor is needed.
    :param tags: Existing repository tags.
    :returns: The preceding tag, or ``None`` when this is the first release.
    """
    target = parse_tag(tag)
    candidates: list[tuple[Version, str]] = []
    for candidate in tags:
        try:
            version = parse_tag(candidate)
        except ValueError:
            continue
        if version < target:
            candidates.append((version, candidate))
    return max(candidates)[1] if candidates else None


def require_newer_tag(tag: str, tags: list[str]) -> None:
    """Require ``tag`` to follow every existing numeric release tag.

    :param tag: Candidate release tag.
    :param tags: Existing repository tags.
    :raises ValueError: A matching or newer release tag already exists.
    """
    target = parse_tag(tag)
    versions: list[Version] = []
    for candidate in tags:
        try:
            versions.append(parse_tag(candidate))
        except ValueError:
            continue
    if versions and target <= max(versions):
        msg = f"{tag} must be newer than the latest release tag"
        raise ValueError(msg)


def parse_tag(tag: str) -> Version:
    """Parse a major.minor.patch release tag with an optional v prefix.

    :param tag: Version tag to parse.
    :returns: The canonical release version.
    :raises ValueError: The tag is not a numeric release version.
    """
    candidate = tag.removeprefix("v")
    try:
        version = Version(candidate)
    except InvalidVersion as error:
        msg = f"expected a major.minor.patch version with optional v prefix: {tag}"
        raise ValueError(msg) from error
    match version.release:
        case [_, _, _] if str(version) == candidate and not version.epoch and version.local is None:
            return version
        case _:
            msg = f"expected a major.minor.patch version with optional v prefix: {tag}"
            raise ValueError(msg)


__all__ = [
    "next_tag",
    "parse_tag",
    "previous_tag",
    "require_newer_tag",
]
