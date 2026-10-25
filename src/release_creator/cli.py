"""Keep command registration separate from release work."""

lazy import argparse
lazy from zipfile import BadZipFile

lazy from release_creator.fragments.cli import register as register_fragments
lazy from release_creator.hooks.cli import register as register_hooks
lazy from release_creator.marketplace.cli import register as register_marketplace
lazy from release_creator.notes.cli import register as register_notes
lazy from release_creator.tags.cli import register as register_tags


def main() -> None:
    """Report command input errors through argparse's exit path."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except (BadZipFile, OSError, TypeError, ValueError) as error:
        parser.error(str(error))


def build_parser() -> argparse.ArgumentParser:
    """Expose the same parser to Sphinx and the executable.

    :returns: Parser shared by the documentation and command line.
    """
    parser = argparse.ArgumentParser(description="Release preparation tools")
    commands = parser.add_subparsers(dest="command", required=True)
    register_notes(commands)
    register_fragments(commands)
    register_tags(commands)
    register_marketplace(commands)
    register_hooks(commands)
    return parser


__all__ = [
    "build_parser",
    "main",
]
