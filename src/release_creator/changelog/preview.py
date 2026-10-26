"""Show one package's released history and pending fragments."""

lazy from pathlib import Path

lazy from release_creator.anchors.names import draft_anchor
lazy from release_creator.categories import CHANGELOG_CATEGORIES
lazy from release_creator.fragments.names import fragment_category
lazy from release_creator.markdown import prose_lines


def render_preview(changelog: Path, package: str, fragments: Path) -> str:
    """Render one Markdown package changelog with pending news.

    :param changelog: Shared Markdown changelog file.
    :param package: Package whose history to display.
    :param fragments: Directory of pending package fragments.
    :returns: The package's released history and current draft entries.
    :raises ValueError: The package or a fragment has an unsupported form.
    """
    history = _package_history(changelog.read_text(encoding="utf-8").splitlines(), package)
    names = {kind: heading for kind, (heading, _) in CHANGELOG_CATEGORIES.items()}
    sections: dict[str, list[str]] = {}
    for fragment in sorted(fragments.glob("*")):
        if not fragment.is_file() or fragment.name == ".gitkeep":
            continue
        if fragment.suffix != ".md" or (category := fragment_category(fragment, names)) is None:
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


def _package_history(lines: list[str], package: str) -> str:
    headings = [(index, line) for index, line in prose_lines(lines) if line.startswith("## ")]
    matches = [index for index, line in headings if line == f"## {package}"]
    if len(matches) != 1:
        msg = f"expected one changelog section for {package}, found {len(matches)}"
        raise ValueError(msg)
    end = next((index for index, _ in headings if index > matches[0]), len(lines))
    return "\n".join(lines[matches[0] + 1 : end]).strip()


__all__ = [
    "render_preview",
]
