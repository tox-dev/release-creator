"""Keep note options beside their renderer."""

lazy import argparse
lazy import sys
lazy from pathlib import Path

lazy from release_creator.explain import counted, explain
lazy from release_creator.notes.render import ReleaseContext, render_markdown, render_rst


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Keep note options with the note command."""
    notes = commands.add_parser("notes", help="render notes from a tagged changelog")
    notes.add_argument("--changelog", type=Path, required=True, help="tagged Markdown or reStructuredText changelog")
    notes.add_argument("--tag", required=True, help="release tag to render")
    notes.add_argument("--repository", required=True, help="GitHub owner/repository")
    notes.add_argument("--package", help="package section in a shared Markdown changelog")
    notes.add_argument("--previous", help="previous tag for the comparison link")
    notes.add_argument(
        "--artifact-url", action="append", default=[], help="link to a published package or artifact; repeatable"
    )
    notes.add_argument(
        "--artifact-label",
        action="append",
        default=[],
        help="text for each --artifact-url, in the same order; default PyPI release",
    )
    notes.set_defaults(handler=_render)


def _render(args: argparse.Namespace) -> None:
    labels = args.artifact_label or ["PyPI release"] * len(args.artifact_url)
    if len(labels) != len(args.artifact_url):
        msg = f"got {len(labels)} --artifact-label for {len(args.artifact_url)} --artifact-url"
        raise ValueError(msg)
    context = ReleaseContext(
        tag=args.tag,
        repository=args.repository,
        previous=args.previous,
        artifacts=tuple(zip(labels, args.artifact_url, strict=True)),
        package=args.package,
    )
    changelog = args.changelog.read_text(encoding="utf-8")
    if rst := args.changelog.suffix == ".rst":
        explain(f"Changelog format: reStructuredText ({args.changelog.as_posix()} ends in .rst)")
    else:
        explain(f"Changelog format: Markdown ({args.changelog.as_posix()} does not end in .rst)")
    notes = (render_rst if rst else render_markdown)(changelog, context)
    lines = notes.splitlines()
    entries = counted(sum(line.startswith("- ") for line in lines), "entry", "entries")
    categories = counted(sum(line.startswith("### ") for line in lines), "category", "categories")
    source = (
        f"the {args.package} section of {args.changelog.as_posix()}"
        if args.package is not None and not rst
        else args.changelog.as_posix()
    )
    explain(f"Release notes for {args.tag}: {entries} in {categories} from {source}")
    if args.previous is None:
        explain(f"Comparison link: commits/{args.tag} (no --previous tag)")
    else:
        explain(f"Comparison link: compare/{args.previous}...{args.tag}")
    if not args.artifact_url:
        explain("Artifact link: none (no --artifact-url)")
    for label, url in context.artifacts:
        explain(f"Artifact link: {label} -> {url}")
    sys.stdout.write(notes)


__all__ = [
    "register",
]
