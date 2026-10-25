"""Recognize Towncrier fragment names."""

lazy from collections.abc import Collection
lazy from pathlib import Path
lazy from typing import Final


def pending_fragments(directory: Path) -> list[Path]:
    """Reject names Towncrier would publish without a PR reference.

    :param directory: Towncrier fragment directory.
    :returns: Pending fragment paths.
    :raises ValueError: A fragment lacks a supported name.
    """
    fragments = sorted(path for extension in ("md", "rst") for path in directory.glob(f"*.*.{extension}"))
    for fragment in fragments:
        if fragment_category(fragment) is None:
            msg = f"unsupported changelog fragment name {fragment.name!r}; prefix a name with + or use a PR number"
            raise ValueError(msg)
    return fragments


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


__all__ = [
    "fragment_category",
    "pending_fragments",
]
