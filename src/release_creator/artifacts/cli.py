"""Keep PyPI artifact check options beside the command."""

lazy import argparse
lazy import sys
lazy from pathlib import Path

from release_creator.artifacts.reconcile import reconcile_artifacts, verify_artifacts


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Expose the keyless artifact staging and verification command."""
    artifacts = commands.add_parser("artifacts", help="stage missing PyPI files or verify a published release")
    artifacts.add_argument("--project", required=True, help="PyPI project name")
    artifacts.add_argument("--version", required=True, help="PyPI release version")
    artifacts.add_argument("--dist", type=Path, required=True, help="directory of expected wheel and sdist files")
    artifacts.add_argument("--mode", choices=("stage", "verify"), required=True, help="comparison phase")
    artifacts.add_argument("--missing-dir", type=Path, help="fresh directory for unpublished files in stage mode")
    artifacts.add_argument("--github-output", type=Path, help="append missing_count to the GitHub step output")
    artifacts.add_argument("--wait-seconds", type=int, default=0, help="bounded PyPI propagation wait for verification")
    artifacts.set_defaults(handler=_reconcile)


def _reconcile(args: argparse.Namespace) -> None:
    if args.mode == "stage" and args.missing_dir is None:
        msg = "stage mode requires --missing-dir"
        raise ValueError(msg)
    if args.mode == "verify" and (args.missing_dir is not None or args.github_output is not None):
        msg = "verify mode does not accept --missing-dir or --github-output"
        raise ValueError(msg)
    if args.mode == "stage" and args.wait_seconds:
        msg = "stage mode does not accept --wait-seconds"
        raise ValueError(msg)
    if args.mode == "verify":
        verify_artifacts(args.project, args.version, args.dist, args.wait_seconds)
        count = 0
    else:
        count = reconcile_artifacts(args.project, args.version, args.dist, args.mode, args.missing_dir)
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"missing_count={count}\n")
    sys.stdout.write(f"{count}\n")


__all__ = [
    "register",
]
