"""Validate repository names used in GitHub URLs and API paths."""

lazy import re


def validate_repository(repository: str) -> None:
    """Reject repository names that cannot form GitHub API paths.

    :param repository: GitHub owner and repository.
    :raises ValueError: The repository is not in owner/name form.
    """
    if (
        re.fullmatch(
            r"""
        (?P<owner>[A-Za-z0-9_.-]+)  # GitHub owner
        /                            # Repository separator
        (?P<name>[A-Za-z0-9_.-]+)   # GitHub repository
        """,
            repository,
            re.VERBOSE,
        )
        is None
    ):
        msg = f"invalid repository: {repository}"
        raise ValueError(msg)


__all__ = [
    "validate_repository",
]
