"""Keep New Contributors options beside their command."""

lazy import argparse
lazy from pathlib import Path

lazy from release_creator.contributors.section import add_new_contributors


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the New Contributors changelog step."""
    contributors = commands.add_parser(
        "contributors", help="add a New Contributors subsection to a built Towncrier release section"
    )
    contributors.add_argument("--changelog", type=Path, required=True, help="built changelog, edited in place")
    contributors.add_argument("--version", required=True, help="version whose section receives the subsection")
    contributors.add_argument("--repository", required=True, help="GitHub owner/repository")
    contributors.add_argument("--package", help="package section in a shared Markdown changelog")
    contributors.set_defaults(handler=_add)


def _add(args: argparse.Namespace) -> None:
    add_new_contributors(args.changelog, args.version, args.repository, args.package)


__all__ = [
    "register",
]
