"""Keep changelog preview options beside their command."""

lazy import argparse
lazy from pathlib import Path

lazy from release_creator.changelog.knope import render_knope_preview
lazy from release_creator.changelog.preview import render_preview


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the read-only Markdown changelog preview command."""
    changelog = commands.add_parser("changelog", help="render package history with current draft fragments")
    changelog.add_argument("--changelog", type=Path, required=True, help="shared Markdown changelog")
    changelog.add_argument("--format", choices=("package", "knope"), required=True, help="source changelog style")
    changelog.add_argument("--package", help="package section for the package format")
    changelog.add_argument("--config", type=Path, help="knope.toml for Knope changesets")
    changelog.add_argument("--fragments", type=Path, required=True, help="package fragment directory")
    changelog.add_argument("--output", type=Path, required=True, help="package documentation page")
    changelog.set_defaults(handler=_render)


def _render(args: argparse.Namespace) -> None:
    if args.output.resolve() == args.changelog.resolve():
        msg = "output must differ from the tracked changelog"
        raise ValueError(msg)
    if args.format == "package":
        if args.package is None or args.config is not None:
            msg = "package format requires --package and no --config"
            raise ValueError(msg)
    elif args.config is None or args.package is not None:
        msg = f"{args.format} format requires --config and no --package"
        raise ValueError(msg)
    if not args.fragments.is_dir():
        msg = f"fragment directory does not exist: {args.fragments}"
        raise ValueError(msg)
    if args.format == "package":
        content = render_preview(args.changelog, args.package, args.fragments)
    else:
        content = render_knope_preview(args.changelog, args.config, args.fragments)
    args.output.write_text(content, encoding="utf-8")


__all__ = [
    "register",
]
