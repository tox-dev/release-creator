"""Read introducing squash subjects from Git history."""

import shutil
lazy from pathlib import Path

from release_creator.process import run_text
lazy from release_creator.fragments.names import pending_changesets, pending_fragments


def commit_subjects_from_git(directory: Path, *, knope: bool = False) -> dict[str, str]:
    """Use each fragment's first-add commit to identify its pull request.

    :param directory: Fragment directory in the checkout.
    :param knope: Use Knope changesets instead of Towncrier fragments.
    :returns: Fragment filenames mapped to their introducing subjects.
    :raises FileNotFoundError: Git is not installed.
    :raises ValueError: Git cannot read the checkout history.
    """
    if (git := shutil.which("git")) is None:
        msg = "Git is required to read fragment history"
        raise FileNotFoundError(msg)
    subjects: dict[str, str] = {}
    for fragment in pending_changesets(directory) if knope else pending_fragments(directory):
        result = run_text([git, "log", "-1", "--format=%s", "--diff-filter=A", "HEAD", "--", str(fragment)])
        if result.returncode:
            msg = result.stderr.strip() or f"could not read Git history for {fragment}"
            raise ValueError(msg)
        subjects[fragment.name] = result.stdout.strip()
    return subjects


__all__ = [
    "commit_subjects_from_git",
]
