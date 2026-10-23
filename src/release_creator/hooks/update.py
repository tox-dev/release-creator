"""Refresh hook dependencies while preserving unrelated pre-commit YAML."""

lazy import json
lazy import operator
lazy import shutil
lazy from pathlib import Path
lazy from tempfile import TemporaryDirectory
lazy from typing import Final, cast

lazy from packaging.requirements import InvalidRequirement, Requirement
lazy from packaging.utils import NormalizedName, canonicalize_name
lazy from yaml import MappingNode, ScalarNode, SequenceNode, compose, safe_load
lazy from yaml.error import Mark, YAMLError
lazy from yaml.nodes import Node

lazy from release_creator.process import run_text

type _Group = tuple[ScalarNode, SequenceNode, list[tuple[ScalarNode, Requirement]], list[ScalarNode], bool]
type _Edit = tuple[int, int, str]


def update_pins(config: Path, exclude_newer: str, python_version: str) -> None:
    """Refresh each hook's complete dependency closure under the selected cutoff."""
    source = config.read_text(encoding="utf-8")
    root = _config_root(source)
    edits: list[_Edit] = []
    with TemporaryDirectory() as temporary:
        packages, missing, python_groups = _hook_packages(root, Path(temporary), config.parent)
        groups = _groups(source, root, python_groups)
        for group in groups:
            direct = group[2]
            package = packages.get(_start(group[0]))
            if direct or package is not None:
                resolved = _resolve(
                    [requirement for _, requirement in direct], config, exclude_newer, python_version, package
                )
                edits.extend(_group_edits(source, group, resolved))
            elif group[3]:
                edits.extend(_group_edits(source, group, []))
        for hook, package in missing:
            resolved = _resolve([], config, exclude_newer, python_version, package)
            if resolved:
                edits.append(_new_group_edit(source, hook, resolved))
    for start, end, replacement in sorted(edits, key=operator.itemgetter(0), reverse=True):
        source = f"{source[:start]}{replacement}{source[end:]}"
    if edits:
        config.write_text(source, encoding="utf-8")


def _config_root(source: str) -> MappingNode:
    try:
        root = compose(source)
    except YAMLError as error:
        msg = f"invalid pre-commit YAML: {error}"
        raise ValueError(msg) from error
    if not isinstance(root, MappingNode):
        msg = "pre-commit configuration must be a YAML mapping"
        raise TypeError(msg)
    return root


def _groups(source: str, root: MappingNode, python_groups: set[int]) -> list[_Group]:
    groups: list[_Group] = []
    pending: list[MappingNode | SequenceNode | ScalarNode] = [root]
    while pending:
        node = pending.pop()
        if isinstance(node, MappingNode):
            for key, value in node.value:
                if (
                    isinstance(key, ScalarNode)
                    and key.value == "additional_dependencies"
                    and (_start(key) in python_groups or _mapping_value(root, "repos") is None)
                ):
                    groups.append(_parse_group(source, key, value, flow_mapping=node.flow_style is True))
                else:
                    pending.append(value)
        elif isinstance(node, SequenceNode):
            pending.extend(node.value)
    return groups


def _parse_group(
    source: str, key: ScalarNode, value: MappingNode | SequenceNode | ScalarNode, *, flow_mapping: bool
) -> _Group:
    if not isinstance(value, SequenceNode) or not all(isinstance(item, ScalarNode) for item in value.value):
        msg = "additional_dependencies must be a list of package strings"
        raise TypeError(msg)
    direct: list[tuple[ScalarNode, Requirement]] = []
    managed: list[ScalarNode] = []
    for item in value.value:
        line_end = source.find("\n", _end(item))
        if "# release-creator managed" in source[_end(item) : line_end if line_end >= 0 else len(source)]:
            managed.append(item)
            continue
        try:
            requirement = Requirement(item.value)
        except InvalidRequirement as error:
            msg = f"invalid hook dependency {item.value!r}"
            raise ValueError(msg) from error
        if requirement.url is not None:
            msg = f"direct URL hook dependency bypasses the package cooldown: {item.value!r}"
            raise ValueError(msg)
        direct.append((item, requirement))
    return key, value, direct, managed, flow_mapping


