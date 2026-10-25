"""Keep lock export options beside the command."""

lazy import argparse
lazy from pathlib import Path

lazy from release_creator.locks.export import export_lock


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Expose the selectable lock export."""
    locks = commands.add_parser("locks", help="export every project group and extra to one pylock.toml")
    locks.add_argument("--check", action="store_true", help="verify that the committed lock matches the project")
    locks.add_argument("--keep-uv-lock", action="store_true", help="keep uv.lock for projects that use it separately")
    locks.set_defaults(handler=_export)


def _export(args: argparse.Namespace) -> None:
    export_lock(Path.cwd(), check=args.check, keep_uv_lock=args.keep_uv_lock)


__all__ = [
    "register",
]
