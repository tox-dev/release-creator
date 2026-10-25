"""Names shared by changelog previews and GitHub Release notes."""

lazy from typing import Final

CHANGELOG_CATEGORIES: Final = {
    "feature": ("Added", "Features"),
    "change": ("Changes", "Changes"),
    "bugfix": ("Fixed", "Bug fixes"),
    "doc": ("Documentation", "Documentation"),
    "breaking": ("Breaking changes", "Breaking changes"),
    "security": ("Security", "Security"),
    "performance": ("Performance", "Performance"),
    "deprecation": ("Deprecated", "Deprecations"),
    "removal": ("Removed", "Removals"),
    "packaging": ("Packaging", "Packaging"),
}
RELEASE_CATEGORIES: Final = dict(CHANGELOG_CATEGORIES.values()) | {"Other changes": "Other changes"}

__all__ = [
    "CHANGELOG_CATEGORIES",
    "RELEASE_CATEGORIES",
]