def _end(node: MappingNode | ScalarNode | SequenceNode) -> int:
    return int(cast("Mark", node.end_mark).index)


def _last_content_end(node: MappingNode | ScalarNode | SequenceNode) -> int:
    if isinstance(node, MappingNode) and not node.flow_style:
        return _last_content_end(node.value[-1][1])
    if isinstance(node, SequenceNode) and not node.flow_style:
        return _last_content_end(node.value[-1])
    return _end(node)


def _hook_packages(
    root: MappingNode, temporary: Path, cwd: Path
) -> tuple[dict[int, Path], list[tuple[MappingNode, Path]], set[int]]:
    packages: dict[int, Path] = {}
    missing: list[tuple[MappingNode, Path]] = []
    python_groups: set[int] = set()
    repositories = _mapping_value(root, "repos")
    if not isinstance(repositories, SequenceNode):
        return packages, missing, python_groups
    for index, repository in enumerate(repositories.value):
        if not isinstance(repository, MappingNode):
            msg = "hook repository must be a mapping"
            raise TypeError(msg)
        hooks = _mapping_value(repository, "hooks")
        if not isinstance(hooks, SequenceNode):
            msg = "hook repository must include hooks"
            raise TypeError(msg)
        checkout_and_hooks = _repository_checkout(repository, temporary / str(index), cwd)
        checkout = checkout_and_hooks[0] if checkout_and_hooks is not None else None
        languages = (
            {
                entry["id"]: entry["language"]
                for entry in safe_load((checkout / ".pre-commit-hooks.yaml").read_text(encoding="utf-8"))
            }
            if checkout is not None
            else {}
        )
        for hook in hooks.value:
            if _hook_language(hook, languages, require_id=checkout is not None) not in {None, "python"}:
                continue
            hook = cast("MappingNode", hook)
            if isinstance(dependencies := _mapping_key(hook, "additional_dependencies"), ScalarNode):
                python_groups.add(_start(dependencies))
                if checkout is not None:
                    packages[_start(dependencies)] = checkout
            elif checkout is not None:
                missing.append((hook, checkout))
    return packages, missing, python_groups


def _hook_language(hook: Node, languages: dict[str, str], *, require_id: bool) -> str | None:
    if not isinstance(hook, MappingNode):
        msg = "selected hook must be a mapping with an id"
        raise TypeError(msg)
    identifier = _mapping_value(hook, "id")
    if require_id and not isinstance(identifier, ScalarNode):
        msg = "selected hook must be a mapping with an id"
        raise TypeError(msg)
    override = _mapping_value(hook, "language")
    if isinstance(override, ScalarNode):
        return str(override.value)
    return languages.get(identifier.value) if isinstance(identifier, ScalarNode) else None


def _mapping_value(node: MappingNode, name: str) -> Node | None:
    return next(
        (cast("Node", value) for key, value in node.value if isinstance(key, ScalarNode) and key.value == name), None
    )


def _repository_checkout(repository: MappingNode, checkout: Path, cwd: Path) -> tuple[Path, SequenceNode] | None:
    url = _mapping_value(repository, "repo")
    hooks = _mapping_value(repository, "hooks")
    if not isinstance(url, ScalarNode) or url.value in {"local", "meta"} or not isinstance(hooks, SequenceNode):
        return None
    revision = _mapping_value(repository, "rev")
    if not isinstance(revision, ScalarNode):
        msg = f"missing frozen revision for hook repository {url.value}"
        raise TypeError(msg)
    git_sha1_hex_length: Final = 40
    if len(revision.value) != git_sha1_hex_length or any(
        character not in "0123456789abcdef" for character in revision.value
    ):
        msg = f"hook repository {url.value} must use a frozen commit"
        raise ValueError(msg)
    _checkout_hook_repository(url.value, revision.value, checkout, cwd)
    return checkout, hooks


