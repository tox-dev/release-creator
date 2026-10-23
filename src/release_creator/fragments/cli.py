"""Keep fragment options beside PR link insertion."""

from pathlib import Path
lazy import argparse
lazy import sys

lazy from release_creator.fragments.check import changed_changesets, changed_fragments, validate_fragment_deletions
lazy from release_creator.fragments.git import fragment_commits_from_git
lazy from release_creator.fragments.links import add_pull_request_links
lazy from release_creator.fragments.names import pending_changesets, pending_fragments
lazy from release_creator.fragments.pull_requests import fragment_pull_requests
lazy from release_creator.github import validate_repository


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Keep fragment options with the fragment command."""
    fragments = commands.add_parser("fragments", help="link fragments to their merged pull requests")
    fragments.add_argument("--format", choices=("towncrier", "knope"), default="towncrier", help="fragment format")
    fragments.add_argument("--directory", type=Path, help="fragment directory; defaults to changelog.d or .changeset")
    fragments.add_argument("--repository", required=True, help="GitHub owner/repository")
    fragments.add_argument(
        "--numbered-prs", action="store_true", help="treat numeric Towncrier fragment stems as PR numbers"
    )
    fragments.set_defaults(handler=_link)
    news = commands.add_parser("validate-news", help="validate changed pull request fragments")
    news.add_argument("--format", choices=("towncrier", "knope"), default="towncrier", help="fragment format")
    news.add_argument("--base", required=True, help="pull request base branch")
    news.set_defaults(handler=_check)
    deletions = commands.add_parser("validate-fragment-deletions", help="check staged Towncrier fragment deletions")
    deletions.set_defaults(handler=_check_deletions)


def _link(args: argparse.Namespace) -> None:
    validate_repository(args.repository)
    knope = args.format == "knope"
    if knope and args.numbered_prs:
        msg = "--numbered-prs applies only to Towncrier fragments"
        raise ValueError(msg)
    directory = args.directory or Path(".changeset" if knope else "changelog.d")
    (pending_changesets if knope else pending_fragments)(directory)
    commits = fragment_commits_from_git(directory, knope=knope)
    pull_requests = fragment_pull_requests(args.repository, commits, numbered_prs=args.numbered_prs)
    mode = "knope" if knope else "numbered-prs" if args.numbered_prs else "towncrier"
    add_pull_request_links(directory, args.repository, pull_requests, mode=mode)


def _check(args: argparse.Namespace) -> None:
    knope = args.format == "knope"
    config = Path("knope.toml" if knope else "pyproject.toml")
    sys.stdout.write(f"{(changed_changesets if knope else changed_fragments)(config, args.base)}\n")


def _check_deletions(_: argparse.Namespace) -> None:
    validate_fragment_deletions(Path("pyproject.toml"))


__all__ = [
    "register",
]
