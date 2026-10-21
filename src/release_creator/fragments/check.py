"""Validate changed changelog fragments in a pull request."""

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Git checks the PR diff without a shell.
lazy import tomllib
lazy from pathlib import Path

from release_creator.fragments.knope import changeset_parts


def changed_fragments(config: Path, base: str) -> int:
    """Count valid added or modified fragments relative to the PR base.

    Returns:
        Number of changed fragments.

    Raises:
        ValueError: The configuration or a changed fragment is invalid.

    """
    towncrier = tomllib.loads(config.read_text(encoding="utf-8"))["tool"]["towncrier"]
    directory = Path(towncrier["directory"])
    suffix = Path(towncrier["filename"]).suffix
    categories = {item["directory"] for item in towncrier["type"]}
    if not base or suffix not in {".md", ".rst"}:
        msg = "news validation needs a PR base and a Markdown or reStructuredText changelog"
        raise ValueError(msg)
    count = 0
    for path in _changed_paths(directory, base):
        if path.parent != directory or path.suffix != suffix:
            continue
        match path.stem.rsplit(".", 2):
            case [stem, category, number] if number.isdecimal():
                pass
            case [*stem_parts, category] if stem_parts:
                stem = ".".join(stem_parts)
            case _:
                continue
        if not ((stem.startswith("+") and len(stem) > 1) or stem.isdigit()) or category not in categories:
            msg = f"unsupported changelog fragment: {path}"
            raise ValueError(msg)
        if not path.read_text(encoding="utf-8").strip():
            msg = f"empty changelog fragment: {path}"
            raise ValueError(msg)
        count += 1
    return count


def changed_changesets(config: Path, base: str) -> int:
    """Count and validate changed Knope changesets.

    Returns:
        Number of added or modified changesets.

    Raises:
        ValueError: The configuration or a changed changeset is invalid.

    """
    if not base:
        msg = "news validation needs a PR base"
        raise ValueError(msg)
    knope = tomllib.loads(config.read_text(encoding="utf-8"))["package"]
    categories = {"major", "minor", "patch"}
    categories.update(kind for section in knope.get("extra_changelog_sections", []) for kind in section["types"])
    directory = Path(".changeset")
    count = 0
    for path in _changed_paths(directory, base):
        if path.parent != directory or path.suffix != ".md" or path.name == "README.md":
            continue
        frontmatter, _, _ = changeset_parts(path, path.read_text(encoding="utf-8"))
        entries = frontmatter.removeprefix("---\n").partition("---\n")[0].splitlines()
        if not entries:
            msg = f"empty changeset front matter in {path}"
            raise ValueError(msg)
        for entry in entries:
            package, separator, kind = entry.partition(":")
            if not separator or not package.strip() or kind.strip() not in categories:
                msg = f"unsupported changeset type in {path}: {entry}"
                raise ValueError(msg)
        count += 1
    return count


def _changed_paths(directory: Path, base: str) -> list[Path]:
    if (git := shutil.which("git")) is None:
        msg = "Git is required to validate changelog fragments"
        raise FileNotFoundError(msg)
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Git argument list has no shell.
        [git, "diff", "--diff-filter=AM", "--name-only", "-z", f"origin/{base}...HEAD", "--", str(directory)],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        msg = result.stderr.decode("utf-8").strip() or f"could not compare changelog fragments with origin/{base}"
        raise ValueError(msg)
    return [Path(filename) for filename in result.stdout.decode("utf-8").strip("\0").split("\0") if filename]


__all__ = [
    "changed_changesets",
    "changed_fragments",
]
