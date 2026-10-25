"""Check that a release patch deletes only fragments Towncrier consumed."""

lazy import argparse
lazy import tomllib
lazy from pathlib import Path

lazy from release_creator.fragments.names import fragment_category
lazy from release_creator.process import run_text


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the staged fragment deletion check."""
    deletions = commands.add_parser("validate-fragment-deletions", help="check staged Towncrier fragment deletions")
    deletions.set_defaults(handler=_check_deletions)


def _check_deletions(_: argparse.Namespace) -> None:
    config = Path("towncrier.toml") if Path("towncrier.toml").is_file() else Path("pyproject.toml")
    if (towncrier := tomllib.loads(config.read_text(encoding="utf-8")).get("tool", {}).get("towncrier")) is None:
        msg = f"missing [tool.towncrier] in {config}"
        raise ValueError(msg)
    directory = Path(towncrier.get("directory", "newsfragments"))
    suffix = Path(towncrier.get("filename", "NEWS.rst")).suffix
    categories = (
        set(towncrier["fragment"])
        if "fragment" in towncrier
        else {item.get("directory") or item["name"].lower() for item in towncrier["type"]}
        if "type" in towncrier
        else {"feature", "bugfix", "doc", "removal", "misc"}
    )
    command = ["git", "diff", "--cached", "--diff-filter=D", "--no-renames", "--relative", "--name-only", "-z"]
    if (result := run_text([*command, "--", str(directory)])).returncode:
        msg = result.stderr.strip() or "could not inspect changelog fragments"
        raise ValueError(msg)
    for path in map(Path, filter(None, result.stdout.split("\0"))):
        if path.parent != directory or path.suffix != suffix or fragment_category(path, categories) is None:
            msg = f"unsupported release fragment: {path}"
            raise ValueError(msg)


__all__ = [
    "register",
]
