"""Pin each Python hook's complete dependency closure while preserving unrelated pre-commit YAML."""

lazy import json
lazy import operator
lazy import re
lazy from pathlib import Path
lazy from tempfile import TemporaryDirectory
lazy from typing import cast

lazy from packaging.requirements import InvalidRequirement, Requirement
lazy from packaging.utils import NormalizedName, canonicalize_name
lazy from yaml import MappingNode, ScalarNode, SequenceNode, compose, safe_load
lazy from yaml.error import Mark, YAMLError
lazy from yaml.nodes import Node

lazy from release_creator.process import isolated_uv_env, run_text

type _PinKey = tuple[NormalizedName, str]
type _Edit = tuple[int, int, str]
type _Hook = tuple[MappingNode, tuple[ScalarNode, Node] | None, Path | None, list[str], list[Requirement]]
"""Hook mapping, ``additional_dependencies`` key and value, checkout, uv compile command, and manifest defaults."""


def update_pins(config: Path, exclude_newer: str, python_version: str) -> None:
    """Refresh each Python hook's dependency closure under the selected cutoff.

    :param config: Pre-commit configuration file.
    :param exclude_newer: Cutoff for eligible package releases.
    :param python_version: Python version for hooks that do not select one.
    """
    source = config.read_text(encoding="utf-8", newline="")
    edits: list[_Edit] = []
    with TemporaryDirectory() as temporary:
        for hook, dependencies, checkout, compiler, defaults in _python_hooks(
            source, Path(temporary), config.parent, exclude_newer, python_version
        ):
            if dependencies is None:
                if checkout is not None and (resolved := _resolve(compiler, defaults, config.parent, checkout)):
                    edits.append(_new_list(source, hook, defaults, resolved))
                continue
            key, value = dependencies
            direct, managed = _dependencies(source, value)
            if (roots := [requirement for _, requirement in direct]) or checkout is not None:
                edits.extend(_list_edits(source, key, value, _resolve(compiler, roots, config.parent, checkout)))
            elif managed:
                edits.extend(_list_edits(source, key, value, []))
    for start, end, replacement in sorted(edits, key=operator.itemgetter(0), reverse=True):
        source = f"{source[:start]}{replacement}{source[end:]}"
    if edits:
        _config_root(source)
        config.write_text(source, encoding="utf-8", newline="")


def check_pins(config: Path, exclude_newer: str, python_version: str) -> None:
    """Check that each Python hook pins exactly its resolved dependency closure.

    :param config: Proposed pre-commit configuration file.
    :param exclude_newer: Cutoff for eligible package releases.
    :param python_version: Python version for hooks that do not select one.
    :raises ValueError: The proposed pins differ from the resolved dependency closure.
    """
    source = config.read_text(encoding="utf-8", newline="")
    with TemporaryDirectory() as temporary:
        for hook, dependencies, checkout, compiler, defaults in _python_hooks(
            source, Path(temporary), config.parent, exclude_newer, python_version
        ):
            hook_id = cast("ScalarNode", _value(hook, "id")).value
            if dependencies is None:
                if checkout is not None and _resolve(compiler, defaults, config.parent, checkout, constraints=[]):
                    msg = f"hook is missing managed dependencies: {hook_id}"
                    raise ValueError(msg)
                continue
            direct, managed = _dependencies(source, dependencies[1])
            roots = [requirement for _, requirement in direct]
            pins = [requirement for _, requirement in managed]
            resolved = (
                _resolve(compiler, roots, config.parent, checkout, constraints=pins)
                if roots or checkout is not None
                else []
            )
            if _pins(resolved) != _pins([*filter(_exact_pin, roots), *pins]):
                msg = f"hook dependency pins do not match the resolved closure: {hook_id}"
                raise ValueError(msg)


