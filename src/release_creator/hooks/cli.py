"""Keep hook update options beside the command."""

lazy import argparse
lazy from pathlib import Path

lazy from release_creator.hooks.update import update_pins


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the exact hook dependency pin updater."""
    hooks = commands.add_parser("hooks", help="refresh exact pre-commit additional_dependencies pins")
    hooks.add_argument("--config", type=Path, default=Path(".pre-commit-config.yaml"), help="pre-commit configuration")
    hooks.add_argument("--exclude-newer", required=True, help="UTC cutoff for eligible package releases")
    hooks.add_argument("--python-version", required=True, help="Python version used to resolve hook dependencies")
    hooks.set_defaults(handler=_update)


def _update(args: argparse.Namespace) -> None:
    update_pins(args.config, args.exclude_newer, args.python_version)


__all__ = [
    "register",
]
