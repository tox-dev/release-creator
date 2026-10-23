"""Read Knope changesets without rewriting their YAML front matter."""

lazy import tomllib
lazy from pathlib import Path


def load_knope_package(config: Path) -> dict[str, object]:
    """Read one package from a Knope configuration.

    :param config: Knope configuration path.
    :returns: The configured package.
    :raises ValueError: The package layout is absent or ambiguous.
    """
    document = tomllib.loads(config.read_text(encoding="utf-8"))
    package = document.get("package")
    if package is None and isinstance(packages := document.get("packages"), dict) and len(packages) == 1:
        package = next(iter(packages.values()))
    if isinstance(package, dict):
        return {str(key): value for key, value in package.items()}
    msg = f"expected one [package] or [packages.<name>] in {config}"
    raise ValueError(msg)


def knope_kinds(config: dict[str, object]) -> set[str]:
    """Return types accepted by Knope's standard and extra sections.

    :param config: Knope package configuration.
    :returns: Accepted changeset types.
    """
    return {"major", "minor", "patch"} | {kind for _, kinds in knope_sections(config) for kind in kinds}


def knope_sections(config: dict[str, object]) -> list[tuple[str, list[str]]]:
    """Validate named changeset sections.

    :param config: Knope package configuration.
    :returns: Section names and their accepted types.
    :raises TypeError: The section collection has an invalid type.
    :raises ValueError: A section lacks its name or sources.
    """
    sections = config.get("extra_changelog_sections", [])
    if not isinstance(sections, list):
        msg = "Knope changelog sections need a name and nonempty types or footers"
        raise TypeError(msg)
    result: list[tuple[str, list[str]]] = []
    for section in sections:
        if not isinstance(section, dict):
            msg = "Knope changelog sections need a name and nonempty types or footers"
            raise TypeError(msg)
        name, kinds, footers = section.get("name"), section.get("types", []), section.get("footers", [])
        if not isinstance(name, str) or not name or not isinstance(kinds, list) or not isinstance(footers, list):
            msg = "Knope changelog sections need a name and nonempty types or footers"
            raise ValueError(msg)
        if (
            not (kinds or footers)
            or not all(isinstance(kind, str) for kind in kinds)
            or not all(isinstance(footer, str) for footer in footers)
        ):
            msg = "Knope changelog sections need a name and nonempty types or footers"
            raise ValueError(msg)
        result.append((name, kinds))
    return result


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
    "knope_kinds",
    "knope_sections",
    "load_knope_package",
]