def _python_hooks(source: str, temporary: Path, cwd: Path, exclude_newer: str, python_version: str) -> list[_Hook]:
    root = _config_root(source)
    _reject_interpreter_env(_value(root, "default_env"), "default_env")
    defaults = _value(root, "default_language_version")
    default_version = _python_version(
        _value(defaults, "python") if isinstance(defaults, MappingNode) else None, python_version, python_version
    )
    if not isinstance(repositories := _value(root, "repos"), SequenceNode):
        msg = "pre-commit configuration must list repos"
        raise TypeError(msg)
    hooks: list[_Hook] = []
    for index, repository in enumerate(repositories.value):
        if not isinstance(repository, MappingNode) or not isinstance(
            entries := _value(repository, "hooks"), SequenceNode
        ):
            msg = "hook repository must be a mapping with a list of hooks"
            raise TypeError(msg)
        checkout = _checkout(repository, temporary / str(index), cwd)
        manifest = (
            {
                entry["id"]: entry
                for entry in safe_load((checkout / ".pre-commit-hooks.yaml").read_text(encoding="utf-8"))
            }
            if checkout is not None
            else {}
        )
        for hook in entries.value:
            if not isinstance(hook, MappingNode) or not isinstance(identifier := _value(hook, "id"), ScalarNode):
                msg = "hook must be a mapping with an id"
                raise TypeError(msg)
            _reject_interpreter_env(_value(hook, "env"), f"hook {identifier.value} env")
            entry = manifest.get(identifier.value, {})
            language = configured.value if isinstance(configured := _value(hook, "language"), ScalarNode) else None
            found = next(
                (
                    cast("tuple[ScalarNode, Node]", pair)
                    for pair in hook.value
                    if pair[0].value == "additional_dependencies"
                ),
                None,
            )
            if (language or entry.get("language")) != "python":
                if found is not None:
                    msg = f"additional_dependencies are only supported for Python hooks: {identifier.value}"
                    raise ValueError(msg)
                continue
            version = _python_version(
                _value(hook, "language_version") or entry.get("language_version"), default_version, python_version
            )
            compiler = ["uv", "pip", "compile", "-", "--universal", "--quiet", "--no-header", "--no-annotate"]
            compiler += ["--no-config", "--no-sources", "--exclude-newer", exclude_newer, "--python-version", version]
            dependencies = entry.get("additional_dependencies", [])
            if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
                msg = f"hook manifest additional_dependencies must be requirement strings: {identifier.value}"
                raise TypeError(msg)
            hooks.append((hook, found, checkout, compiler, [_requirement(item) for item in dependencies]))
    return hooks


def _config_root(source: str) -> MappingNode:
    try:
        root = compose(source)
    except YAMLError as error:
        msg = f"invalid pre-commit YAML: {error}"
        raise ValueError(msg) from error
    if not isinstance(root, MappingNode):
        msg = "pre-commit configuration must be a YAML mapping"
        raise TypeError(msg)
    # Aliases, merge keys, and duplicate keys can hide what a hook installs from the edits made here.
    seen: set[int] = set()
    pending: list[Node] = [root]
    while pending:
        if id(node := pending.pop()) in seen:
            msg = "YAML aliases are not supported in pre-commit configuration"
            raise ValueError(msg)
        seen.add(id(node))
        if isinstance(node, SequenceNode):
            pending.extend(node.value)
        elif isinstance(node, MappingNode):
            keys = [key.value if isinstance(key, ScalarNode) else None for key, _ in node.value]
            if None in keys or "<<" in keys or len(set(keys)) != len(keys):
                msg = "pre-commit configuration keys must be unique scalars without merge keys"
                raise ValueError(msg)
            pending.extend(value for _, value in node.value)
    return root


def _reject_interpreter_env(env: Node | None, where: str) -> None:
    # These variables redirect where uv and pip install from, or what Python imports, around the cooled pins.
    if isinstance(env, MappingNode) and (
        names := sorted(name.value for name, _ in env.value if name.value.upper().startswith(("UV_", "PIP_", "PYTHON")))
    ):
        msg = f"{where} must not set {', '.join(names)}"
        raise ValueError(msg)


def _python_version(value: Node | str | None, default: str, system: str) -> str:
    text = cast("str", value.value) if isinstance(value, ScalarNode) else value
    if not isinstance(text, str) or text == "default":
        return default
    if text == "python3":
        return system
    # Markers do not distinguish free-threaded builds, so python3.14t resolves like python3.14.
    version = text.removeprefix("python").removesuffix("t")
    if version == text or not version.startswith("3."):
        msg = f"unsupported Python hook language_version: {text}"
        raise ValueError(msg)
    return version


def _checkout(repository: MappingNode, checkout: Path, cwd: Path) -> Path | None:
    url = cast("ScalarNode", _value(repository, "repo")).value
    if url in {"local", "meta"}:
        return None
    if not isinstance(revision := _value(repository, "rev"), ScalarNode) or not re.fullmatch(
        r"[0-9a-f]{40}", revision.value
    ):
        msg = f"hook repository {url} must use a frozen commit"
        raise ValueError(msg)
    for command in (
        ["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", "--", url, str(checkout)],
        ["git", "-C", str(checkout), "checkout", "--quiet", revision.value],
    ):
        if (result := run_text(command, cwd=cwd)).returncode:
            msg = f"cannot read hook repository {url}@{revision.value}: {result.stderr.strip()}"
            raise ValueError(msg)
    return checkout


