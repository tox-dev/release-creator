"""Calculate numeric tags and find their predecessors."""

from __future__ import annotations

lazy from collections import Counter
lazy from pathlib import Path

lazy from packaging.version import InvalidVersion, Version

lazy from release_creator.explain import counted, explain
lazy from release_creator.fragments.names import fragment_category


def next_tag(bump: str, tags: list[str], fragments: list[str], prefix: str = "") -> str:
    """Choose a release version from existing tags and pending fragments.

    :param bump: ``auto``, ``major``, ``minor``, or ``patch``.
    :param tags: Existing repository tags.
    :param fragments: Pending fragment filenames.
    :param prefix: Optional prefix for the new tag.
    :returns: The next major.minor.patch version, with the requested prefix.
    """
    if releases := _release_versions(tags):
        current, current_tag = max(releases)
        explain(f"Current version: {current_tag} (newest of {counted(len(releases), 'release tag')})")
    else:
        current, current_tag = Version("0.0.0"), "0.0.0"
        explain("Current version: 0.0.0 (no release tags yet)")
    reason = f"{bump} bump requested"
    if bump == "auto":
        bump, reason = _auto_bump(fragments)
    if _finalizes_prerelease(current, bump):
        version = f"{prefix}{current.base_version}"
        explain(f"Next version: {version} ({reason}, finalizing prerelease {current_tag})")
        return version
    major, minor, patch = current.release
    numbers = {"major": (major + 1, 0, 0), "minor": (major, minor + 1, 0), "patch": (major, minor, patch + 1)}[bump]
    version = f"{prefix}{'.'.join(map(str, numbers))}"
    explain(f"Next version: {version} ({reason})")
    return version


def _auto_bump(fragments: list[str]) -> tuple[str, str]:
    kinds = Counter(fragment_category(Path(fragment)) or "unrecognized" for fragment in fragments)
    bump = "major" if kinds.keys() & {"breaking", "removal"} else "minor" if "feature" in kinds else "patch"
    if not fragments:
        return bump, f"{bump} bump: no pending fragments"
    found = ", ".join(f"{number} {kind}" for kind, number in sorted(kinds.items()))
    return bump, f"{bump} bump from {counted(len(fragments), 'pending fragment')}: {found}"


def _finalizes_prerelease(current: Version, bump: str) -> bool:
    if not current.is_prerelease:
        return False
    _, minor, patch = current.release
    return bump == "patch" or (bump == "minor" and patch == 0) or (bump == "major" and minor == patch == 0)


def previous_tag(tag: str, tags: list[str]) -> str | None:
    """Select the greatest numeric release tag before ``tag``.

    :param tag: Release tag whose predecessor is needed.
    :param tags: Existing repository tags.
    :returns: The preceding tag, or ``None`` when this is the first release or ``tag`` is not a release version.
    """
    try:
        target = parse_tag(tag)
    except ValueError:
        explain(f"Previous release tag: none ({tag} is not a major.minor.patch tag)")
        return None
    if not (candidates := [(version, name) for version, name in _release_versions(tags) if version < target]):
        explain(f"Previous release tag: none (no release tag before {tag})")
        return None
    previous = max(candidates)[1]
    explain(f"Previous release tag: {previous} (newest release tag before {tag})")
    return previous


def _release_versions(tags: list[str]) -> list[tuple[Version, str]]:
    releases: list[tuple[Version, str]] = []
    ignored: list[str] = []
    for tag in tags:
        try:
            releases.append((parse_tag(tag), tag))
        except ValueError:
            ignored.append(tag)
    if ignored:
        explain(f"Ignored {counted(len(ignored), 'non-release tag')} (not major.minor.patch): {', '.join(ignored)}")
    return releases


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
]
