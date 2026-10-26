"""Read Knope changesets without rewriting their YAML front matter."""

lazy import tomllib
lazy from itertools import takewhile
lazy from pathlib import Path
lazy from typing import Any, cast


def load_knope_package(config: Path) -> dict[str, object]:
    """Read the package from a Knope configuration.

    :param config: Knope configuration path.
    :returns: The ``[package]`` table, or else the first ``[packages.<name>]`` table.
    """
    document = tomllib.loads(config.read_text(encoding="utf-8"))
    package = document["package"] if "package" in document else next(iter(document["packages"].values()))
    return {str(key): value for key, value in package.items()}


def knope_kinds(config: dict[str, object]) -> set[str]:
    """Return types accepted by Knope's standard and extra sections.

    :param config: Knope package configuration.
    :returns: Accepted changeset types.
    """
    return {"major", "minor", "patch"} | {kind for _, kinds in knope_sections(config) for kind in kinds}


def knope_sections(config: dict[str, object]) -> list[tuple[str, list[str]]]:
    """Read named changeset sections.

    :param config: Knope package configuration.
    :returns: Section names and their accepted types.
    """
    sections = cast("list[dict[str, Any]]", config.get("extra_changelog_sections", []))
    return [(section["name"], section.get("types", [])) for section in sections]


def changeset_versioning(fragment: Path, content: str) -> dict[str, str]:
    """Read a changeset's package change types the way Knope does.

    Knope reads each front matter line as ``package: type`` split at the first colon, not as YAML, so quotes and
    comments stay part of the name or type.

    :param fragment: Changeset path used in errors.
    :param content: Complete changeset text.
    :returns: Change type keyed by package name.
    :raises ValueError: The front matter is missing, invalid, or empty.
    """
    lines = content.removesuffix("\n").split("\n")
    if lines[0].strip() != "---":
        msg = f"missing YAML front matter in {fragment}"
        raise ValueError(msg)
    entries = list(takewhile(lambda line: line.strip() != "---", lines[1:]))
    pairs = [line.partition(":") for line in entries]
    if not all(colon for _, colon, _ in pairs):
        msg = f"invalid changeset front matter in {fragment}"
        raise ValueError(msg)
    if not (versioning := {package.strip(): kind.strip() for package, _, kind in pairs}):
        msg = f"empty changeset front matter in {fragment}"
        raise ValueError(msg)
    # Knope skips as many lines as it kept packages before expecting the closing fence, so a repeated package fails.
    if len(versioning) != len(entries) or len(entries) + 1 == len(lines):
        msg = f"invalid changeset front matter in {fragment}"
        raise ValueError(msg)
    return versioning


def changeset_parts(fragment: Path, content: str) -> tuple[str, str, str]:
    """Separate a changeset's front matter, heading, and remaining text.

    :param fragment: Changeset path used in errors.
    :param content: Complete changeset text.
    :returns: Front matter, heading text, and text following the heading.
    :raises ValueError: The changeset has no front matter or summary heading.
    """
    if not content.startswith("---\n") or (boundary := content.find("\n---\n", 3)) == -1:
        msg = f"missing YAML front matter in {fragment}"
        raise ValueError(msg)
    frontmatter = content[: boundary + 5]
    rest = content[boundary + 5 :]
    if not rest.startswith("\n# "):
        msg = f"missing level-one changeset heading in {fragment}"
        raise ValueError(msg)
    heading, _, remainder = rest[3:].partition("\n")
    if not heading.strip():
        msg = f"empty changeset summary in {fragment}"
        raise ValueError(msg)
    return f"{frontmatter}\n", heading, f"\n{remainder}"


__all__ = [
    "changeset_parts",
    "changeset_versioning",
    "knope_kinds",
    "knope_sections",
    "load_knope_package",
]
