"""Associate named Towncrier fragments with merged pull requests."""

from __future__ import annotations

import re
lazy from pathlib import Path


def add_pull_request_links(directory: Path, repository: str, commit_subjects: dict[str, str]) -> None:
    """Add pull request links to named fragments using squash commit subjects.

    Raises:
        ValueError: A fragment has no unambiguous squash commit or already names a pull request.

    """
    if not re.fullmatch(
        r"""
        (?P<owner>[A-Za-z0-9_.-]+)  # GitHub owner
        /                            # Repository separator
        (?P<name>[A-Za-z0-9_.-]+)   # GitHub repository
        """,
        repository,
        re.VERBOSE,
    ):
        msg = f"invalid repository: {repository}"
        raise ValueError(msg)
    for fragment in sorted(directory.glob("+*.*")):
        subject = commit_subjects.get(fragment.name, "")
        if (
            match := re.search(
                r"""
                \(\#                    # Squash merge PR marker
                (?P<number>\d+)       # Pull request number
                \)$                    # Marker ends the subject
                """,
                subject,
                re.VERBOSE,
            )
        ) is None:
            msg = f"no squash pull request number for {fragment}: {subject}"
            raise ValueError(msg)
        content = fragment.read_text(encoding="utf-8").rstrip()
        if re.search(
            rf"""
            https://github\.com/       # GitHub host
            {re.escape(repository)}    # This repository
            /pull/                      # Pull request route
            (?P<number>\d+)            # Existing pull request link
            """,
            content,
            re.VERBOSE,
        ):
            msg = f"pull request already linked in {fragment}"
            raise ValueError(msg)
        link = f"([#{match['number']}](https://github.com/{repository}/pull/{match['number']}))"
        content, count = re.subn(
            r"""
            (?P<before>,?\s+)           # Optional comma and space before author credit
            by
            (?P<after>\s+)             # Space after credit marker
            (?=\[@|:user:)              # Markdown or RST author link
            """,
            f" {link} by ",
            content,
            count=1,
            flags=re.VERBOSE,
        )
        if not count:
            content = f"{content.removesuffix('.')} {link}."
        fragment.write_text(f"{content}\n", encoding="utf-8")


__all__ = [
    "add_pull_request_links",
]
