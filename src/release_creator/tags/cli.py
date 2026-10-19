"""Keep tag selection options beside the command."""

import sys
lazy import argparse
lazy from datetime import UTC, datetime
lazy from pathlib import Path

lazy from release_creator.tags.select import next_tag, parse_tag, previous_tag, require_newer_tag


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register numeric tag validation and predecessor selection."""
    tags = commands.add_parser("tags", help="calculate, validate, or compare numeric release tags")
    tags.add_argument("tag", nargs="?", help="major.minor.patch release tag")
    choice = tags.add_mutually_exclusive_group()
    choice.add_argument(
        "--next",
        choices=("auto", "major", "minor", "patch", "calver"),
        help="calculate a version from pending fragments",
    )
    choice.add_argument("--previous", action="store_true", help="print the preceding tag from standard input")
    choice.add_argument("--require-newer", action="store_true", help="require a tag newer than those on standard input")
    tags.add_argument(
        "--directory", type=Path, default=Path("changelog.d"), help="pending fragment directory for --next"
    )
    tags.set_defaults(handler=_select)


def _select(args: argparse.Namespace) -> None:
    if args.next is not None:
        if args.tag is not None:
            msg = "omit the tag when calculating the next version"
            raise ValueError(msg)
        version = next_tag(
            args.next,
            sys.stdin.read().splitlines(),
            [path.name for extension in ("md", "rst") for path in args.directory.glob(f"*.*.{extension}")],
            datetime.now(UTC).date(),
        )
        sys.stdout.write(f"{version}\n")
        return
    if args.tag is None:
        msg = "provide a tag or --next"
        raise ValueError(msg)
    parse_tag(args.tag)
    if not args.previous and not args.require_newer:
        return
    tags = sys.stdin.read().splitlines()
    if args.require_newer:
        require_newer_tag(args.tag, tags)
    elif (previous := previous_tag(args.tag, tags)) is not None:
        sys.stdout.write(f"{previous}\n")


__all__ = [
    "register",
]
