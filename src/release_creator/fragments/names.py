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
    """Recognize a numbered or orphan fragment, including Towncrier's optional counter.

    :param fragment: Fragment path.
    :param categories: Configured Towncrier category names, when available.
    :returns: The category, or None if the filename is unsupported.
    """
    minimum_parts: Final[int] = 2
    parts = fragment.stem.split(".")
    if len(parts) > minimum_parts and parts[-1].isdigit():
        parts.pop()
    if len(parts) < minimum_parts:
        return None
    category = parts.pop()
    identifier = ".".join(parts)
    if categories is not None and category not in categories:
        return None
    if (identifier.isascii() and identifier.isdecimal()) or (identifier.startswith("+") and len(identifier) > 1):
        return category
    return None


def pending_changesets(directory: Path) -> list[Path]:
    """List Knope changesets, excluding its directory guide.

    :param directory: Knope changeset directory.
    :returns: Pending Markdown changeset paths.
    """
    return sorted(path for path in directory.glob("*.md") if path.name != "README.md")


__all__ = [
    "fragment_category",
    "pending_changesets",
    "pending_fragments",
]
