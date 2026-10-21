"""Keep tag selection options beside the command."""

import re
import sys
lazy import argparse
lazy from datetime import UTC, datetime
lazy from pathlib import Path

lazy from release_creator.fragments.names import pending_fragments
lazy from release_creator.tags.select import next_tag, parse_tag, previous_tag, require_newer_tag


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register numeric tag validation and predecessor selection."""
    tags = commands.add_parser("tags", help="calculate, validate, or compare numeric release tags")
    tags.add_argument("tag", nargs="?", help="major.minor.patch release tag, optionally prefixed with v")
    choice = tags.add_mutually_exclusive_group()
    choice.add_argument(
        "--next",
        choices=("auto", "major", "minor", "patch", "calver"),
        help="calculate a version from pending fragments",
    )
    choice.add_argument("--previous", action="store_true", help="print the preceding tag from standard input")
    choice.add_argument("--require-newer", action="store_true", help="require a tag newer than those on standard input")
    tags.add_argument("--prefix", choices=("v",), default="", help="prefix the calculated tag with v")
    tags.add_argument("--package", help="scope tags to package/ and print package-prefixed results")
    tags.add_argument(
        "--directory", type=Path, help="pending fragment directory for --next; defaults to changelog.d[/package]"
    )
    tags.set_defaults(handler=_select)


def _select(args: argparse.Namespace) -> None:
    if (
        args.package is not None
        and re.fullmatch(
            r"""
        (?P<package>[A-Za-z0-9][A-Za-z0-9_.-]*)  # One non-relative Git tag path component
        """,
            args.package,
            re.VERBOSE,
        )
        is None
    ):
        msg = f"invalid package name: {args.package}"
        raise ValueError(msg)
    if args.next is not None:
        if args.tag is not None:
            msg = "omit the tag when calculating the next version"
            raise ValueError(msg)
        directory = args.directory or (Path("changelog.d") / args.package if args.package else Path("changelog.d"))
        version = next_tag(
            args.next,
            _scoped_tags(sys.stdin.read().splitlines(), args.package),
            [path.name for path in pending_fragments(directory)],
            datetime.now(UTC).date(),
            args.prefix,
        )
        sys.stdout.write(f"{args.package}/{version}\n" if args.package else f"{version}\n")
        return
    if args.tag is None:
        msg = "provide a tag or --next"
        raise ValueError(msg)
    tag = _scoped_target(args.tag, args.package)
    parse_tag(tag)
    if not args.previous and not args.require_newer:
        return
    tags = _scoped_tags(sys.stdin.read().splitlines(), args.package)
    if args.require_newer:
        require_newer_tag(tag, tags)
    elif (previous := previous_tag(tag, tags)) is not None:
        sys.stdout.write(f"{args.package}/{previous}\n" if args.package else f"{previous}\n")


def _scoped_target(tag: str, package: str | None) -> str:
    if package is None or "/" not in tag:
        return tag
    namespace, _, version = tag.partition("/")
    if namespace != package:
        msg = f"tag {tag} does not belong to package {package}"
        raise ValueError(msg)
    return version


def _scoped_tags(tags: list[str], package: str | None) -> list[str]:
    if package is None:
        return tags
    prefix = f"{package}/"
    return [tag.removeprefix(prefix) for tag in tags if tag.startswith(prefix)]


__all__ = [
    "register",
]
