"""Keep note options beside their renderer."""

lazy import argparse
lazy import sys
lazy from pathlib import Path

lazy from release_creator.notes.render import ReleaseContext, render_markdown, render_rst


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Keep note options with the note command."""
    notes = commands.add_parser("notes", help="render notes from a tagged changelog")
    notes.add_argument("--changelog", type=Path, required=True, help="tagged Markdown or reStructuredText changelog")
    notes.add_argument("--tag", required=True, help="release tag to render")
    notes.add_argument("--repository", required=True, help="GitHub owner/repository")
    notes.add_argument("--package", help="package section in a shared Markdown changelog")
    notes.add_argument("--previous", help="previous tag for the comparison link")
    notes.add_argument("--artifact-url", help="HTTPS link to the published package or artifact")
    notes.add_argument("--artifact-label", default="PyPI release", help="text for the artifact link")
    notes.add_argument("--generated-notes", type=Path, help="GitHub generated notes for New Contributors credits")
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
    generated = args.generated_notes.read_text(encoding="utf-8") if args.generated_notes is not None else None
    if args.changelog.suffix == ".rst":
        sys.stdout.write(render_rst(changelog, context, generated_notes=generated))
    else:
        sys.stdout.write(render_markdown(changelog, context, generated_notes=generated))


__all__ = [
    "register",
]
