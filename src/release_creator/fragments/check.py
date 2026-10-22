"""Validate changed changelog fragments in a pull request."""

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Git checks the PR diff without a shell.
lazy import tomllib
lazy from pathlib import Path

from release_creator.fragments.knope import changeset_parts
from release_creator.fragments.names import fragment_category


def changed_fragments(config: Path, base: str) -> int:
    """Count valid added or modified fragments relative to the PR base.

    :param config: Towncrier configuration file.
    :param base: Target branch name for the pull request diff.
    :returns: Number of changed fragments.
    :raises ValueError: The configuration or a changed fragment is invalid.
    """
    if config.name == "pyproject.toml" and (towncrier_config := config.with_name("towncrier.toml")).is_file():
        config = towncrier_config
    towncrier = tomllib.loads(config.read_text(encoding="utf-8"))["tool"]["towncrier"]
    directory = Path(towncrier["directory"])
    suffix = Path(towncrier["filename"]).suffix
    categories = (
        set(towncrier["fragment"])
        if "fragment" in towncrier
        else {item.get("directory", item["name"].lower()) for item in towncrier["type"]}
    )
    if not base or suffix not in {".md", ".rst"}:
        msg = "news validation needs a PR base and a Markdown or reStructuredText changelog"
        raise ValueError(msg)
    count = 0
    for path in _changed_paths(directory, base):
        if path.parent != directory or path.suffix != suffix:
            continue
        if fragment_category(path, categories) is None:
            msg = f"unsupported changelog fragment: {path}"
            raise ValueError(msg)
        if not path.read_text(encoding="utf-8").strip():
            msg = f"empty changelog fragment: {path}"
            raise ValueError(msg)
        count += 1
    return count


def changed_changesets(config: Path, base: str) -> int:
    """Count and validate changed Knope changesets.

    :param config: Knope configuration file.
    :param base: Target branch name for the pull request diff.
    :returns: Number of added or modified changesets.
    :raises ValueError: The configuration or a changed changeset is invalid.
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
