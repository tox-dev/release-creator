"""Refresh hook dependencies while preserving unrelated pre-commit YAML."""

lazy import json
lazy import operator
lazy import os
lazy from pathlib import Path
lazy from tempfile import TemporaryDirectory
lazy from typing import Final, cast

lazy from packaging.requirements import InvalidRequirement, Requirement
lazy from packaging.utils import NormalizedName, canonicalize_name
lazy from yaml import MappingNode, ScalarNode, SequenceNode, compose, safe_load
lazy from yaml.error import Mark, YAMLError
lazy from yaml.nodes import Node

lazy from release_creator.process import required_executable, run_text

type _Group = tuple[ScalarNode, SequenceNode, list[tuple[ScalarNode, Requirement]], list[ScalarNode], bool]
type _Edit = tuple[int, int, str]


def update_pins(config: Path, exclude_newer: str, python_version: str) -> None:
    """Refresh each hook's complete dependency closure under the selected cutoff.

    A missing configuration file, Git, or uv raises :exc:`FileNotFoundError`.

    :param config: Pre-commit configuration file.
    :param exclude_newer: Cutoff for eligible package releases.
    :param python_version: Python version used for dependency resolution.
    """
    source = config.read_bytes().decode("utf-8")
    newline = "\r\n" if source.count("\r\n") == source.count("\n") and "\r\n" in source else "\n"
    source = source.replace("\r\n", "\n")
    root = _config_root(source)
    edits: list[_Edit] = []
    with TemporaryDirectory() as temporary:
        version = _default_python_version(root, python_version)
        packages, missing, python_groups = _hook_packages(root, Path(temporary), config.parent, version, python_version)
        groups = _groups(source, root, set(python_groups))
        for group in groups:
            direct = group[2]
            package = packages.get(_start(group[0]))
            if direct or package is not None:
                resolved = _resolve(
                    [requirement for _, requirement in direct],
                    config,
                    exclude_newer,
                    python_groups.get(_start(group[0]), version),
                    package,
                )
                edits.extend(_group_edits(source, group, resolved))
            elif group[3]:
                edits.extend(_group_edits(source, group, []))
        for hook, package, hook_version in missing:
            resolved = _resolve([], config, exclude_newer, hook_version, package)
            if resolved:
                edits.append(_new_group_edit(source, hook, resolved))
    _reject_shared_edits(root, edits)
    for start, end, replacement in sorted(edits, key=operator.itemgetter(0), reverse=True):
        source = f"{source[:start]}{replacement}{source[end:]}"
    if edits:
        _config_root(source)
        config.write_bytes(source.replace("\n", newline).encode("utf-8"))


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


def _reject_shared_edits(root: MappingNode, edits: list[_Edit]) -> None:
    seen: set[int] = set()
    pending: list[Node] = [root]
    while pending:
        node = pending.pop()
        if id(node) in seen:
            shared = cast("MappingNode | ScalarNode | SequenceNode", node)
            if any(start <= _end(shared) and _start(shared) <= end for start, end, _ in edits):
                msg = "YAML aliases cannot be updated safely"
                raise ValueError(msg)
            continue
        seen.add(id(node))
        if isinstance(node, MappingNode):
            pending.extend(child for pair in node.value for child in pair)
        elif isinstance(node, SequenceNode):
            pending.extend(node.value)


def _default_python_version(root: MappingNode, fallback: str) -> str:
    defaults = _mapping_value(root, "default_language_version")
    override = _mapping_value(defaults, "python") if isinstance(defaults, MappingNode) else None
    return _python_version(override, fallback)


def _python_version(value: Node | None, fallback: str, system_version: str | None = None) -> str:
    if not isinstance(value, ScalarNode) or value.value == "default":
        return fallback
    if value.value == "python3":
        return system_version or fallback
    version = str(value.value).removeprefix("python")
    if version == value.value or not version.startswith("3."):
        msg = f"unsupported Python hook language_version: {value.value}"
        raise ValueError(msg)
    return version


def _groups(source: str, root: MappingNode, python_groups: set[int]) -> list[_Group]:
    groups: list[_Group] = []
    pending: list[MappingNode | SequenceNode | ScalarNode] = [root]
    seen: set[int] = set()
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
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
        line_end = source.find("\n", _start(item))
        if "# release-creator managed" in source[_start(item) : line_end if line_end >= 0 else len(source)]:
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
    return _end(node) - 1 if isinstance(node, ScalarNode) and node.style in {"|", ">"} else _end(node)


def _hook_packages(
    root: MappingNode, temporary: Path, cwd: Path, default_version: str, system_version: str
) -> tuple[dict[int, Path], list[tuple[MappingNode, Path, str]], dict[int, str]]:
    packages: dict[int, Path] = {}
    missing: list[tuple[MappingNode, Path, str]] = []
    python_groups: dict[int, str] = {}
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
            version = _python_version(_mapping_value(hook, "language_version"), default_version, system_version)
            if isinstance(dependencies := _mapping_key(hook, "additional_dependencies"), ScalarNode):
                python_groups[_start(dependencies)] = version
                if checkout is not None:
                    packages[_start(dependencies)] = checkout
            elif checkout is not None:
                missing.append((hook, checkout, version))
    return packages, missing, python_groups


