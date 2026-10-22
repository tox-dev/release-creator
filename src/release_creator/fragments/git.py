"""Find the commits that introduced pending fragments."""

import shutil
lazy from pathlib import Path

from release_creator.process import run_text
lazy from release_creator.fragments.names import pending_changesets, pending_fragments


def fragment_commits_from_git(directory: Path, *, knope: bool = False) -> dict[str, str]:
    """Read pending fragment origins in one Git history query.

    :param directory: Fragment directory in the checkout.
    :param knope: Use Knope changesets instead of Towncrier fragments.
    :returns: Fragment filenames mapped to introducing commit hashes.
    :raises FileNotFoundError: Git is not installed.
    :raises ValueError: Git cannot read the checkout history or a fragment has no introducing commit.
    """
    if (git := shutil.which("git")) is None:
        msg = "Git is required to read fragment history"
        raise FileNotFoundError(msg)
    fragments = (pending_changesets if knope else pending_fragments)(directory)
    result = run_text([
        git,
        "log",
        "--format=COMMIT%x09%H",
        "--name-only",
        "--no-renames",
        "--diff-filter=A",
        "HEAD",
        "--",
        str(directory),
    ])
    if result.returncode:
        msg = result.stderr.strip() or f"could not read Git history for {directory}"
        raise ValueError(msg)
    pending = {fragment.name for fragment in fragments}
    commits: dict[str, str] = {}
    commit = ""
    for line in result.stdout.splitlines():
        if line.startswith("COMMIT\t"):
            commit = line.partition("\t")[2]
        elif line and (name := Path(line).name) in pending:
            commits.setdefault(name, commit)
    if missing := pending - commits.keys():
        msg = f"no introducing Git commit for {', '.join(sorted(missing))}"
        raise ValueError(msg)
    return commits


__all__ = [
    "fragment_commits_from_git",
]
