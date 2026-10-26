"""Keep Marketplace comparison options beside the command."""

lazy import argparse
lazy import sys
lazy from pathlib import Path

lazy from release_creator.explain import explain
lazy from release_creator.marketplace.compare import reconcile_marketplace


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Expose a read-only check for an existing plugin version."""
    marketplace = commands.add_parser("marketplace", help="compare a signed ZIP with JetBrains Marketplace")
    marketplace.add_argument("--plugin-id", required=True, help="JetBrains plugin XML ID")
    marketplace.add_argument("--version", required=True, help="plugin version without a tag prefix")
    marketplace.add_argument("--archive", required=True, type=Path, help="signed local plugin ZIP")
    marketplace.add_argument("--mode", choices=("stage", "verify"), default="stage", help="comparison phase")
    marketplace.add_argument(
        "--github-output", type=Path, help="append publish=true or false to the GitHub step output"
    )
    marketplace.set_defaults(handler=_reconcile)


def _reconcile(args: argparse.Namespace) -> None:
    publish = reconcile_marketplace(args.plugin_id, args.version, args.archive, args.mode)
    result = f"publish={str(publish).lower()}\n"
    if args.github_output is None:
        explain("GitHub step output: not written (no --github-output)")
    else:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(result)
        explain(f"GitHub step output: appended {result.strip()} to {args.github_output.as_posix()}")
    sys.stdout.write(result)


__all__ = [
    "register",
]
