"""Keep changelog preview options beside their command."""

lazy import argparse
lazy from pathlib import Path

lazy from release_creator.changelog.knope import render_knope_preview
lazy from release_creator.explain import explain


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the read-only Markdown changelog preview command."""
    changelog = commands.add_parser("changelog", help="render released history with current draft entries")
    changelog.add_argument("--changelog", type=Path, required=True, help="tracked Markdown changelog")
    changelog.add_argument("--config", type=Path, required=True, help="knope.toml for Knope changesets")
    changelog.add_argument("--fragments", type=Path, required=True, help="Knope changeset directory")
    changelog.add_argument("--output", type=Path, required=True, help="documentation page")
    changelog.set_defaults(handler=_render)


def _render(args: argparse.Namespace) -> None:
    args.output.write_text(render_knope_preview(args.changelog, args.config, args.fragments), encoding="utf-8")
    explain(f"Wrote {args.output.as_posix()} from {args.changelog.as_posix()}")


__all__ = [
    "register",
]
