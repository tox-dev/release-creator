"""Keep anchor options beside the anchor command."""

from pathlib import Path
lazy import argparse

lazy from release_creator.anchors.markdown import add_release_anchors


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register changelog anchor repair."""
    anchors = commands.add_parser("anchors", help="add stable Markdown release and category anchors")
    anchors.add_argument("--changelog", type=Path, required=True, help="assembled Markdown changelog")
    anchors.set_defaults(handler=_add)


def _add(args: argparse.Namespace) -> None:
    changelog = args.changelog.read_text(encoding="utf-8")
    args.changelog.write_text(add_release_anchors(changelog), encoding="utf-8")


__all__ = [
    "register",
]
