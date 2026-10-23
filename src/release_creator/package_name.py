"""Validate package names used in release headings and scoped tags."""

lazy import re


def valid_package_name(package: str) -> bool:
    """Check a package name used as one release path component.

    :param package: Candidate package name.
    :returns: Whether the package is one safe path component.
    """
    return (
        re.fullmatch(
            r"""
            (?P<package>[A-Za-z0-9][A-Za-z0-9_.-]*)  # One non-relative package or tag path component
            """,
            package,
            re.VERBOSE,
        )
        is not None
    )


__all__ = [
    "valid_package_name",
]
