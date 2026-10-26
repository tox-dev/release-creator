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
    notes.add_argument("--artifact-url", help="link to the published package or artifact")
    notes.add_argument("--artifact-label", default="PyPI release", help="text for the artifact link")
    notes.set_defaults(handler=_render)


def _render(args: argparse.Namespace) -> None:
    context = ReleaseContext(
        tag=args.tag,
        repository=args.repository,
        previous=args.previous,
        artifact_url=args.artifact_url,
        artifact_label=args.artifact_label,
        package=args.package,
    )
    changelog = args.changelog.read_text(encoding="utf-8")
    if rst := args.changelog.suffix == ".rst":
        explain(f"Changelog format: reStructuredText ({args.changelog} ends in .rst)")
    else:
        explain(f"Changelog format: Markdown ({args.changelog} does not end in .rst)")
    notes = (render_rst if rst else render_markdown)(changelog, context)
    lines = notes.splitlines()
    entries = counted(sum(line.startswith("- ") for line in lines), "entry", "entries")
    categories = counted(sum(line.startswith("### ") for line in lines), "category", "categories")
    source = (
        f"the {args.package} section of {args.changelog}"
        if args.package is not None and not rst
        else str(args.changelog)
    )
    explain(f"Release notes for {args.tag}: {entries} in {categories} from {source}")
    if args.previous is None:
        explain(f"Comparison link: commits/{args.tag} (no --previous tag)")
    else:
        explain(f"Comparison link: compare/{args.previous}...{args.tag}")
    if args.artifact_url is None:
        explain("Artifact link: none (no --artifact-url)")
    else:
        explain(f"Artifact link: {args.artifact_label} -> {args.artifact_url}")
    sys.stdout.write(notes)


__all__ = [
    "register",
]
