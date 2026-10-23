"""Find the commits that introduced pending fragments."""

lazy from pathlib import Path

lazy from release_creator.fragments.names import pending_changesets, pending_fragments
lazy from release_creator.process import required_executable, run_text


def fragment_commits_from_git(directory: Path, *, knope: bool = False) -> dict[str, str]:
    """Read pending fragment origins in one Git history query.

    A missing Git executable raises :exc:`FileNotFoundError`.

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
        "-c",
        "core.quotePath=false",
        "log",
        "--format=COMMIT%x09%H%x00",
        "--name-status",
        "--find-renames",
        "-z",
        "HEAD",
        "--",
        str(directory),
    ])
    if result.returncode:
        msg = result.stderr.strip() or f"could not read Git history for {directory}"
        raise ValueError(msg)
    pending = {fragment.name for fragment in fragments}
    commits = _origin_commits(result.stdout, pending)
    if missing := pending - commits.keys():
        msg = f"no introducing Git commit for {', '.join(sorted(missing))}"
        raise ValueError(msg)
    return commits


def _origin_commits(history: str, pending: set[str]) -> dict[str, str]:
    origins = {name: name for name in pending}
    commits: dict[str, str] = {}
    commit = ""
    fields = iter(history.split("\0"))
    for field in fields:
        status = field.lstrip("\n")
        if status.startswith("COMMIT\t"):
            commit = status.partition("\t")[2]
        elif status.startswith("R"):
            old, new = Path(next(fields)).name, Path(next(fields)).name
            for name, origin in origins.items():
                if origin == new and name not in commits:
                    origins[name] = old
        elif status.startswith("A"):
            path = Path(next(fields)).name
            for name, origin in origins.items():
                if origin == path and name not in commits:
                    commits[name] = commit
        elif status and status[0] in "MDCUTB":
            next(fields)
    return commits


__all__ = [
    "fragment_commits_from_git",
]
