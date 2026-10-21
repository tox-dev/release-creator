"""Keep command registration separate from release work."""

import argparse

lazy from release_creator.anchors.cli import register as register_anchors
lazy from release_creator.build_constraints.cli import register as register_build_constraints
lazy from release_creator.changelog.cli import register as register_changelog
lazy from release_creator.fragments.cli import register as register_fragments
lazy from release_creator.hooks.cli import register as register_hooks
lazy from release_creator.locks.cli import register as register_locks
lazy from release_creator.notes.cli import register as register_notes
lazy from release_creator.tags.cli import register as register_tags


def main() -> None:
    """Report command input errors through argparse's exit path."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except (OSError, TypeError, ValueError) as error:
        parser.error(str(error))


def build_parser() -> argparse.ArgumentParser:
    """Expose the same parser to Sphinx and the executable.

    Returns:
        Parser shared by the documentation and command line.

    """
    parser = argparse.ArgumentParser(description="Release preparation tools")
    commands = parser.add_subparsers(dest="command", required=True)
    register_notes(commands)
    register_changelog(commands)
    register_fragments(commands)
    register_anchors(commands)
    register_tags(commands)
    register_locks(commands)
    register_build_constraints(commands)
    register_hooks(commands)
    return parser


__all__ = [
    "build_parser",
    "main",
]
