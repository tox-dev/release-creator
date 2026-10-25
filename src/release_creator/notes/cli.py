"""Keep note options beside the section extractor."""

lazy import argparse
lazy import sys
lazy from pathlib import Path

lazy from release_creator.notes.section import release_section


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the changelog section extractor."""
    notes = commands.add_parser("notes", help="print the changelog section of a release")
    notes.add_argument("--changelog", type=Path, required=True, help="Markdown or reStructuredText (.rst) changelog")
    notes.add_argument("--tag", required=True, help="release tag whose version section to print")
    notes.add_argument("--package", help="heading of the package section in a shared changelog")
    notes.set_defaults(handler=_print)


def _print(args: argparse.Namespace) -> None:
    changelog = args.changelog.read_text(encoding="utf-8")
    sys.stdout.write(release_section(changelog, args.tag, args.package, rst=args.changelog.suffix == ".rst"))


__all__ = [
    "register",
]
