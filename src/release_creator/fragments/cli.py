"""Keep fragment options beside PR link insertion."""

from pathlib import Path
lazy import argparse
lazy import sys

lazy from release_creator.fragments.check import changed_changesets, changed_fragments
lazy from release_creator.fragments.git import commit_subjects_from_git
lazy from release_creator.fragments.links import add_pull_request_links
lazy from release_creator.fragments.names import pending_changesets, pending_fragments
lazy from release_creator.fragments.pull_requests import pull_request_authors, validate_repository


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Keep fragment options with the fragment command."""
    fragments = commands.add_parser("fragments", help="link named fragments to their squash pull requests")
    fragments.add_argument("--format", choices=("towncrier", "knope"), default="towncrier", help="fragment format")
    fragments.add_argument("--directory", type=Path, help="fragment directory; defaults to changelog.d or .changeset")
    fragments.add_argument("--repository", required=True, help="GitHub owner/repository")
    fragments.add_argument(
        "--numbered-prs", action="store_true", help="treat numeric Towncrier fragment stems as PR numbers"
    )
    fragments.add_argument(
        "--resolve-authors",
        action="store_true",
        help="add verified human PR authors using GitHub CLI read access",
    )
    source = fragments.add_mutually_exclusive_group(required=True)
    source.add_argument("--commit-map", type=Path, help="TSV file of fragment names and squash subjects")
    source.add_argument("--git", action="store_true", help="read each fragment's introducing squash commit from Git")
    fragments.set_defaults(handler=_link)
    news = commands.add_parser("validate-news", help="validate changed pull request fragments")
    news.add_argument("--format", choices=("towncrier", "knope"), default="towncrier", help="fragment format")
    news.add_argument("--config", type=Path, help="configuration; defaults to pyproject.toml or knope.toml")
    news.add_argument("--base", required=True, help="pull request base branch")
    news.set_defaults(handler=_check)


def _link(args: argparse.Namespace) -> None:
    validate_repository(args.repository)
    knope = args.format == "knope"
    if knope and args.numbered_prs:
        msg = "--numbered-prs applies only to Towncrier fragments"
        raise ValueError(msg)
    directory = args.directory or Path(".changeset" if knope else "changelog.d")
    (pending_changesets if knope else pending_fragments)(directory)
    commit_subjects = (
        dict(line.split("\t", 1) for line in args.commit_map.read_text(encoding="utf-8").splitlines())
        if args.commit_map is not None
        else commit_subjects_from_git(directory, knope=knope)
    )
    authors = (
        pull_request_authors(args.repository, commit_subjects, numbered_prs=args.numbered_prs)
        if args.resolve_authors
        else None
    )
    mode = "knope" if knope else "numbered-prs" if args.numbered_prs else "towncrier"
    add_pull_request_links(directory, args.repository, commit_subjects, authors, mode=mode)


def _check(args: argparse.Namespace) -> None:
    knope = args.format == "knope"
    config = args.config or Path("knope.toml" if knope else "pyproject.toml")
    sys.stdout.write(f"{(changed_changesets if knope else changed_fragments)(config, args.base)}\n")


__all__ = [
    "register",
]