def _value(node: Node, name: str) -> Node | None:
    return cast(
        "Node | None", next((value for key, value in cast("MappingNode", node).value if key.value == name), None)
    )


def _dependencies(
    source: str, value: Node
) -> tuple[list[tuple[ScalarNode, Requirement]], list[tuple[ScalarNode, Requirement]]]:
    if not isinstance(value, SequenceNode) or not all(isinstance(item, ScalarNode) for item in value.value):
        msg = "additional_dependencies must be a list of package strings"
        raise TypeError(msg)
    direct: list[tuple[ScalarNode, Requirement]] = []
    managed: list[tuple[ScalarNode, Requirement]] = []
    for item in value.value:
        before, marker, comment = source[_end(item) :].partition("\n")[0].partition("#")
        if marker and comment.startswith(" release-creator managed") and not before.strip(" ,"):
            managed.append((item, _requirement(item.value, managed=True)))
        else:
            direct.append((item, _requirement(item.value)))
    return direct, managed


def _requirement(text: str, *, managed: bool = False) -> Requirement:
    # uv reads an option, a URL, or a path here as an install source that bypasses the index cooldown.
    if (
        text.lstrip().startswith(("-", ".", "~"))
        or any(part in text for part in ("@", "://", "file:", "/", "\\"))
        or re.search(r"\.(whl|zip|tar|tar\.gz|tgz|tar\.bz2|tbz2?|tar\.xz|txz)\s*$", text, re.IGNORECASE)
    ):
        msg = f"hook dependency must be a package requirement, not an option, URL, or path: {text!r}"
        raise ValueError(msg)
    try:
        requirement = Requirement(text)
    except InvalidRequirement as error:
        msg = f"invalid hook dependency {text!r}"
        raise ValueError(msg) from error
    # uv ignores extras in --constraint, so an extra's dependencies would install unpinned.
    if managed and (not _exact_pin(requirement) or requirement.extras or "extra" in str(requirement.marker)):
        msg = f"managed hook dependency must be an exact pin without extras: {text!r}"
        raise ValueError(msg)
    if not managed and requirement.marker is not None:
        msg = f"hook dependency markers are not supported: {text!r}"
        raise ValueError(msg)
    return requirement


def _end(node: Node) -> int:
    return int(cast("Mark", node.end_mark).index)


def _resolve(
    compiler: list[str],
    roots: list[Requirement],
    cwd: Path,
    checkout: Path | None,
    *,
    constraints: list[Requirement] | None = None,
) -> list[Requirement]:
    editable = f"-e {checkout.as_uri()}\n" if checkout is not None else ""
    # An update relaxes exact roots so they can move; a check resolves them as written.
    lines = "".join(f"{root if constraints is not None else _relaxed(root)}\n" for root in roots)
    command = list(compiler)
    with TemporaryDirectory() as temporary:
        if constraints is not None and len(constraints) > 0:
            (constraint_file := Path(temporary) / "constraints.txt").write_text(
                "".join(f"{pin}\n" for pin in constraints), encoding="utf-8"
            )
            command += ["--constraint", str(constraint_file)]
        result = run_text(command, stdin=f"{editable}{lines}", cwd=cwd, env=isolated_uv_env())
    if result.returncode:
        msg = f"cannot resolve hook dependencies: {result.stderr.strip()}"
        raise ValueError(msg)
    resolved = [Requirement(line) for line in result.stdout.splitlines() if line.strip() and not line.startswith("-e ")]
    if unpinned := [
        str(requirement) for requirement in resolved if requirement.url is not None or not _exact_pin(requirement)
    ]:
        msg = f"hook dependency resolution did not return exact index pins: {', '.join(unpinned)}"
        raise ValueError(msg)
    return resolved


def _relaxed(requirement: Requirement) -> str:
    extras = f"[{','.join(sorted(requirement.extras))}]" if requirement.extras else ""
    return f"{requirement.name}{extras}{'' if _exact_pin(requirement) else requirement.specifier}"


def _exact_pin(requirement: Requirement) -> bool:
    return (
        len(requirement.specifier) == 1
        and (specifier := next(iter(requirement.specifier))).operator == "=="
        and "*" not in specifier.version
    )


