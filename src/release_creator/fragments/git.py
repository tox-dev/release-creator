"""Read introducing squash subjects from Git history."""

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Git history supplies fragment provenance.
lazy from pathlib import Path

lazy from release_creator.fragments.names import pending_changesets, pending_fragments


def commit_subjects_from_git(directory: Path, *, knope: bool = False) -> dict[str, str]:
    """Use each fragment's first-add commit to identify its pull request.

    Returns:
        Fragment filenames mapped to their introducing subjects.

    Raises:
        FileNotFoundError: Git is not installed.
        ValueError: Git cannot read the checkout history.

    """
    if (git := shutil.which("git")) is None:
        msg = "Git is required to read fragment history"
        raise FileNotFoundError(msg)
    subjects: dict[str, str] = {}
    for fragment in pending_changesets(directory) if knope else pending_fragments(directory):
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Fixed Git argv.
            [git, "log", "-1", "--format=%s", "--diff-filter=A", "HEAD", "--", str(fragment)],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode:
            msg = result.stderr.strip() or f"could not read Git history for {fragment}"
            raise ValueError(msg)
        subjects[fragment.name] = result.stdout.strip()
    return subjects


__all__ = [
    "commit_subjects_from_git",
]
