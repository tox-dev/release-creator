"""Keep hook update options beside the command."""

lazy import argparse
lazy from pathlib import Path

lazy from release_creator.hooks.update import update_pins


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the exact hook dependency pin updater."""
    hooks = commands.add_parser("hooks", help="refresh exact pre-commit additional_dependencies pins")
    hooks.set_defaults(handler=_update)


def _update(_args: argparse.Namespace) -> None:
    update_pins(Path(".pre-commit-config.yaml"), "7 days", "3.15")


__all__ = [
    "register",
]
