"""Keep build constraint options beside the command."""

lazy import argparse
lazy from pathlib import Path

lazy from release_creator.build_constraints.render import write_build_constraints


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Expose build pins for the current Python and platform."""
    constraints = commands.add_parser("build-constraints", help="select hashed build pins from pylock.toml")
    constraints.add_argument("--lock", type=Path, default=Path("pylock.toml"), help="PEP 751 input")
    constraints.add_argument("--group", default="build", help="build dependency group in the lock")
    constraints.add_argument("--output", type=Path, required=True, help="hashed uv build constraints output")
    constraints.set_defaults(handler=_write)


def _write(args: argparse.Namespace) -> None:
    write_build_constraints(args.lock, args.output, args.group)


__all__ = [
    "register",
]
