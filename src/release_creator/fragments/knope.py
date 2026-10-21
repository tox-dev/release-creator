"""Read Knope changesets without rewriting their YAML front matter."""

lazy from pathlib import Path


def changeset_parts(fragment: Path, content: str) -> tuple[str, str, str]:
    """Separate a changeset's front matter, heading, and remaining text.

    Returns:
        Front matter, heading text, and text following the heading.

    Raises:
        ValueError: The changeset has no front matter or summary heading.

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
]
