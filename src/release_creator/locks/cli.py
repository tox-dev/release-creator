"""Keep lock export options beside the command."""

lazy import argparse
lazy from pathlib import Path

lazy from release_creator.locks.export import export_lock


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Expose the selectable lock export."""
    locks = commands.add_parser("locks", help="export every project group and extra to one pylock.toml")
    locks.add_argument("--project", type=Path, default=Path("pyproject.toml"), help="project input")
    locks.add_argument("--output", type=Path, default=Path("pylock.toml"), help="PEP 751 output")
    locks.add_argument("--tool-python", help="Python range for a tool-only pyproject.toml")
    locks.add_argument(
        "--build-requirement",
        action="append",
        default=[],
        help="dynamic build dependency missing from [build-system].requires; repeat as needed",
    )
    locks.add_argument(
        "--exclude-newer-package",
        action="append",
        default=[],
        help="package-specific cutoff override as NAME=DATE; repeat as needed",
    )
    locks.set_defaults(handler=_export)


def _export(args: argparse.Namespace) -> None:
    export_lock(
        args.project,
        args.output,
        args.tool_python,
        tuple(args.build_requirement),
        tuple(args.exclude_newer_package),
    )


__all__ = [
    "register",
]
