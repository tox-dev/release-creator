"""Show one package's released history and pending fragments."""

lazy from pathlib import Path

lazy from release_creator.anchors.names import draft_anchor
lazy from release_creator.categories import CHANGELOG_CATEGORIES
lazy from release_creator.fragments.names import fragment_category
lazy from release_creator.package_name import valid_package_name


def render_preview(changelog: Path, package: str, fragments: Path) -> str:
    """Render one Markdown package changelog with pending news.

    :param changelog: Shared Markdown changelog file.
    :param package: Package whose history to display.
    :param fragments: Directory of pending package fragments.
    :returns: The package's released history and current draft entries.
    :raises ValueError: The package or a fragment has an unsupported form.
    """
    if not valid_package_name(package):
        msg = f"invalid package: {package}"
        raise ValueError(msg)
    lines = changelog.read_text(encoding="utf-8").splitlines()
    headings = [index for index, line in enumerate(lines) if line == f"## {package}"]
    if len(headings) != 1:
        msg = f"expected one changelog section for {package}, found {len(headings)}"
        raise ValueError(msg)
    end = next((index for index in range(headings[0] + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    history = "\n".join(lines[headings[0] + 1 : end]).strip()
    names = {kind: heading for kind, (heading, _) in CHANGELOG_CATEGORIES.items()}
    sections: dict[str, list[str]] = {}
    for fragment in sorted(fragments.glob("*.md")):
        if (category := fragment_category(fragment, names)) is None:
            msg = f"invalid changelog fragment: {fragment}"
            raise ValueError(msg)
        content = fragment.read_text(encoding="utf-8").strip()
        if not content or "\n\n" in content or content.startswith(("- ", "# ")):
            msg = f"expected one nonempty paragraph in {fragment}"
            raise ValueError(msg)
        sections.setdefault(names[category], []).append(f"- {' '.join(line.strip() for line in content.splitlines())}")
    page = ["# Changelog", f"## {package}"]
    if sections:
        draft = [f'<a name="{draft_anchor(package)}"></a>', "", "### Draft", ""]
        for category in dict.fromkeys(names.values()):
            if (items := sections.get(category)) is not None:
                draft.extend((
                    f'<a name="{draft_anchor(package, category)}"></a>',
                    "",
                    f"#### {category}",
                    "",
                    *items,
                    "",
                ))
        page.append("\n".join(draft).strip())
    if history:
        page.append(history)
    return f"{'\n\n'.join(page)}\n"


__all__ = [
    "render_preview",
]
