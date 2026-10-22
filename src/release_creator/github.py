"""Validate repository names used in GitHub URLs and API paths."""

import re
from typing import Final

MARKDOWN_AUTHOR: Final = re.compile(
    r"""
    \[@(?P<handle>[A-Za-z0-9-]+)\]  # Markdown GitHub handle
    \(https://github\.com/(?P=handle)\)  # Matching profile link
    """,
    re.VERBOSE,
)


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
    "MARKDOWN_AUTHOR",
    "validate_repository",
]