def _pins(requirements: list[Requirement]) -> dict[_PinKey, str]:
    pins: dict[_PinKey, str] = {}
    for requirement in requirements:
        key = canonicalize_name(requirement.name), str(requirement.marker or "")
        if pins.setdefault(key, version := next(iter(requirement.specifier)).version) != version:
            msg = f"conflicting hook dependency pins for {key[0]}"
            raise ValueError(msg)
    return pins


def _new_list(source: str, hook: MappingNode, defaults: list[Requirement], resolved: list[Requirement]) -> _Edit:
    if hook.flow_style:
        msg = f"cannot add managed dependencies to a flow-style hook: {cast('ScalarNode', _value(hook, 'id')).value}"
        raise ValueError(msg)
    end = source.find("\n", _content_end(hook.value[-1][1]))
    position = end + 1 if end >= 0 else len(source)
    indent = " " * cast("Mark", hook.value[0][0].start_mark).column
    versions = _pins(resolved)
    lines = [
        f"{indent}  - {json.dumps(_repinned(str(requirement), requirement, versions))}\n" for requirement in defaults
    ]
    lines += [
        f"{indent}  - {json.dumps(str(item))} # release-creator managed\n" for item in _transitive(defaults, resolved)
    ]
    return position, position, f"{'' if end >= 0 else '\n'}{indent}additional_dependencies:\n{''.join(lines)}"


def _list_edits(source: str, key: ScalarNode, value: Node, resolved: list[Requirement]) -> list[_Edit]:
    direct, managed = _dependencies(source, value)
    sequence = cast("SequenceNode", value)
    roots = [requirement for _, requirement in direct]
    if missing := sorted(
        {canonicalize_name(root.name) for root in roots}
        - {canonicalize_name(item.name) for item in resolved if item.marker is None}
    ):
        msg = f"hook dependency resolution omitted direct packages: {', '.join(missing)}"
        raise ValueError(msg)
    transitive = _transitive(roots, resolved)
    if sequence.flow_style and (managed or transitive):
        line = cast("Mark", key.start_mark).line + 1
        msg = f"write additional_dependencies on line {line} as a block list to hold managed pins"
        raise ValueError(msg)
    versions = _pins(resolved)
    edits: list[_Edit] = []
    for node, requirement in direct:
        if (updated := _repinned(scalar := source[_start(node) : _end(node)], requirement, versions)) != scalar:
            edits.append((_start(node), _end(node), updated))
    if not direct and not transitive and managed:
        end = source.find("\n", _content_end(sequence.value[-1]))
        return [(_start(key), end + 1 if end >= 0 else len(source), f"{key.value}: []\n")]
    for node, _ in managed:
        end = source.find("\n", _end(node))
        edits.append((source.rfind("\n", 0, _start(node)) + 1, end + 1 if end >= 0 else len(source), ""))
    if transitive:
        first = _start(sequence.value[0])
        indent = source[source.rfind("\n", 0, first) + 1 : first].partition("-")[0]
        end = source.find("\n", _content_end(sequence.value[-1]))
        lines = "".join(f"{indent}- {json.dumps(str(item))} # release-creator managed\n" for item in transitive)
        edits.append((end + 1, end + 1, lines) if end >= 0 else (len(source), len(source), f"\n{lines}"))
    return edits


def _transitive(roots: list[Requirement], resolved: list[Requirement]) -> list[Requirement]:
    # A root given as a range keeps its range and also gets the resolved exact pin.
    pinned = {canonicalize_name(root.name) for root in roots if _exact_pin(root)}
    return [item for item in resolved if canonicalize_name(item.name) not in pinned]


def _repinned(scalar: str, requirement: Requirement, versions: dict[_PinKey, str]) -> str:
    if not _exact_pin(requirement):
        return scalar
    old = next(iter(requirement.specifier)).version
    before, _, after = scalar.partition("==")
    spacing = after[: len(after) - len(after.lstrip())]
    return f"{before}=={spacing}{versions[canonicalize_name(requirement.name), '']}{after[len(spacing) + len(old) :]}"


def _start(node: Node) -> int:
    return int(cast("Mark", node.start_mark).index)


def _content_end(node: Node) -> int:
    if isinstance(node, MappingNode) and not node.flow_style:
        return _content_end(node.value[-1][1])
    if isinstance(node, SequenceNode) and not node.flow_style:
        return _content_end(node.value[-1])
    # A block scalar's end mark is past its final newline.
    return _end(node) - 1 if isinstance(node, ScalarNode) and node.style in {"|", ">"} else _end(node)


__all__ = [
    "check_pins",
    "update_pins",
]