def _checkout_hook_repository(url: str, revision: str, checkout: Path, cwd: Path) -> None:
    if (git := shutil.which("git")) is None:
        msg = "git is required to resolve hook repository dependencies"
        raise FileNotFoundError(msg)
    for command in (
        [git, "clone", "--quiet", "--filter=blob:none", "--no-checkout", "--", url, str(checkout)],
        [git, "-C", str(checkout), "checkout", "--quiet", revision],
    ):
        result = run_text(command, cwd=cwd)
        if result.returncode:
            msg = f"cannot read hook repository {url}@{revision}: {result.stderr.strip()}"
            raise ValueError(msg)


def _mapping_key(node: MappingNode, name: str) -> ScalarNode | None:
    return next((key for key, _ in node.value if isinstance(key, ScalarNode) and key.value == name), None)


def _start(node: MappingNode | ScalarNode | SequenceNode) -> int:
    return int(cast("Mark", node.start_mark).index)


def _resolve(
    roots: list[Requirement], config: Path, exclude_newer: str, python_version: str, package: Path | None = None
) -> list[Requirement]:
    if (uv := shutil.which("uv")) is None:
        msg = "uv is required to refresh hook dependency pins"
        raise FileNotFoundError(msg)
    editable = f"-e {package.as_uri()}\n" if package is not None else ""
    root_lines = "".join(f"{_root_input(root)}\n" for root in roots)
    result = run_text(
        [
            uv,
            "pip",
            "compile",
            "-",
            "--universal",
            "--quiet",
            "--no-header",
            "--no-annotate",
            "--exclude-newer",
            exclude_newer,
            "--python-version",
            python_version,
        ],
        stdin=f"{editable}{root_lines}",
        cwd=config.parent,
    )
    if result.returncode:
        msg = f"cannot resolve hook dependencies: {result.stderr.strip()}"
        raise ValueError(msg)
    resolved = [
        _resolved_line(line) for line in result.stdout.splitlines() if line.strip() and not line.startswith("-e ")
    ]
    root_names = {canonicalize_name(root.name) for root in roots}
    for name in root_names:
        if len([item for item in resolved if canonicalize_name(item.name) == name]) != 1:
            msg = f"uv returned different hook dependencies: {result.stdout.strip()}"
            raise ValueError(msg)
    if len({(canonicalize_name(item.name), str(item.marker)) for item in resolved}) != len(resolved):
        msg = f"uv returned duplicate hook dependencies: {result.stdout.strip()}"
        raise ValueError(msg)
    return resolved


def _root_input(requirement: Requirement) -> str:
    extras = f"[{','.join(sorted(requirement.extras))}]" if requirement.extras else ""
    marker = f"; {requirement.marker}" if requirement.marker else ""
    specifier = "" if _exact_pin(requirement) else str(requirement.specifier)
    return f"{requirement.name}{extras}{specifier}{marker}"


def _exact_pin(requirement: Requirement) -> bool:
    return len(requirement.specifier) == 1 and next(iter(requirement.specifier)).operator == "=="


def _resolved_line(line: str) -> Requirement:
    try:
        requirement = Requirement(line)
    except InvalidRequirement as error:
        msg = f"invalid package from uv: {error}"
        raise ValueError(msg) from error
    if len(requirement.specifier) != 1 or next(iter(requirement.specifier)).operator != "==":
        msg = f"expected an exact pin from uv: {line}"
        raise ValueError(msg)
    return requirement


def _group_edits(source: str, group: _Group, resolved: list[Requirement]) -> list[_Edit]:
    key, sequence, direct, managed, flow_mapping = group
    if managed and not direct and not resolved and len(managed) == len(sequence.value):
        end = source.find("\n", _end(sequence.value[-1]))
        return [(_start(key), end + 1 if end >= 0 else len(source), f"{key.value}: []\n")]
    roots = {canonicalize_name(requirement.name) for _, requirement in direct}
    transitive = [item for item in resolved if canonicalize_name(item.name) not in roots]
    versions = {
        canonicalize_name(item.name): next(iter(item.specifier)).version
        for item in resolved
        if canonicalize_name(item.name) in roots
    }
    if flow_mapping and transitive:
        values = [
            _replace_scalar(node.value, requirement, versions[canonicalize_name(requirement.name)])
            if _exact_pin(requirement)
            else node.value
            for node, requirement in direct
        ]
        values.extend(str(item) for item in transitive)
        return [(_start(sequence), _end(sequence), json.dumps(values))]
    if cast("Mark", sequence.start_mark).line == cast("Mark", sequence.end_mark).line and transitive:
        return [_inline_edit(source, group, versions, transitive)]
    return _block_edits(source, group, versions, transitive)


