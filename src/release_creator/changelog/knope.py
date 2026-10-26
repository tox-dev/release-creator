"""Preview unreleased Knope changesets in a Markdown changelog."""

lazy from pathlib import Path

lazy from release_creator.anchors.names import draft_anchor
lazy from release_creator.explain import counted, explain
lazy from release_creator.fragments.knope import (
    changeset_parts,
    changeset_versioning,
    knope_kinds,
    knope_sections,
    load_knope_package,
)
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
        explain(f"Draft section: none (no pending changesets in {fragments.as_posix()})")
        return history
    package = load_knope_package(config)
    sections = knope_sections(package)
    categories = {kind: name for name, kinds in sections for kind in kinds}
    defaults = {"major": "Breaking changes", "minor": "Added", "patch": "Fixed"}
    for kind in knope_kinds(package):
        if kind in defaults:
            categories.setdefault(kind, defaults[kind])
    items: dict[str, list[str]] = {}
    for changeset in changesets:
        for category, body in _changeset_items(changeset, categories):
            items.setdefault(category, []).append(body)
    draft = [f'<a name="{draft_anchor()}"></a>', "", "## Draft", ""]
    shown: list[str] = []
    for name in dict.fromkeys([*defaults.values(), *(name for name, _ in sections)]):
        if (entries := items.get(name)) is not None:
            shown.append(name)
            draft.extend((
                f'<a name="{draft_anchor(category=name)}"></a>',
                "",
                f"### {name}",
                "",
                *entries,
                "",
            ))
    explain(
        f"Draft section: {counted(len(changesets), 'changeset')} from {fragments.as_posix()} under "
        f"{counted(len(shown), 'category', 'categories')} ({', '.join(shown)})"
    )
    intro, marker, released = history.partition('<a name="release-')
    return f"{'\n\n'.join(part.rstrip() for part in (intro, '\n'.join(draft), f'{marker}{released}') if part)}\n"


def _changeset_items(changeset: Path, categories: dict[str, str]) -> list[tuple[str, str]]:
    content = changeset.read_text(encoding="utf-8")
    versioning = changeset_versioning(changeset, content)
    _, heading, remainder = changeset_parts(changeset, content)
    result: list[tuple[str, str]] = []
    for kind in versioning.values():
        if kind not in categories:
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
