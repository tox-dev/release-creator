"""Preview unreleased Knope changesets in a Markdown changelog."""

lazy import tomllib
lazy from pathlib import Path

lazy import yaml

from release_creator.fragments.knope import changeset_parts
from release_creator.fragments.names import pending_changesets
from release_creator.optional import require_yaml


def render_knope_preview(changelog: Path, config: Path, fragments: Path) -> str:
    """Add a Draft section from current changesets to a Markdown changelog.

    Returns:
        The unchanged history with a pending Draft section when changesets exist.

    Raises:
        ValueError: The changelog or a changeset cannot be rendered.

    """
    require_yaml()
    history = changelog.read_text(encoding="utf-8")
    changesets = pending_changesets(fragments)
    if not changesets:
        return history
    sections = tomllib.loads(config.read_text(encoding="utf-8"))["package"]["extra_changelog_sections"]
    categories = {kind: section["name"] for section in sections for kind in section["types"]}
    items: dict[str, list[str]] = {}
    for changeset in changesets:
        frontmatter, heading, remainder = changeset_parts(changeset, changeset.read_text(encoding="utf-8"))
        try:
            entries = yaml.safe_load(frontmatter[4:].partition("\n---\n")[0])
        except yaml.YAMLError as error:
            msg = f"invalid changeset front matter in {changeset}"
            raise ValueError(msg) from error
        if not isinstance(entries, dict) or not entries:
            msg = f"empty changeset front matter in {changeset}"
            raise ValueError(msg)
        for kind in entries.values():
            if not isinstance(kind, str) or kind not in categories:
                msg = f"unsupported changeset type in {changeset}: {kind}"
                raise ValueError(msg)
            body = remainder.removeprefix("\n").rstrip()
            items.setdefault(categories[kind], []).append(
                "- " + heading + "".join(f"\n  {line}" if line else "\n" for line in body.splitlines())
            )
    draft = ['<a name="draft"></a>', "", "## Draft", ""]
    for section in sections:
        if (entries := items.get(section["name"])) is not None:
            draft.extend((
                f'<a name="draft-{section["name"].lower().replace(" ", "-")}"></a>',
                "",
                f"### {section['name']}",
                "",
                *entries,
                "",
            ))
    intro, marker, released = history.partition('<a name="release-')
    return "\n\n".join(part.rstrip() for part in (intro, "\n".join(draft), marker + released) if part) + "\n"


__all__ = [
    "render_knope_preview",
]