def _inline_edit(
    source: str,
    group: _Group,
    versions: dict[NormalizedName, str],
    transitive: list[Requirement],
) -> _Edit:
    key, sequence, direct, _, _ = group
    indent = " " * cast("Mark", key.start_mark).column
    existing = []
    for item in sequence.value:
        item = cast("ScalarNode", item)
        scalar = source[_start(item) : _end(item)]
        match = next(((node, requirement) for node, requirement in direct if node is item), None)
        if match and _exact_pin(match[1]):
            scalar = _replace_scalar(scalar, match[1], versions[canonicalize_name(match[1].name)])
        existing.append(f"{indent}  - {scalar}\n")
    generated = [f"{indent}  - {json.dumps(str(item))} # release-creator managed\n" for item in transitive]
    line_end = source.find("\n", _end(sequence))
    if line_end < 0:
        line_end = len(source)
    suffix = source[_end(sequence) : line_end]
    replacement = f"{key.value}:{suffix if suffix.strip() else ''}\n{''.join(existing + generated)}"
    return _start(key), line_end + 1 if line_end < len(source) else line_end, replacement


def _replace_scalar(scalar: str, requirement: Requirement, version: str) -> str:
    old_version = next(iter(requirement.specifier)).version
    if old_version == version:
        return scalar
    before, _, after = scalar.partition("==")
    spacing = after[: len(after) - len(after.lstrip())]
    return f"{before}=={spacing}{version}{after[len(spacing) + len(old_version) :]}"


def _block_edits(
    source: str,
    group: _Group,
    versions: dict[NormalizedName, str],
    transitive: list[Requirement],
) -> list[_Edit]:
    _, sequence, direct, managed, _ = group
    edits: list[_Edit] = []
    for node, requirement in direct:
        scalar = source[_start(node) : _end(node)]
        updated = (
            _replace_scalar(scalar, requirement, versions[canonicalize_name(requirement.name)])
            if _exact_pin(requirement)
            else scalar
        )
        if scalar != updated:
            edits.append((_start(node), _end(node), updated))
    for node in managed:
        start = source.rfind("\n", 0, _start(node)) + 1
        end = source.find("\n", _end(node))
        edits.append((start, end + 1 if end >= 0 else len(source), ""))
    if transitive:
        indent = " " * (cast("Mark", sequence.value[0].start_mark).column - 2)
        end = source.find("\n", _end(sequence.value[-1]))
        insertion = end + 1 if end >= 0 else len(source)
        prefix = "\n" if end < 0 and not source.endswith("\n") else ""
        lines = (f"{indent}- {json.dumps(str(item))} # release-creator managed\n" for item in transitive)
        generated = f"{prefix}{''.join(lines)}"
        edits.append((insertion, insertion, generated))
    return edits


def _new_group_edit(source: str, hook: MappingNode, resolved: list[Requirement]) -> _Edit:
    if source[_start(hook)] == "{":
        msg = "cannot add managed dependencies to a flow-style hook"
        raise ValueError(msg)
    end = source.find("\n", _last_content_end(hook.value[-1][1]))
    position = end + 1 if end >= 0 else len(source)
    indent = " " * cast("Mark", hook.value[0][0].start_mark).column
    generated = "".join(f"{indent}  - {json.dumps(str(item))} # release-creator managed\n" for item in resolved)
    prefix = "\n" if end < 0 else ""
    return position, position, f"{prefix}{indent}additional_dependencies:\n{generated}"


__all__ = [
    "update_pins",
]
