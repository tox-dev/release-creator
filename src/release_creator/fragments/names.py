"""Keep unlinked fragments out of release output."""

lazy from pathlib import Path


def pending_fragments(directory: Path) -> list[Path]:
    """Reject names Towncrier would publish without a PR reference.

    :param directory: Towncrier fragment directory.
    :returns: Pending fragment paths.
    :raises ValueError: A fragment lacks a supported name.
    """
    fragments = sorted(path for extension in ("md", "rst") for path in directory.glob(f"*.*.{extension}"))
    for fragment in fragments:
        stem = fragment.name.partition(".")[0]
        if not ((stem.startswith("+") and len(stem) > 1) or fragment_number(fragment) is not None):
            msg = f"unsupported changelog fragment name {fragment.name!r}; prefix a name with + or use a PR number"
            raise ValueError(msg)
    return fragments


def pending_changesets(directory: Path) -> list[Path]:
    """List Knope changesets, excluding its directory guide.

    :param directory: Knope changeset directory.
    :returns: Pending Markdown changeset paths.
    """
    return sorted(path for path in directory.glob("*.md") if path.name != "README.md")


def fragment_number(fragment: Path) -> str | None:
    """Recognize legacy issue-number fragments before finding their pull requests.

    :param fragment: Fragment whose stem may be a PR number.
    :returns: The filename's issue number, or None for a named fragment.
    """
    stem = fragment.name.partition(".")[0]
    return stem if stem.isascii() and stem.isdecimal() else None


__all__ = [
    "fragment_number",
    "pending_changesets",
    "pending_fragments",
]
