"""Find the commits that introduced pending fragments."""

lazy from pathlib import Path

lazy from release_creator.fragments.names import pending_changesets, pending_fragments
lazy from release_creator.process import required_executable, run_text


def fragment_commits_from_git(directory: Path, *, knope: bool = False) -> dict[str, str]:
    """Read pending fragment origins in one Git history query.

    :param directory: Fragment directory in the checkout.
    :param knope: Use Knope changesets instead of Towncrier fragments.
    :returns: Fragment filenames mapped to introducing commit hashes.
    :raises ValueError: Git cannot read the checkout history or a fragment has no introducing commit.
    """
    git = required_executable("git")
    shallow = run_text([git, "rev-parse", "--is-shallow-repository"])
    if shallow.returncode:
        msg = shallow.stderr.strip() or f"could not read Git history for {directory}"
        raise ValueError(msg)
    if shallow.stdout.strip() == "true":
        msg = "full Git history is required to attribute changelog fragments"
        raise ValueError(msg)
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
