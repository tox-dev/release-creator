"""Validate changed changelog fragments in a pull request."""

lazy import sys
lazy import tomllib
lazy from fnmatch import fnmatch
lazy from pathlib import Path

lazy import yaml

lazy from release_creator.fragments.knope import changeset_parts, knope_kinds, load_knope_package
lazy from release_creator.fragments.names import fragment_category
lazy from release_creator.process import required_executable, run_text


def changed_fragments(config: Path, base: str) -> int:
    """Count valid added or modified fragments relative to the PR base.

    A missing Git executable raises :exc:`FileNotFoundError`.

    :param config: Towncrier configuration file.
    :param base: Target branch name for the pull request diff.
    :returns: Number of changed fragments.
    :raises ValueError: The configuration or a changed fragment is invalid.
    """
    config, directory, suffix, categories, ignored = _towncrier_settings(config)
    if not base or suffix not in {".md", ".rst"}:
        msg = "news validation needs a PR base and a Markdown or reStructuredText changelog"
        raise ValueError(msg)
    count = 0
    for path in _git_paths(directory, ["--diff-filter=AM", "--no-renames", f"origin/{base}...HEAD"]):
        count += _validate_changed_fragment(path, directory, suffix, categories, ignored)
    if count:
        root = run_text([_git_executable(), "rev-parse", "--show-toplevel"])
        if root.returncode:
            msg = root.stderr.strip() or "could not locate repository root"
            raise ValueError(msg)
        result = run_text(
            [
                sys.executable,
                "-m",
                "towncrier",
                "check",
                "--config",
                str(config.resolve()),
                "--compare-with",
                f"origin/{base}",
            ],
            cwd=Path(root.stdout.strip()),
        )
        if result.returncode:
            msg = result.stderr.strip() or result.stdout.strip()
            raise ValueError(msg)
    return count


def _validate_changed_fragment(
    path: Path, directory: Path, suffix: str, categories: set[str], ignored: set[str]
) -> int:
    if path.parent != directory or any(fnmatch(path.name.lower(), pattern) for pattern in ignored):
        return 0
    if path.suffix != suffix:
        kind = " extension" if set(path.name.split(".")[1:]) & categories else ""
        msg = f"unsupported changelog fragment{kind}: {path}"
        raise ValueError(msg)
    if fragment_category(path, categories) is None:
        msg = f"unsupported changelog fragment: {path}"
        raise ValueError(msg)
    if not path.read_text(encoding="utf-8").strip():
        msg = f"empty changelog fragment: {path}"
        raise ValueError(msg)
    return 1


def validate_fragment_deletions(config: Path) -> None:
    """Reject staged deletions that Towncrier could not have consumed.

    A missing Git executable raises :exc:`FileNotFoundError`.

    :param config: Towncrier configuration file.
    :raises ValueError: A deleted path is not a configured fragment.
    """
    _, directory, suffix, categories, _ = _towncrier_settings(config)
    for path in _git_paths(directory, ["--cached", "--diff-filter=D", "--no-renames"]):
        if path.parent != directory or path.suffix != suffix or fragment_category(path, categories) is None:
            msg = f"unsupported release fragment: {path}"
            raise ValueError(msg)


def changed_changesets(config: Path, base: str) -> int:
    """Count and validate changed Knope changesets.

    A missing Git executable raises :exc:`FileNotFoundError`.

    :param config: Knope configuration file.
    :param base: Target branch name for the pull request diff.
    :returns: Number of added or modified changesets.
    :raises ValueError: The configuration or a changed changeset is invalid.
    """
    if not base:
        msg = "news validation needs a PR base"
        raise ValueError(msg)
    knope = load_knope_package(config)
    categories = knope_kinds(knope)
    directory = Path(".changeset")
    count = 0
    for path in _git_paths(directory, ["--diff-filter=AM", "--no-renames", f"origin/{base}...HEAD"]):
        if path.parent != directory or path.suffix != ".md" or path.name == "README.md":
            continue
        frontmatter, _, _ = changeset_parts(path, path.read_text(encoding="utf-8"))
        try:
            entries = yaml.safe_load(frontmatter[4:].partition("\n---\n")[0])
        except yaml.YAMLError as error:
            msg = f"invalid changeset front matter in {path}"
            raise ValueError(msg) from error
        if not isinstance(entries, dict) or not entries:
            msg = f"empty changeset front matter in {path}"
            raise ValueError(msg)
        for package, kind in entries.items():
            if (
                not isinstance(package, str)
                or not package.strip()
                or not isinstance(kind, str)
                or kind not in categories
            ):
                msg = f"unsupported changeset type in {path}: {package}: {kind}"
                raise ValueError(msg)
        count += 1
    return count


def _towncrier_settings(config: Path) -> tuple[Path, Path, str, set[str], set[str]]:
    if config.name == "pyproject.toml" and (towncrier_config := config.with_name("towncrier.toml")).is_file():
        config = towncrier_config
    towncrier = tomllib.loads(config.read_text(encoding="utf-8")).get("tool", {}).get("towncrier")
    if towncrier is None:
        msg = f"missing [tool.towncrier] in {config}"
        raise ValueError(msg)
    if towncrier.get("section"):
        msg = f"Towncrier sections are not supported for news validation: {config}"
        raise ValueError(msg)
    if towncrier.get("package") and "directory" not in towncrier:
        msg = f"set an explicit Towncrier fragment directory for news validation: {config}"
        raise ValueError(msg)
    categories = (
        {str(name) for name in towncrier["fragment"]}
        if "fragment" in towncrier
        else {str(item.get("directory") or str(item.get("name", "")).lower()) for item in towncrier["type"]}
        if "type" in towncrier
        else {"feature", "bugfix", "doc", "removal", "misc"}
    )
    ignored = {".gitignore", ".gitkeep", ".keep", "readme", "readme.md", "readme.rst", "*~"}
    if isinstance(template := towncrier.get("template"), str):
        ignored.add(Path(template).name.lower())
    ignored.update(str(pattern).lower() for pattern in towncrier.get("ignore", []))
    return (
        config,
        Path(towncrier.get("directory", "newsfragments")),
        Path(towncrier.get("filename", "NEWS.rst")).suffix,
        categories,
        ignored,
    )


def _git_paths(directory: Path, options: list[str]) -> list[Path]:
    result = run_text([_git_executable(), "diff", "--relative", "--name-only", "-z", *options, "--", str(directory)])
    if result.returncode:
        msg = result.stderr.strip() or "could not inspect changelog fragments"
        raise ValueError(msg)
    return [Path(filename) for filename in result.stdout.strip("\0").split("\0") if filename]


def _git_executable() -> str:
    return required_executable("git")


__all__ = [
    "changed_changesets",
    "changed_fragments",
    "validate_fragment_deletions",
]
