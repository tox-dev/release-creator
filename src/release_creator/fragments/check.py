"""Validate changed changelog fragments in a pull request."""

lazy import shutil
lazy import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Git checks the PR diff without a shell.
lazy import sys
lazy import tomllib
lazy from pathlib import Path

lazy from release_creator.fragments.knope import changeset_parts, knope_kinds
lazy from release_creator.fragments.names import fragment_category


def changed_fragments(config: Path, base: str) -> int:
    """Count valid added or modified fragments relative to the PR base.

    :param config: Towncrier configuration file.
    :param base: Target branch name for the pull request diff.
    :returns: Number of changed fragments.
    :raises ValueError: The configuration or a changed fragment is invalid.
    """
    config, directory, suffix, categories = _towncrier_settings(config)
    if not base or suffix not in {".md", ".rst"}:
        msg = "news validation needs a PR base and a Markdown or reStructuredText changelog"
        raise ValueError(msg)
    count = 0
    for path in _git_paths(directory, ["--diff-filter=AM", f"origin/{base}...HEAD"]):
        if path.parent != directory:
            continue
        if path.suffix != suffix and fragment_category(path.with_suffix(suffix), categories) is not None:
            msg = f"unsupported changelog fragment extension: {path}"
            raise ValueError(msg)
        if path.suffix != suffix:
            continue
        if fragment_category(path, categories) is None:
            msg = f"unsupported changelog fragment: {path}"
            raise ValueError(msg)
        if not path.read_text(encoding="utf-8").strip():
            msg = f"empty changelog fragment: {path}"
            raise ValueError(msg)
        count += 1
    if count:
        repository_root = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Git receives argv.
            [_git_executable(), "rev-parse", "--show-toplevel"], capture_output=True, check=True, text=True
        ).stdout.strip()
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Towncrier receives argv.
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
            capture_output=True,
            check=False,
            text=True,
            cwd=repository_root,
        )
        if result.returncode:
            msg = result.stderr.strip() or result.stdout.strip()
            raise ValueError(msg)
    return count


def validate_fragment_deletions(config: Path) -> None:
    """Reject staged deletions that Towncrier could not have consumed.

    :param config: Towncrier configuration file.
    :raises ValueError: A deleted path is not a configured fragment.
    """
    _, directory, suffix, categories = _towncrier_settings(config)
    for path in _git_paths(directory, ["--cached", "--diff-filter=D", "--no-renames"]):
        if path.parent != directory or path.suffix != suffix or fragment_category(path, categories) is None:
            msg = f"unsupported release fragment: {path}"
            raise ValueError(msg)


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
    categories = knope_kinds(knope)
    directory = Path(".changeset")
    count = 0
    for path in _git_paths(directory, ["--diff-filter=AM", f"origin/{base}...HEAD"]):
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


def _towncrier_settings(config: Path) -> tuple[Path, Path, str, set[str]]:
    if config.name == "pyproject.toml" and (towncrier_config := config.with_name("towncrier.toml")).is_file():
        config = towncrier_config
    towncrier = tomllib.loads(config.read_text(encoding="utf-8")).get("tool", {}).get("towncrier")
    if towncrier is None:
        msg = f"missing [tool.towncrier] in {config}"
        raise ValueError(msg)
    categories = (
        {str(name) for name in towncrier["fragment"]}
        if "fragment" in towncrier
        else {str(item.get("directory", item["name"].lower())) for item in towncrier["type"]}
        if "type" in towncrier
        else {"feature", "bugfix", "doc", "removal", "misc"}
    )
    return (
        config,
        Path(towncrier.get("directory", "newsfragments")),
        Path(towncrier.get("filename", "NEWS.rst")).suffix,
        categories,
    )


def _git_paths(directory: Path, options: list[str]) -> list[Path]:
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Git argument list has no shell.
        [_git_executable(), "diff", "--relative", "--name-only", "-z", *options, "--", str(directory)],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        msg = result.stderr.decode("utf-8").strip() or "could not inspect changelog fragments"
        raise ValueError(msg)
    return [Path(filename) for filename in result.stdout.decode("utf-8").strip("\0").split("\0") if filename]


def _git_executable() -> str:
    if (git := shutil.which("git")) is None:
        msg = "Git is required to validate changelog fragments"
        raise FileNotFoundError(msg)
    return git


__all__ = [
    "changed_changesets",
    "changed_fragments",
    "validate_fragment_deletions",
]
