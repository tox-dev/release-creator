"""Show one package's released history and pending fragments."""

lazy from pathlib import Path

from release_creator.categories import CHANGELOG_CATEGORIES


def render_preview(changelog: Path, package: str, fragments: Path) -> str:
    """Render one Markdown package changelog with pending news.

    :param changelog: Shared Markdown changelog file.
    :param package: Package whose history to display.
    :param fragments: Directory of pending package fragments.
    :returns: The package's released history and current draft entries.
    :raises ValueError: The package or a fragment has an unsupported form.
    """
    if (
        not package
        or not package[0].isascii()
        or not package[0].isalnum()
        or not all(character.isascii() and (character.isalnum() or character in "_.-") for character in package)
    ):
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
        stem, separator, category = fragment.stem.rpartition(".")
        if (
            not separator
            or not stem
            or category not in names
            or not (stem.isdecimal() or (stem.startswith("+") and stem[1:].replace("-", "").isalnum()))
        ):
            msg = f"invalid changelog fragment: {fragment}"
            raise ValueError(msg)
        content = fragment.read_text(encoding="utf-8").strip()
        if not content or "\n\n" in content or content.startswith(("- ", "# ")):
            msg = f"expected one nonempty paragraph in {fragment}"
            raise ValueError(msg)
        sections.setdefault(names[category], []).append(f"- {' '.join(line.strip() for line in content.splitlines())}")
    page = ["# Changelog", f"## {package}"]
    if sections:
        draft = [f'<a name="draft-{package}"></a>', "", "### Draft", ""]
        for category in dict.fromkeys(names.values()):
            if (items := sections.get(category)) is not None:
                draft.extend((
                    f'<a name="draft-{package}-{category.lower().replace(" ", "-")}"></a>',
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