def _hook_language(hook: Node, languages: dict[str, str], *, require_id: bool) -> str | None:
    if not isinstance(hook, MappingNode):
        msg = "selected hook must be a mapping with an id"
        raise TypeError(msg)
    if any(isinstance(key, ScalarNode) and key.value == "<<" for key, _ in hook.value):
        msg = "YAML merge keys in hook definitions cannot be updated safely"
        raise ValueError(msg)
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
    git = required_executable("git")
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
    uv = required_executable("uv")
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
            "--no-config",
            "--no-sources",
            "--default-index",
            "https://pypi.org/simple/",
            "--exclude-newer",
            exclude_newer,
            "--python-version",
            python_version,
        ],
        stdin=f"{editable}{root_lines}",
        cwd=config.parent,
        env={
            name: value
            for name, value in os.environ.items()
            if not name.startswith(("UV_", "PIP_"))
            and name not in {"SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"}
        },
    )
    if result.returncode:
        msg = f"cannot resolve hook dependencies: {result.stderr.strip()}"
        raise ValueError(msg)
    resolved = [
        _resolved_line(line) for line in result.stdout.splitlines() if line.strip() and not line.startswith("-e ")
    ]
    names = [canonicalize_name(requirement.name) for requirement in resolved]
    if len(names) != len(set(names)):
        msg = "hook dependency resolution selected multiple versions of one package"
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
    requirement = Requirement(line)
    if requirement.url is not None or not _exact_pin(requirement) or "*" in next(iter(requirement.specifier)).version:
        msg = f"hook dependency resolution did not return an exact index pin: {line}"
        raise ValueError(msg)
    return requirement


def _group_edits(source: str, group: _Group, resolved: list[Requirement]) -> list[_Edit]:
    key, sequence, direct, managed, flow_mapping = group
    if managed and not direct and not resolved and len(managed) == len(sequence.value):
        if flow_mapping:
            return [(_start(sequence), _end(sequence), "[]")]
        end = source.find("\n", _last_content_end(sequence.value[-1]))
        return [(_start(key), end + 1 if end >= 0 else len(source), f"{key.value}: []\n")]
    roots = {canonicalize_name(requirement.name) for _, requirement in direct}
    unpinned = {canonicalize_name(requirement.name) for _, requirement in direct if not _exact_pin(requirement)}
    transitive = [
        item
        for item in resolved
        if canonicalize_name(item.name) not in roots or canonicalize_name(item.name) in unpinned
    ]
    versions = {
        canonicalize_name(item.name): next(iter(item.specifier)).version
        for item in resolved
        if canonicalize_name(item.name) in roots
    }
    if missing := roots - versions.keys():
        msg = f"hook dependency resolution omitted direct packages: {', '.join(sorted(missing))}"
        raise ValueError(msg)
    if flow_mapping and (transitive or managed):
        return [_flow_mapping_edit(source, group, versions, transitive)]
    if sequence.flow_style and not transitive and not managed:
        return _block_edits(source, group, versions, [])
    if sequence.flow_style or (
        cast("Mark", sequence.start_mark).line == cast("Mark", sequence.end_mark).line and transitive
    ):
        return [_inline_edit(source, group, versions, transitive)]
    return _block_edits(source, group, versions, transitive)


def _flow_mapping_edit(
    source: str, group: _Group, versions: dict[NormalizedName, str], transitive: list[Requirement]
) -> _Edit:
    key, sequence, direct, _, _ = group
    values = [
        (
            _replace_scalar(
                source[_start(node) : _end(node)], requirement, versions[canonicalize_name(requirement.name)]
            ),
            False,
        )
        for node, requirement in direct
    ]
    values.extend((json.dumps(str(item)), True) for item in transitive)
    indent = " " * (cast("Mark", key.start_mark).column + 2)
    closing = " " * cast("Mark", key.start_mark).column
    lines = [
        f"{indent}{value}{',' if index < len(values) - 1 else ''}{' # release-creator managed' if managed else ''}"
        for index, (value, managed) in enumerate(values)
    ]
    return _start(sequence), _end(sequence), f"[\n{'\n'.join(lines)}\n{closing}]"


def _inline_edit(
    source: str,
    group: _Group,
    versions: dict[NormalizedName, str],
    transitive: list[Requirement],
) -> _Edit:
    key, sequence, direct, _, _ = group
    indent = " " * cast("Mark", key.start_mark).column
    existing = []
    for node, requirement in direct:
        scalar = source[_start(node) : _end(node)]
        existing.append(
            f"{indent}  - {_replace_scalar(scalar, requirement, versions[canonicalize_name(requirement.name)])}\n"
        )
    generated = [f"{indent}  - {json.dumps(str(item))} # release-creator managed\n" for item in transitive]
    line_end = source.find("\n", _end(sequence))
    if line_end < 0:
        line_end = len(source)
    suffix = source[_end(sequence) : line_end]
    replacement = f"{key.value}:{suffix if suffix.strip() else ''}\n{''.join(existing + generated)}"
    return _start(key), line_end + 1 if line_end < len(source) else line_end, replacement


def _replace_scalar(scalar: str, requirement: Requirement, version: str) -> str:
    if not _exact_pin(requirement):
        return scalar
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
        updated = _replace_scalar(scalar, requirement, versions[canonicalize_name(requirement.name)])
        if scalar != updated:
            edits.append((_start(node), _end(node), updated))
    for node in managed:
        start = source.rfind("\n", 0, _start(node)) + 1
        end = source.find("\n", _end(node))
        edits.append((start, end + 1 if end >= 0 else len(source), ""))
    if transitive:
        first = _start(sequence.value[0])
        indent = source[source.rfind("\n", 0, first) + 1 : first].partition("-")[0]
        end = source.find("\n", _last_content_end(sequence.value[-1]))
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
