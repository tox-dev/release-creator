"""Preview unreleased Knope changesets in a Markdown changelog."""

lazy import tomllib
lazy from pathlib import Path

lazy import yaml

lazy from release_creator.anchors.names import draft_anchor
lazy from release_creator.fragments.knope import changeset_parts, knope_kinds
lazy from release_creator.fragments.names import pending_changesets


def render_knope_preview(changelog: Path, config: Path, fragments: Path) -> str:
    """Add a Draft section from current changesets to a Markdown changelog.

    :param changelog: Released changelog file.
    :param config: Knope configuration file.
    :param fragments: Directory of pending changesets.
    :returns: The unchanged history with a pending Draft section when changesets exist.
    """
    history = changelog.read_text(encoding="utf-8")
    changesets = pending_changesets(fragments)
    if not changesets:
        return history
    package = tomllib.loads(config.read_text(encoding="utf-8"))["package"]
    sections = package.get("extra_changelog_sections", [])
    categories = {kind: section["name"] for section in sections for kind in section["types"]}
    defaults = {"major": "Breaking changes", "minor": "Added", "patch": "Fixed"}
    for kind in knope_kinds(package):
        if kind in defaults:
            categories.setdefault(kind, defaults[kind])
    items: dict[str, list[str]] = {}
    for changeset in changesets:
        for category, body in _changeset_items(changeset, categories):
            items.setdefault(category, []).append(body)
    draft = [f'<a name="{draft_anchor()}"></a>', "", "## Draft", ""]
    for name in dict.fromkeys([*defaults.values(), *(section["name"] for section in sections)]):
        if (entries := items.get(name)) is not None:
            draft.extend((
                f'<a name="{draft_anchor(category=name)}"></a>',
                "",
                f"### {name}",
                "",
                *entries,
                "",
            ))
    intro, marker, released = history.partition('<a name="release-')
    return f"{'\n\n'.join(part.rstrip() for part in (intro, '\n'.join(draft), f'{marker}{released}') if part)}\n"


def _changeset_items(changeset: Path, categories: dict[str, str]) -> list[tuple[str, str]]:
    frontmatter, heading, remainder = changeset_parts(changeset, changeset.read_text(encoding="utf-8"))
    try:
        entries = yaml.safe_load(frontmatter[4:].partition("\n---\n")[0])
    except yaml.YAMLError as error:
        msg = f"invalid changeset front matter in {changeset}"
        raise ValueError(msg) from error
    if not isinstance(entries, dict) or not entries:
        msg = f"empty changeset front matter in {changeset}"
        raise ValueError(msg)
    result: list[tuple[str, str]] = []
    for kind in entries.values():
        if not isinstance(kind, str) or kind not in categories:
            msg = f"unsupported changeset type in {changeset}: {kind}"
            raise ValueError(msg)
        body = remainder.removeprefix("\n").rstrip()
        result.append((
            categories[kind],
            f"- {heading}{''.join(f'\n  {line}' if line else '\n' for line in body.splitlines())}",
        ))
    return result


__all__ = [
    "render_knope_preview",
]
