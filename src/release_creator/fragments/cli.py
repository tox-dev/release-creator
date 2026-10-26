"""Keep fragment options beside PR link insertion."""

lazy import argparse
lazy import sys
lazy from pathlib import Path

lazy from release_creator.explain import counted, explain
lazy from release_creator.fragments.check import changed_changesets, changed_fragments
lazy from release_creator.fragments.git import fragment_commits_from_git, is_shallow_clone
lazy from release_creator.fragments.links import add_pull_request_links
lazy from release_creator.fragments.pull_requests import fragment_pull_requests


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Keep fragment options with the fragment command."""
    fragments = commands.add_parser("fragments", help="link fragments to their merged pull requests")
    fragments.add_argument("--format", choices=("towncrier", "knope"), default="towncrier", help="fragment format")
    fragments.add_argument("--directory", type=Path, help="fragment directory; defaults to changelog.d or .changeset")
    fragments.add_argument("--repository", required=True, help="GitHub owner/repository")
    fragments.set_defaults(handler=_link)
    news = commands.add_parser("validate-news", help="validate changed pull request fragments")
    news.add_argument("--format", choices=("towncrier", "knope"), default="towncrier", help="fragment format")
    news.add_argument("--base", required=True, help="pull request base branch")
    news.set_defaults(handler=_check)


def _link(args: argparse.Namespace) -> None:
    knope = args.format == "knope"
    if args.directory is not None:
        directory, source = args.directory, "from --directory"
    else:
        directory, source = Path(".changeset" if knope else "changelog.d"), f"default for {args.format}"
    explain(f"Fragment directory: {directory.as_posix()} ({source})")
    if is_shallow_clone(directory):
        explain("Shallow clone: the history that added the fragments is cut off, so they stay unchanged")
        return
    commits = fragment_commits_from_git(directory, knope=knope)
    pull_requests = fragment_pull_requests(args.repository, {name: commit.sha for name, commit in commits.items()})
    mode = "knope" if knope else "towncrier"
    add_pull_request_links(directory, args.repository, pull_requests, commits=commits, mode=mode)


def _check(args: argparse.Namespace) -> None:
    knope = args.format == "knope"
    config = Path("knope.toml" if knope else "pyproject.toml")
    count = (changed_changesets if knope else changed_fragments)(config, args.base)
    explain(
        f"Validated {counted(count, 'changed changeset' if knope else 'changed fragment')} against origin/{args.base}"
    )
    sys.stdout.write(f"{count}\n")


__all__ = [
    "register",
]
