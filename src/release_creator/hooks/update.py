"""Refresh exact dependency pins without changing other pre-commit YAML."""

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # uv resolves public package versions.
lazy from pathlib import Path
lazy from typing import cast

lazy from packaging.requirements import InvalidRequirement, Requirement
lazy from packaging.utils import canonicalize_name
lazy from yaml import MappingNode, ScalarNode, SequenceNode, compose
lazy from yaml.error import Mark, YAMLError


def update_pins(config: Path, exclude_newer: str, python_version: str) -> None:
    """Refresh exact hook dependency pins that have eligible updates."""
    source = config.read_text(encoding="utf-8")
    pinned = _pinned_dependencies(source)
    if pinned:
        resolved = _resolve(
            {canonicalize_name(requirement.name) for _, requirement in pinned}, config, exclude_newer, python_version
        )
        updated = _replace_pins(source, pinned, resolved)
        if source != updated:
            config.write_text(updated, encoding="utf-8")


def _pinned_dependencies(source: str) -> list[tuple[ScalarNode, Requirement]]:
    try:
        root = compose(source)
    except YAMLError as error:
        msg = f"invalid pre-commit YAML: {error}"
        raise ValueError(msg) from error
    if not isinstance(root, MappingNode):
        msg = "pre-commit configuration must be a YAML mapping"
        raise TypeError(msg)
    pinned: list[tuple[ScalarNode, Requirement]] = []
    for node in _dependency_nodes(root):
        try:
            requirement = Requirement(node.value)
        except InvalidRequirement as error:
            msg = f"invalid hook dependency {node.value!r}"
            raise ValueError(msg) from error
        if len(requirement.specifier) == 1 and next(iter(requirement.specifier)).operator == "==":
            pinned.append((node, requirement))
    return pinned


def _resolve(names: set[str], config: Path, exclude_newer: str, python_version: str) -> dict[str, str]:
    if (uv := shutil.which("uv")) is None:
        msg = "uv is required to refresh hook dependency pins"
        raise FileNotFoundError(msg)
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Fixed uv argv.
        [
            uv,
            "pip",
            "compile",
            "-",
            "--no-deps",
            "--quiet",
            "--no-header",
            "--no-annotate",
            "--exclude-newer",
            exclude_newer,
            "--python-version",
            python_version,
        ],
        input="".join(f"{name}\n" for name in sorted(names)),
        text=True,
        capture_output=True,
        check=False,
        cwd=config.parent,
    )
    if result.returncode:
        msg = f"cannot resolve hook dependencies: {result.stderr.strip()}"
        raise ValueError(msg)
    lines = [_resolved_line(line) for line in result.stdout.splitlines()]
    resolved = dict(lines)
    if len(resolved) != len(lines) or set(resolved) != names:
        msg = f"uv returned different hook dependencies: {result.stdout.strip()}"
        raise ValueError(msg)
    return resolved


def _resolved_line(line: str) -> tuple[str, str]:
    try:
        requirement = Requirement(line)
    except InvalidRequirement as error:
        msg = f"invalid package from uv: {error}"
        raise ValueError(msg) from error
    if len(requirement.specifier) != 1 or (specifier := next(iter(requirement.specifier))).operator != "==":
        msg = f"expected an exact pin from uv: {line}"
        raise ValueError(msg)
    return canonicalize_name(requirement.name), specifier.version


def _replace_pins(source: str, pinned: list[tuple[ScalarNode, Requirement]], resolved: dict[str, str]) -> str:
    for node, requirement in sorted(pinned, key=lambda item: _start(item[0]), reverse=True):
        old_version = next(iter(requirement.specifier)).version
        new_version = resolved[canonicalize_name(requirement.name)]
        if old_version == new_version:
            continue
        start = _start(node)
        end = cast("Mark", node.end_mark).index
        scalar = source[start:end]
        before, _, after = scalar.partition("==")
        spacing = after[: len(after) - len(after.lstrip())]
        updated = f"{before}=={spacing}{new_version}{after[len(spacing) + len(old_version) :]}"
        source = f"{source[:start]}{updated}{source[end:]}"
    return source


def _start(node: ScalarNode) -> int:
    return int(cast("Mark", node.start_mark).index)


def _dependency_nodes(root: MappingNode) -> list[ScalarNode]:
    result: list[ScalarNode] = []
    pending: list[MappingNode | SequenceNode | ScalarNode] = [root]
    while pending:
        node = pending.pop()
        if isinstance(node, MappingNode):
            for key, value in node.value:
                if isinstance(key, ScalarNode) and key.value == "additional_dependencies":
                    if not isinstance(value, SequenceNode) or not all(
                        isinstance(item, ScalarNode) for item in value.value
                    ):
                        msg = "additional_dependencies must be a list of package strings"
                        raise TypeError(msg)
                    result.extend(value.value)
                else:
                    pending.append(value)
        elif isinstance(node, SequenceNode):
            pending.extend(node.value)
    return result


__all__ = [
    "update_pins",
]
