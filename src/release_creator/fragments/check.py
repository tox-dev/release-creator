"""Validate changed changelog fragments in a pull request."""

lazy import sys
lazy import tomllib
lazy from fnmatch import fnmatch
lazy from pathlib import Path
lazy from typing import Any

lazy import yaml

lazy from release_creator.explain import counted, explain
lazy from release_creator.fragments.knope import changeset_parts, knope_kinds, load_knope_package
lazy from release_creator.fragments.links import (
    has_hand_written_credit,
    has_hand_written_pull_request_link,
    has_unclosed_code_fence,
)
lazy from release_creator.fragments.names import fragment_category
lazy from release_creator.fragments.shape import validate_towncrier_fragment
lazy from release_creator.notes.rst import TILDE_PLACEHOLDER, rst_errors
lazy from release_creator.process import run_text


def changed_fragments(config: Path, base: str) -> int:
    """Count valid added or modified fragments relative to the PR base.

    :param config: Towncrier configuration file.
    :param base: Target branch name for the pull request diff.
    :returns: Number of changed fragments.
    :raises ValueError: The configuration or a changed fragment is invalid.
    """
    config, directory, suffix, categories, ignored = _towncrier_settings(config, base)
    count = 0
    for path in _git_paths(directory, base):
        count += _validate_changed_fragment(path, directory, suffix, categories, ignored)
    if not count:
        explain("Towncrier check skipped: no changed fragments")
    else:
        root = run_text(["git", "rev-parse", "--show-toplevel"])
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
        sys.stderr.write(f"{result.stdout}{result.stderr}")
        explain(f"Towncrier check passed against origin/{base}")
    return count


def _validate_changed_fragment(
    path: Path, directory: Path, suffix: str, categories: set[str], ignored: set[str]
) -> int:
    if path.parent != directory:
        explain(f"Skipped {path.as_posix()} (not directly in {directory.as_posix()})")
        return 0
    if any(fnmatch(path.name.lower(), pattern) for pattern in ignored):
        explain(f"Skipped {path.as_posix()} (ignored name)")
        return 0
    if path.suffix != suffix:
        kind = " extension" if set(path.name.split(".")[1:]) & categories else ""
        msg = f"unsupported changelog fragment{kind}: {path}"
        raise ValueError(msg)
    if fragment_category(path, categories) is None:
        msg = f"unsupported changelog fragment: {path}"
        raise ValueError(msg)
    if not (content := path.read_text(encoding="utf-8")).strip():
        msg = f"empty changelog fragment: {path}"
        raise ValueError(msg)
    if suffix == ".rst" and (errors := rst_errors(content)):
        msg = f"invalid reStructuredText in changelog fragment ({errors[0]}): {path}"
        raise ValueError(msg)
    validate_towncrier_fragment(content, path)
    _reject_release_breaking_text(content, suffix, path)
    _reject_hand_written_attribution(content, suffix, path)
    explain(f"Valid fragment: {path.as_posix()}")
    return 1


def _reject_release_breaking_text(content: str, suffix: str, path: Path) -> None:
    if TILDE_PLACEHOLDER in content:
        msg = f"private-use character U+E000 in changelog fragment; release notes reserve it for escaping: {path}"
        raise ValueError(msg)
    if suffix == ".md" and has_unclosed_code_fence(content):
        msg = f"unclosed Markdown code fence in changelog fragment: {path}"
        raise ValueError(msg)


def _reject_hand_written_attribution(content: str, suffix: str, path: Path) -> None:
    if has_hand_written_credit(content, suffix):
        msg = f"hand-written author credit in changelog fragment; the fragments linker adds it: {path}"
        raise ValueError(msg)
    if has_hand_written_pull_request_link(content, suffix):
        msg = f"hand-written pull request link in changelog fragment; the fragments linker adds it: {path}"
        raise ValueError(msg)


def changed_changesets(config: Path, base: str) -> int:
    """Count and validate changed Knope changesets.

    :param config: Knope configuration file.
    :param base: Target branch name for the pull request diff.
    :returns: Number of added or modified changesets.
    :raises ValueError: The configuration or a changed changeset is invalid.
    """
    knope = load_knope_package(config)
    categories = knope_kinds(knope)
    directory = Path(".changeset")
    count = 0
    for path in _git_paths(directory, base):
        if path.parent != directory or path.suffix != ".md" or path.name == "README.md":
            explain(f"Skipped {path.as_posix()} (not a changeset)")
            continue
        content = path.read_text(encoding="utf-8")
        frontmatter, _, _ = changeset_parts(path, content)
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
        body = content.removeprefix(frontmatter)
        _reject_release_breaking_text(body, ".md", path)
        _reject_hand_written_attribution(body, ".md", path)
        explain(f"Valid changeset: {path.as_posix()}")
        count += 1
    return count


def _towncrier_settings(config: Path, base: str) -> tuple[Path, Path, str, set[str], set[str]]:
    if config.name == "pyproject.toml" and (towncrier_config := config.with_name("towncrier.toml")).is_file():
        explain(f"Towncrier config: {towncrier_config.as_posix()} (found next to {config.as_posix()})")
        config = towncrier_config
    else:
        explain(f"Towncrier config: {config.as_posix()}")
    towncrier = _towncrier_table(config.read_text(encoding="utf-8"))
    if _towncrier_changed(config, towncrier, base):
        explain(f"Towncrier layout checked: the config differs from origin/{base}")
        _reject_unsupported_towncrier_layout(config, towncrier)
    else:
        explain(f"Towncrier layout check skipped: the config matches origin/{base}")
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


def _towncrier_table(document: str) -> dict[str, Any]:
    return tomllib.loads(document).get("tool", {}).get("towncrier")


def _towncrier_changed(config: Path, towncrier: dict[str, Any], base: str) -> bool:
    previous = run_text(["git", "show", f"origin/{base}:./{config.name}"], cwd=config.parent)
    return bool(previous.returncode) or _towncrier_table(previous.stdout) != towncrier


def _reject_unsupported_towncrier_layout(config: Path, towncrier: dict[str, Any]) -> None:
    if towncrier.get("section"):
        msg = f"Towncrier sections are not supported for news validation: {config}"
        raise ValueError(msg)
    if towncrier.get("package") and "directory" not in towncrier:
        msg = f"set an explicit Towncrier fragment directory for news validation: {config}"
        raise ValueError(msg)


def _git_paths(directory: Path, base: str) -> list[Path]:
    result = run_text([
        "git",
        "diff",
        "--relative",
        "--name-only",
        "-z",
        "--diff-filter=AM",
        "--no-renames",
        f"origin/{base}...HEAD",
        "--",
        str(directory),
    ])
    if result.returncode:
        msg = result.stderr.strip() or "could not inspect changelog fragments"
        raise ValueError(msg)
    paths = [Path(filename) for filename in result.stdout.strip("\0").split("\0") if filename]
    explain(f"Added or modified in {directory.as_posix()} since origin/{base}: {counted(len(paths), 'file')}")
    return paths


__all__ = [
    "changed_changesets",
    "changed_fragments",
]
