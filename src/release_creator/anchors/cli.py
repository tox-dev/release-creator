"""Keep anchor options beside the anchor command."""

lazy import argparse
lazy from pathlib import Path

lazy from release_creator.anchors.markdown import add_release_anchors
lazy from release_creator.explain import counted, explain


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register changelog anchor repair."""
    anchors = commands.add_parser("anchors", help="add stable Markdown release and category anchors")
    anchors.add_argument("--changelog", type=Path, required=True, help="assembled Markdown changelog")
    anchors.set_defaults(handler=_add)


def _add(args: argparse.Namespace) -> None:
    changelog = args.changelog.read_text(encoding="utf-8")
    anchored = add_release_anchors(changelog)
    args.changelog.write_text(anchored, encoding="utf-8")
    anchors = counted(sum(line.startswith('<a name="release-') for line in anchored.splitlines()), "release anchor")
    state = "already in place" if anchored == changelog else "updated"
    explain(f"Anchors: {anchors} in {args.changelog}, {state}")


__all__ = [
    "register",
]
