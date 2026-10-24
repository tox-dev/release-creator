"""Keep hook update options beside the command."""

lazy import argparse
lazy from pathlib import Path
lazy from typing import Final

lazy from release_creator.hooks.update import check_pins, update_pins

_MINIMUM_DAYS: Final = 7


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the exact hook dependency pin updater."""
    hooks = commands.add_parser("hooks", help="refresh exact pre-commit additional_dependencies pins")
    hooks.add_argument("--check", action="store_true", help="verify the proposed dependency closure without changes")
    hooks.add_argument(
        "--minimum-days", type=int, default=_MINIMUM_DAYS, help="minimum package age in days (at least seven)"
    )
    hooks.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> None:
    if args.minimum_days < _MINIMUM_DAYS:
        msg = "minimum hook dependency age must be at least seven days"
        raise ValueError(msg)
    (check_pins if args.check else update_pins)(Path(".pre-commit-config.yaml"), f"{args.minimum_days} days", "3.15")


__all__ = [
    "register",
]
