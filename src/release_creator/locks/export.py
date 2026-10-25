"""Preserve uv's resolved selections in a PEP 751 export."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # Dataclass decorators resolve when the lock models are defined.
lazy import json
lazy import os
lazy import shutil
lazy import tomllib
lazy from collections import defaultdict
lazy from dataclasses import dataclass
lazy from datetime import UTC, date, datetime, time, timedelta
lazy from pathlib import Path
lazy from tempfile import TemporaryDirectory
lazy from typing import cast
lazy from urllib.parse import urlsplit

lazy import tomli_w
lazy from packaging.requirements import InvalidRequirement, Requirement
lazy from packaging.specifiers import SpecifierSet
lazy from packaging.utils import canonicalize_name
lazy from packaging.version import Version

lazy from release_creator.process import run_text

type _TomlValue = (
    str | int | float | bool | datetime | date | time | list[str] | list[_TomlTable] | list[_TomlValue] | _TomlTable
)
type _TomlTable = dict[str, _TomlValue]


def export_lock(root: Path, *, check: bool = False, keep_uv_lock: bool = False) -> None:
    """Export each resolved group and extra of ``root/pyproject.toml`` to ``root/pylock.toml``.

    :param root: Project directory.
    :param check: Compare the committed lock instead of writing it.
    :param keep_uv_lock: Refresh and keep the project's native ``uv.lock`` too.
    :raises ValueError: The project cannot describe a selectable lock.
    :raises FileNotFoundError: uv is not installed.
    """
    project = root / "pyproject.toml"
    output = root / "pylock.toml"
    lock_path = root / "uv.lock"
    previous = (
        lock_path.read_bytes() if lock_path.exists() else None,
        output.read_bytes() if output.exists() else None,
    )
    if (uv := shutil.which("uv")) is None:
        msg = "uv is required to export a project lock"
        raise FileNotFoundError(msg)
    created_at = _creation_time(output) if check else datetime.now(tz=UTC)
    completed = False
    try:
        rendered = _render_lock(project, uv, created_at, check=check, keep_uv_lock=keep_uv_lock)
        if check:
            if output.read_text(encoding="utf-8") != rendered:
                msg = f"project lock is stale: {output}"
                raise ValueError(msg)
        else:
            output.write_text(rendered, encoding="utf-8")
        completed = True
    finally:
        _restore_exports(
            lock_path,
            output,
            previous,
            completed=completed and not check,
            keep_uv_lock=keep_uv_lock and not check,
        )


@dataclass(frozen=True, kw_only=True)
class _Compiler:
    uv: str
    directory: Path
    options: list[str]


def _render_lock(project: Path, uv: str, created_at: datetime, *, check: bool, keep_uv_lock: bool) -> str:
    requires_python, groups, extras, projects = _project_selections(project)
    if "project-runtime" in groups:
        msg = "project-runtime is reserved for the project's runtime dependencies"
        raise ValueError(msg)
    build = [
        requirement
        for _, item in projects
        for requirement in cast("list[str]", _table(item, "build-system").get("requires", []))
    ]
    for requirement in build:
        _require_pypi(requirement)
    cutoffs = _package_cutoffs(projects[0][1])
    cutoff_options = [
        "--exclude-newer",
        (created_at - timedelta(days=7)).isoformat(),
        "--no-cache",
        "--no-config",
        "--no-sources",
        "--default-index",
        "https://pypi.org/simple/",
    ]
    cutoff_options.extend(
        option for name, date in cutoffs.items() for option in ("--exclude-newer-package", f"{name}={date}")
    )
    compiler = _Compiler(
        uv=uv,
        directory=project.parent,
        options=[
            "--universal",
            "--python-version",
            _minimum_python(requires_python),
            "--format",
            "pylock.toml",
            *cutoff_options,
        ],
    )
    if keep_uv_lock:
        if check:
            _run_uv(uv, project.parent, "lock", "--check", "--no-config")
        else:
            _run_uv(
                uv,
                project.parent,
                "lock",
                "--upgrade",
                *(option for option in cutoff_options if option != "--no-sources"),
            )
            _run_uv(uv, project.parent, "lock", "--no-config")
    packages: dict[str, _TomlTable] = {}
    markers: dict[str, set[str]] = defaultdict(set)
    runtime = [
        requirement
        for _, item in projects
        for requirement in cast("list[str]", _table(item, "project").get("dependencies", []))
    ]
    _add_selection(
        packages,
        markers,
        _compile_selection(compiler, requirements=runtime),
        "project-runtime",
        "dependency_groups",
    )
    for group in groups:
        sources = [f"{path}:{group}" for path, item in projects if group in _table(item, "dependency-groups")]
        _add_selection(
            packages,
            markers,
            _compile_selection(compiler, groups=sources, requirements=build if group == "build" else None),
            group,
            "dependency_groups",
        )
    for extra in extras:
        extra_requirements = [
            requirement
            for _, item in projects
            for requirement in cast(
                "list[str]", _table(_table(item, "project"), "optional-dependencies").get(extra, [])
            )
        ]
        _add_selection(
            packages,
            markers,
            _compile_extra(compiler, runtime, extra, extra_requirements, requires_python),
            extra,
            "extras",
        )
    if build and "build" not in groups:
        _add_selection(
            packages,
            markers,
            _compile_selection(compiler, requirements=build),
            "build",
            "dependency_groups",
        )
    records = _package_records(packages, markers)
    for package in records:
        _check_package_artifacts(package, created_at, cutoffs)
    if keep_uv_lock:
        _check_native_lock(project.parent / "uv.lock", created_at, cutoffs, projects, records)
    return tomli_w.dumps({
        "lock-version": "1.0",
        "created-by": "release-creator (uv)",
        "requires-python": requires_python,
        "extras": extras,
        "dependency-groups": ["project-runtime", *groups, *(["build"] if build and "build" not in groups else [])],
        "default-groups": [],
        "packages": records,
        "tool": {"release-creator": {"created-at": created_at}, "nab": {"created-at": created_at}},
    })


def _restore_exports(
    lock_path: Path,
    output: Path,
    previous: tuple[bytes | None, bytes | None],
    *,
    completed: bool,
    keep_uv_lock: bool,
) -> None:
    previous_lock, previous_output = previous
    if not keep_uv_lock or not completed:
        if previous_lock is None:
            lock_path.unlink(missing_ok=True)
        elif not lock_path.exists() or lock_path.read_bytes() != previous_lock:
            lock_path.write_bytes(previous_lock)
    if not completed:
        if previous_output is None:
            output.unlink(missing_ok=True)
        elif not output.exists() or output.read_bytes() != previous_output:
            output.write_bytes(previous_output)


def _creation_time(output: Path) -> datetime:
    with output.open("rb") as stream:
        created = tomllib.load(stream).get("tool", {}).get("release-creator", {}).get("created-at")
    if not isinstance(created, datetime) or created.tzinfo is None or created > datetime.now(tz=UTC):
        msg = f"project lock has no valid creation time: {output}"
        raise ValueError(msg)
    return created


def _package_cutoffs(data: _TomlTable) -> dict[str, str]:
    configured = _table(_table(_table(data, "tool"), "release-creator"), "locks").get("exclude-newer-package", {})
    if not isinstance(configured, dict) or any(not isinstance(date, str) for date in configured.values()):
        msg = "tool.release-creator.locks.exclude-newer-package must map package names to UTC dates"
        raise TypeError(msg)
    return {name: cast("str", date) for name, date in configured.items()}


def _package_records(packages: dict[str, _TomlTable], markers: dict[str, set[str]]) -> list[_TomlTable]:
    records: list[_TomlTable] = []
    for key, package in sorted(
        packages.items(), key=lambda entry: (entry[1]["name"], entry[1].get("version", ""), entry[0])
    ):
        package["marker"] = " or ".join(sorted(markers[key]))
        records.append(package)
    return records


def _check_package_artifacts(package: _TomlTable, created_at: datetime, cutoffs: dict[str, str]) -> None:
    if any(key in package for key in ("archive", "directory", "vcs")):
        msg = f"lock has a non-PyPI package source: {package['name']}"
        raise ValueError(msg)
    artifacts = [*cast("list[_TomlTable]", package.get("wheels", []))]
    if (sdist := package.get("sdist")) is not None:
        artifacts.append(cast("_TomlTable", sdist))
    if not artifacts:
        msg = f"lock has no dated artifacts: {package['name']}"
        raise ValueError(msg)
    cutoff = _artifact_cutoff(cast("str", package["name"]), created_at, cutoffs)
    for artifact in artifacts:
        _check_artifact(artifact, cutoff, cast("str", package["name"]))
    if package.get("index") not in {None, "https://pypi.org/simple", "https://pypi.org/simple/"}:
        msg = f"lock has an unapproved index: {package['name']}: {package['index']}"
        raise ValueError(msg)
    package["index"] = "https://pypi.org/simple/"


def _check_artifact(artifact: _TomlTable, cutoff: datetime, package_name: str) -> None:
    url = urlsplit(cast("str", artifact.get("url", "")))
    if url.scheme != "https" or url.hostname != "files.pythonhosted.org":
        msg = f"lock has a non-PyPI artifact: {package_name}"
        raise ValueError(msg)
    filename = url.path.rsplit("/", 1)[-1]
    if not isinstance(uploaded := artifact.get("upload-time"), datetime) or uploaded.tzinfo is None:
        msg = f"lock has no upload time for {filename}"
        raise ValueError(msg)
    if uploaded > cutoff:
        msg = f"lock has an uncooled artifact: {filename}"
        raise ValueError(msg)
    if _table(artifact, "hashes").get("sha256") in {None, ""}:
        msg = f"lock has no SHA-256 for {filename}"
        raise ValueError(msg)


def _check_native_lock(
    lock_path: Path,
    created_at: datetime,
    cutoffs: dict[str, str],
    projects: list[tuple[Path, _TomlTable]],
    records: list[_TomlTable],
) -> None:
    trusted = {
        (
            canonicalize_name(cast("str", package["name"])),
            cast("str", package["version"]),
            cast("str", artifact["url"]),
            cast("str", _table(artifact, "hashes")["sha256"]),
        ): artifact["upload-time"]
        for package in records
        for artifact in [
            *cast("list[_TomlTable]", package.get("wheels", [])),
            *([cast("_TomlTable", package["sdist"])] if "sdist" in package else []),
        ]
    }
    members = {
        canonicalize_name(cast("str", _table(item, "project")["name"])): (
            path.parent.relative_to(lock_path.parent).as_posix()
        )
        for path, item in projects
        if "name" in _table(item, "project")
    }
    for package in cast("list[_TomlTable]", tomllib.loads(lock_path.read_text(encoding="utf-8"))["package"]):
        name = cast("str", package["name"])
        source = _table(package, "source")
        if source in ({"registry": "https://pypi.org/simple"}, {"registry": "https://pypi.org/simple/"}):
            cutoff = _artifact_cutoff(name, created_at, cutoffs)
            artifacts = [*cast("list[_TomlTable]", package.get("wheels", []))]
            if (sdist := package.get("sdist")) is not None:
                artifacts.append(cast("_TomlTable", sdist))
            if not artifacts:
                msg = f"native lock has no dated artifacts: {name}"
                raise ValueError(msg)
            for artifact in artifacts:
                _check_native_artifact(artifact, cutoff, name)
                key = (
                    canonicalize_name(name),
                    cast("str", package["version"]),
                    cast("str", artifact["url"]),
                    cast("str", artifact["hash"])[7:],
                )
                if (trusted_at := trusted.get(key)) is None or abs(
                    cast("datetime", trusted_at) - datetime.fromisoformat(cast("str", artifact["upload-time"]))
                ) >= timedelta(seconds=1):
                    msg = f"native lock artifact differs from cooled project lock: {name}"
                    raise ValueError(msg)
        elif canonicalize_name(name) not in members or source not in (
            {"editable": members.get(canonicalize_name(name))},
            {"virtual": members.get(canonicalize_name(name))},
        ):
            msg = f"native lock has a non-PyPI package source: {name}"
            raise ValueError(msg)


def _artifact_cutoff(name: str, created_at: datetime, cutoffs: dict[str, str]) -> datetime:
    cutoff = created_at - timedelta(days=7)
    if (reviewed := cutoffs.get(canonicalize_name(name))) is not None:
        if (reviewed_at := datetime.fromisoformat(reviewed)).tzinfo is None or reviewed_at > created_at:
            msg = f"invalid reviewed cutoff for {name}: {reviewed}"
            raise ValueError(msg)
        cutoff = max(cutoff, reviewed_at)
    return cutoff


def _check_native_artifact(artifact: _TomlTable, cutoff: datetime, package_name: str) -> None:
    url = urlsplit(cast("str", artifact.get("url", "")))
    if url.scheme != "https" or url.hostname != "files.pythonhosted.org":
        msg = f"native lock has a non-PyPI artifact: {package_name}"
        raise ValueError(msg)
    filename = url.path.rsplit("/", 1)[-1]
    if not isinstance(uploaded := artifact.get("upload-time"), str):
        msg = f"native lock has no upload time for {filename}"
        raise TypeError(msg)
    try:
        uploaded_at = datetime.fromisoformat(uploaded)
    except ValueError as error:
        msg = f"native lock has an invalid upload time for {filename}"
        raise ValueError(msg) from error
    if uploaded_at.tzinfo is None or uploaded_at > cutoff:
        msg = f"native lock has an uncooled artifact: {filename}"
        raise ValueError(msg)
    if (
        not isinstance(digest := artifact.get("hash"), str)
        or len(digest) != len("sha256:") + 64
        or not digest.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in digest[7:].lower())
    ):
        msg = f"native lock has no SHA-256 for {filename}"
        raise ValueError(msg)


def _add_selection(
    packages: dict[str, _TomlTable],
    markers: dict[str, set[str]],
    selected: list[_TomlTable],
    name: str,
    kind: str,
) -> None:
    for package in selected:
        if package.get("index") == "https://pypi.org/simple":
            package["index"] = "https://pypi.org/simple/"
        environment = package.pop("marker", None)
        key = json.dumps(
            {
                field: value
                for field, value in package.items()
                if field != "index" or value != "https://pypi.org/simple/"
            },
            sort_keys=True,
            default=str,
        )
        packages.setdefault(key, package)
        selection = f"{json.dumps(name)} in {kind}"
        markers[key].add(f"({selection} and ({environment}))" if environment is not None else selection)


def _compile_selection(
    compiler: _Compiler,
    *,
    requirements: list[str] | None = None,
    groups: list[str] | None = None,
) -> list[_TomlTable]:
    compiled = _run_uv(
        compiler.uv,
        compiler.directory,
        "pip",
        "compile",
        *(["-"] if requirements is not None else []),
        *(option for group in groups or [] for option in ("--group", group)),
        *compiler.options,
        stdin=f"{'\n'.join(requirements)}\n" if requirements is not None else None,
    )
    return cast("list[_TomlTable]", tomllib.loads(compiled)["packages"])


def _compile_extra(
    compiler: _Compiler, runtime: list[str], extra: str, requirements: list[str], requires_python: str
) -> list[_TomlTable]:
    with TemporaryDirectory() as temporary:
        source = Path(temporary) / "pyproject.toml"
        source.write_text(
            tomli_w.dumps({
                "project": {
                    "name": "release-creator-lock-selection",
                    "version": "0",
                    "requires-python": requires_python,
                    "dependencies": runtime,
                    "optional-dependencies": {extra: requirements},
                }
            }),
            encoding="utf-8",
        )
        compiled = _run_uv(
            compiler.uv, compiler.directory, "pip", "compile", str(source), "--extra", extra, *compiler.options
        )
    return cast("list[_TomlTable]", tomllib.loads(compiled)["packages"])


def _minimum_python(requires_python: str) -> str:
    specifiers = SpecifierSet(requires_python)
    lower_bounds = [Version(spec.version) for spec in specifiers if spec.operator in {">=", "~="}]
    if not lower_bounds or (minimum := max(lower_bounds)) not in specifiers:
        msg = f"cannot infer the minimum Python version from {requires_python!r}"
        raise ValueError(msg)
    return str(minimum)


def _project_selections(project: Path) -> tuple[str, list[str], list[str], list[tuple[Path, _TomlTable]]]:
    data = cast("_TomlTable", tomllib.loads(project.read_text(encoding="utf-8")))
    workspace = _table(_table(_table(data, "tool"), "uv"), "workspace")
    excluded = {path.resolve() for path in _workspace_paths(project.parent, workspace.get("exclude", []))}
    projects = [(project, data)]
    projects.extend(
        (
            member / "pyproject.toml",
            cast("_TomlTable", tomllib.loads((member / "pyproject.toml").read_text(encoding="utf-8"))),
        )
        for member in dict.fromkeys(
            path
            for path in _workspace_paths(project.parent, workspace.get("members", []))
            if path.is_dir() and path.resolve() not in excluded
        )
    )
    _validate_sources([item for _, item in projects])
    project_tables = [_table(item, "project") for _, item in projects]
    for item in project_tables:
        if set(cast("list[str]", item.get("dynamic", []))) & {"dependencies", "optional-dependencies"}:
            msg = "dynamic project dependencies cannot be exported without built metadata"
            raise ValueError(msg)
    ranges = {cast("str", item["requires-python"]) for item in project_tables if "requires-python" in item}
    if len(ranges) > 1:
        msg = "workspace members must share a requires-python range"
        raise ValueError(msg)
    if (requires_python := next(iter(ranges), None)) is None:
        msg = "declare [project].requires-python in the project or its workspace members"
        raise ValueError(msg)
    groups = list(dict.fromkeys(group for _, item in projects for group in _table(item, "dependency-groups")))
    extras = list(dict.fromkeys(extra for item in project_tables for extra in _table(item, "optional-dependencies")))
    return (
        requires_python,
        groups,
        extras,
        projects,
    )


def _workspace_paths(directory: Path, patterns: _TomlValue) -> list[Path]:
    paths: list[Path] = []
    for pattern in cast("list[str]", patterns):
        for path in sorted(directory.glob(pattern)):
            if not path.resolve().is_relative_to(directory.resolve()):
                msg = f"workspace path is outside the project: {path}"
                raise ValueError(msg)
            paths.append(path)
    return paths


def _validate_sources(projects: list[_TomlTable]) -> None:
    members = {
        canonicalize_name(cast("str", _table(item, "project")["name"]))
        for item in projects
        if "name" in _table(item, "project")
    }
    for item in projects:
        uv_config = _table(_table(item, "tool"), "uv")
        if "dev-dependencies" in uv_config:
            msg = "legacy tool.uv.dev-dependencies cannot be exported; use dependency-groups.dev"
            raise ValueError(msg)
        if any(key in uv_config for key in ("index", "default-index", "extra-index-url")) or any(
            canonicalize_name(name) not in members or source != {"workspace": True}
            for name, source in _table(uv_config, "sources").items()
        ):
            msg = "project dependency sources must be PyPI or declared workspace members"
            raise ValueError(msg)
        for requirement in cast("list[str]", _table(item, "project").get("dependencies", [])):
            _require_pypi(requirement)
        for dependencies in _table(_table(item, "project"), "optional-dependencies").values():
            for requirement in cast("list[str]", dependencies):
                _require_pypi(requirement)
        for dependencies in _table(item, "dependency-groups").values():
            for requirement in cast("list[_TomlValue]", dependencies):
                if isinstance(requirement, str):
                    _require_pypi(requirement)


def _table(table: _TomlTable, key: str) -> _TomlTable:
    return cast("_TomlTable", table.get(key, {}))


def _require_pypi(text: str) -> None:
    try:
        requirement = Requirement(text)
    except InvalidRequirement as error:
        msg = f"invalid requirement: {text}"
        raise ValueError(msg) from error
    if requirement.url is not None:
        msg = f"direct dependency source is not supported: {requirement.name}"
        raise ValueError(msg)


def _run_uv(uv: str, directory: Path, *arguments: str, stdin: str | None = None) -> str:
    with TemporaryDirectory() as uv_environment:
        result = run_text(
            [uv, *arguments],
            cwd=directory,
            stdin=stdin,
            env={
                **{
                    name: value
                    for name, value in os.environ.items()
                    if not name.startswith(("UV_", "PIP_"))
                    and name
                    not in {
                        "SSL_CERT_FILE",
                        "SSL_CERT_DIR",
                        "SSL_CLIENT_CERT",
                        "REQUESTS_CA_BUNDLE",
                        "CURL_CA_BUNDLE",
                    }
                },
                "UV_PROJECT_ENVIRONMENT": uv_environment,
            },
        )
    if result.returncode:
        msg = result.stderr.strip() or f"uv {arguments[0]} failed"
        raise ValueError(msg)
    return result.stdout


__all__ = [
    "export_lock",
]
