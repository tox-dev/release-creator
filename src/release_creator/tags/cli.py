"""Keep tag selection options beside the command."""

lazy import argparse
lazy import sys
lazy from pathlib import Path

lazy from release_creator.explain import counted, explain
lazy from release_creator.fragments.names import pending_fragments
lazy from release_creator.tags.select import next_tag, previous_tag


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register version calculation and predecessor selection."""
    tags = commands.add_parser("tags", help="calculate or compare numeric release tags")
    tags.add_argument("tag", nargs="?", help="major.minor.patch release tag, optionally prefixed with v")
    choice = tags.add_mutually_exclusive_group()
    choice.add_argument(
        "--next",
        choices=("auto", "major", "minor", "patch"),
        help="calculate a version from pending fragments",
    )
    choice.add_argument("--previous", action="store_true", help="print the preceding tag from standard input")
    tags.add_argument("--prefix", choices=("v",), default="", help="prefix the calculated tag with v")
    tags.add_argument("--package", help="scope tags to package/ and print package-prefixed results")
    tags.add_argument(
        "--directory", type=Path, help="pending fragment directory for --next; defaults to changelog.d[/package]"
    )
    tags.set_defaults(handler=_select)


def _select(args: argparse.Namespace) -> None:
    if args.next is not None:
        if args.tag is not None:
            msg = "omit the tag when calculating the next version"
            raise ValueError(msg)
        if args.directory is not None:
            directory, source = args.directory, "from --directory"
        elif args.package:
            directory, source = Path("changelog.d") / args.package, f"default for package {args.package}"
        else:
            directory, source = Path("changelog.d"), "default"
        explain(f"Fragment directory: {directory.as_posix()} ({source})")
        version = next_tag(
            args.next,
            _scoped_tags(sys.stdin.read().splitlines(), args.package),
            [path.name for path in pending_fragments(directory)],
            args.prefix,
        )
        sys.stdout.write(f"{args.package}/{version}\n" if args.package else f"{version}\n")
        return
    if args.tag is None:
        msg = "provide a tag or --next"
        raise ValueError(msg)
    tag = _scoped_target(args.tag, args.package)
    if (previous := previous_tag(tag, _scoped_tags(sys.stdin.read().splitlines(), args.package))) is not None:
        sys.stdout.write(f"{args.package}/{previous}\n" if args.package else f"{previous}\n")


def _scoped_target(tag: str, package: str | None) -> str:
    if package is None or "/" not in tag:
        return tag
    return tag.removeprefix(f"{package}/")


def _scoped_tags(tags: list[str], package: str | None) -> list[str]:
    if package is None:
        return tags
    prefix = f"{package}/"
    scoped = [tag.removeprefix(prefix) for tag in tags if tag.startswith(prefix)]
    explain(f"Package scope: {package} ({len(scoped)} of {counted(len(tags), 'tag')} start with {prefix})")
    return scoped


__all__ = [
    "register",
]
