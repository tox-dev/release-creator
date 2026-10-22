"""Keep PyPI artifact check options beside the command."""

lazy import argparse
lazy import sys
lazy from pathlib import Path

from release_creator.artifacts.reconcile import verify_artifacts


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Expose the published artifact verification command."""
    artifacts = commands.add_parser("artifacts", help="verify every built file against its published PyPI release")
    artifacts.add_argument("--project", required=True, help="PyPI project name")
    artifacts.add_argument("--version", required=True, help="PyPI release version")
    artifacts.add_argument("--dist", type=Path, required=True, help="directory of expected wheel and sdist files")
    artifacts.add_argument("--wait-seconds", type=int, default=0, help="bounded PyPI propagation wait for verification")
    artifacts.set_defaults(handler=_verify)


def _verify(args: argparse.Namespace) -> None:
    for url in verify_artifacts(args.project, args.version, args.dist, args.wait_seconds):
        sys.stdout.write(f"{url}\n")


__all__ = [
    "register",
]
