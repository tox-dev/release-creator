"""Keep fragment options beside PR link insertion."""

from pathlib import Path
lazy import argparse

lazy from release_creator.fragments.git import commit_subjects_from_git
lazy from release_creator.fragments.links import add_pull_request_links
lazy from release_creator.fragments.pull_requests import pull_request_authors, validate_repository


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Keep fragment options with the fragment command."""
    fragments = commands.add_parser("fragments", help="link named fragments to their squash pull requests")
    fragments.add_argument("--directory", type=Path, default=Path("changelog.d"), help="Towncrier fragment directory")
    fragments.add_argument("--repository", required=True, help="GitHub owner/repository")
    fragments.add_argument(
        "--resolve-authors",
        action="store_true",
        help="add verified human PR authors using GitHub CLI read access",
    )
    source = fragments.add_mutually_exclusive_group(required=True)
    source.add_argument("--commit-map", type=Path, help="TSV file of fragment names and squash subjects")
    source.add_argument("--git", action="store_true", help="read each fragment's introducing squash commit from Git")
    fragments.set_defaults(handler=_link)


def _link(args: argparse.Namespace) -> None:
    validate_repository(args.repository)
    commit_subjects = (
        dict(line.split("\t", 1) for line in args.commit_map.read_text(encoding="utf-8").splitlines())
        if args.commit_map is not None
        else commit_subjects_from_git(args.directory)
    )
    authors = pull_request_authors(args.repository, commit_subjects) if args.resolve_authors else None
    add_pull_request_links(args.directory, args.repository, commit_subjects, authors)


__all__ = [
    "register",
]
