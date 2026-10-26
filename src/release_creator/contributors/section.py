"""Append a New Contributors subsection to one built Towncrier release section."""

lazy import re
lazy from pathlib import Path

lazy from release_creator.contributors.lookup import FirstContribution, first_contributions
lazy from release_creator.notes.render import markdown_section, rst_section


def add_new_contributors(changelog: Path, version: str, repository: str, package: str | None = None) -> None:
    """Credit first-time pull request authors at the end of a release section.

    :param changelog: Built Markdown or reStructuredText changelog, edited in place.
    :param version: Version whose section receives the subsection.
    :param repository: GitHub owner and repository.
    :param package: Package section of a shared Markdown changelog that holds the version.
    """
    lines = changelog.read_text(encoding="utf-8").splitlines()
    rst = changelog.suffix == ".rst"
    start, end = _rst_section(lines, version) if rst else _markdown_section(lines, version, package)
    section = "\n".join(lines[start:end])
    pattern = r":(?:pr|pull):`(\d+)`" if rst else rf"https://github\.com/{re.escape(repository)}/pull/(\d+)"
    numbers = list(dict.fromkeys(re.findall(pattern, section)))
    if not numbers or not (contributions := first_contributions(repository, numbers)):
        return
    release = f"{package}-{version}" if package is not None else version
    anchor = f"release-{release.replace('.', '-')}-new-contributors"
    block = (
        _rst_block(contributions, anchor, _rst_category_underline(lines[start:end]))
        if rst
        else _markdown_block(contributions, anchor, repository, "####" if package is not None else "###")
    )
    tail = lines[end:]
    while tail and not tail[0].strip():
        tail.pop(0)
    updated = [*lines[:end], "", *block, *(["", *tail] if tail else [])]
    changelog.write_text("\n".join(updated) + "\n", encoding="utf-8")


def _markdown_section(lines: list[str], version: str, package: str | None) -> tuple[int, int]:
    start, end = markdown_section(lines, version, package)
    while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].startswith('<a name="release-')):
        end -= 1
    return start, end


def _rst_section(lines: list[str], version: str) -> tuple[int, int]:
    start, end = rst_section(lines, version)
    while end > start + 2 and (not lines[end - 1].strip() or re.fullmatch(r"\.\. _[^:]+:", lines[end - 1])):
        end -= 1
    return start, end


def _adornment(line: str) -> str | None:
    stripped = line.strip()
    return stripped[0] if stripped[2:] and len(set(stripped)) == 1 and not stripped[0].isalnum() else None


def _rst_category_underline(lines: list[str]) -> str:
    version_underline = _adornment(lines[1])
    return next(
        (
            character
            for line in lines[2:]
            if (character := _adornment(line)) is not None and character != version_underline
        ),
        "-",
    )


def _markdown_block(contributions: list[FirstContribution], anchor: str, repository: str, heading: str) -> list[str]:
    return [
        f'<a name="{anchor}"></a>',
        "",
        f"{heading} New Contributors",
        "",
        *(
            f"- [@{entry.login}](https://github.com/{entry.login}) made their first contribution in "
            f"[#{entry.number}](https://github.com/{repository}/pull/{entry.number})"
            for entry in contributions
        ),
    ]


def _rst_block(contributions: list[FirstContribution], anchor: str, underline: str) -> list[str]:
    return [
        f".. _{anchor}:",
        "",
        "New Contributors",
        underline * len("New Contributors"),
        "",
        *(f"- :user:`{entry.login}` made their first contribution in :pr:`{entry.number}`" for entry in contributions),
    ]


__all__ = [
    "add_new_contributors",
]
