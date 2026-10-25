"""Stable names for release and draft section anchors."""


def release_anchor(tag: str, category: str | None = None) -> str:
    """Build the anchor of a release or one of its sections.

    :param tag: Release version or scoped tag.
    :param category: Optional section heading.
    :returns: Stable release anchor name.
    """
    anchor = f"release-{tag.replace('.', '-').replace('/', '-')}"
    return f"{anchor}-{category.lower().replace(' ', '-')}" if category is not None and bool(category) else anchor


def draft_anchor(package: str | None = None, category: str | None = None) -> str:
    """Build the anchor of a package draft or one of its sections.

    :param package: Package heading, or none for a shared changelog.
    :param category: Optional section heading.
    :returns: Stable draft anchor name.
    """
    anchor = f"draft-{package}" if package is not None and bool(package) else "draft"
    return f"{anchor}-{category.lower().replace(' ', '-')}" if category is not None and bool(category) else anchor


__all__ = [
    "draft_anchor",
    "release_anchor",
]
