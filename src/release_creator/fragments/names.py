"""Keep unlinked fragments out of release output."""

lazy from collections.abc import Collection
lazy from pathlib import Path
lazy from typing import Final


def pending_fragments(directory: Path) -> list[Path]:
    """List pending Towncrier fragments.

    :param directory: Towncrier fragment directory.
    :returns: Pending Markdown and reStructuredText fragment paths.
    """
    return sorted(path for extension in ("md", "rst") for path in directory.glob(f"*.*.{extension}"))


def fragment_category(fragment: Path, categories: Collection[str] | None = None) -> str | None:
    """Recognize a numbered or named fragment, including Towncrier's optional counter.

    :param fragment: Fragment path.
    :param categories: Configured Towncrier category names, when available.
    :returns: The category, or None if the filename is unsupported.
    """
    if (name := _fragment_name(fragment)) is None:
        return None
    identifier, category = name
    if categories is not None and category not in categories:
        return None
    if identifier and identifier != "+" and (identifier.isascii() or not identifier.isdecimal()):
        return category
    return None


def _fragment_name(fragment: Path) -> tuple[str, str] | None:
    minimum_parts: Final[int] = 2
    parts = fragment.stem.split(".")
    if len(parts) > minimum_parts and parts[-1].isdigit():
        parts.pop()
    return (".".join(parts[:-1]), parts[-1]) if len(parts) >= minimum_parts else None


def is_bare_fragment(fragment: Path) -> bool:
    """Identify a name that needs Towncrier's orphan prefix.

    :param fragment: Fragment path.
    :returns: Whether the name needs the prefix.
    """
    identifier = name[0] if (name := _fragment_name(fragment)) is not None else ""
    return bool(identifier and not identifier.startswith("+") and not (identifier.isascii() and identifier.isdecimal()))


def pending_changesets(directory: Path) -> list[Path]:
    """List Knope changesets, excluding its directory guide.

    :param directory: Knope changeset directory.
    :returns: Pending Markdown changeset paths.
    """
    return sorted(path for path in directory.glob("*.md") if path.name != "README.md")


__all__ = [
    "fragment_category",
    "is_bare_fragment",
    "pending_changesets",
    "pending_fragments",
]
