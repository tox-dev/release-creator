"""Find the commits that introduced pending fragments."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # The dataclass decorator resolves during module load.
from __future__ import annotations

lazy from dataclasses import dataclass
lazy from pathlib import Path

lazy from release_creator.fragments.names import pending_changesets, pending_fragments
lazy from release_creator.fragments.pull_requests import PullRequestCredit, commit_author_credits
lazy from release_creator.process import run_text


def is_shallow_clone(directory: Path) -> bool:
    """Detect a shallow checkout, whose oldest commit stands in for the commits it cut off, so it credits no one.

    :param directory: Fragment directory in the checkout.
    :returns: Whether Git reports the repository as shallow.
    """
    return run_text(["git", "rev-parse", "--is-shallow-repository"], cwd=directory).stdout.strip() == "true"


def fragment_commits_from_git(directory: Path, *, knope: bool = False) -> dict[str, FragmentCommit]:
    """Read pending fragment origins in one Git history query.

    :param directory: Fragment directory in the checkout.
    :param knope: Use Knope changesets instead of Towncrier fragments.
    :returns: Fragment filenames mapped to their introducing commits; a fragment without one is left out.
    :raises ValueError: Git cannot read the checkout history.
    """
    fragments = (pending_changesets if knope else pending_fragments)(directory)
    result = run_text(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "log",
            "--relative",
            "--format=COMMIT%x09%H%x09%aN%x09%aE%x00",
            "--name-status",
            "--find-renames",
            "-z",
            "HEAD",
            "--",
            ".",
        ],
        cwd=directory,
    )
    if result.returncode:
        msg = result.stderr.strip() or f"could not read Git history for {directory}"
        raise ValueError(msg)
    origins = _origin_commits(result.stdout, {fragment.name for fragment in fragments})
    return {name: _fragment_commit(header) for name, header in origins.items()}


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
            old, new = next(fields), next(fields)
            for name, origin in origins.items():
                if origin == new and name not in commits:
                    origins[name] = old
        elif status.startswith("A"):
            path = next(fields)
            for name, origin in origins.items():
                if origin == path and name not in commits:
                    commits[name] = commit
        elif status and status[0] in "MDCUTB":
            next(fields)
    return commits


def _fragment_commit(header: str) -> FragmentCommit:
    sha, _, author = header.partition("\t")
    name, _, email = author.rpartition("\t")
    return FragmentCommit(sha=sha, credits=commit_author_credits(name, email))


@dataclass(frozen=True, kw_only=True)
class FragmentCommit:
    """Commit that introduced a pending fragment, with its author's credit; empty for an AI assistant."""

    sha: str
    credits: tuple[PullRequestCredit, ...]


__all__ = [
    "FragmentCommit",
    "fragment_commits_from_git",
    "is_shallow_clone",
]
