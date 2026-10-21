"""Select build artifacts whose lock markers match this runner."""

lazy import tomllib
lazy from pathlib import Path
lazy from typing import Any, Final, Literal

lazy from packaging.markers import InvalidMarker, Marker, default_environment
lazy from packaging.specifiers import SpecifierSet
lazy from packaging.utils import canonicalize_name
lazy from packaging.version import InvalidVersion, Version

_SHA256_LENGTH: Final = 64


def write_build_constraints(
    lock: Path,
    output: Path,
    group: str = "build",
    python_versions: tuple[str, ...] = (),
    platform: Literal["linux", "macos", "windows"] | None = None,
) -> None:
    """Write exact build pins with all available artifact hashes.

    Raises:
        ValueError: The lock cannot provide a complete build selection.

    """
    data = tomllib.loads(lock.read_text(encoding="utf-8"))
    if missing := next((key for key in ("dependency-groups", "requires-python", "packages") if key not in data), None):
        msg = f"invalid lock: missing {missing}"
        raise ValueError(msg)
    if group not in data["dependency-groups"]:
        msg = f"build group {group!r} is absent from {lock}"
        raise ValueError(msg)
    versions = python_versions or (None,)
    selected = _select(data, group, versions[0], platform)
    for version in versions[1:]:
        if _select(data, group, version, platform) != selected:
            msg = f"build selection differs across target Python versions in {lock}"
            raise ValueError(msg)
    output.write_text(
        "".join(
            f"{name}=={version} " + " ".join(f"--hash=sha256:{digest}" for digest in sorted(hashes)) + "\n"
            for name, (version, hashes) in sorted(selected.items())
        ),
        encoding="utf-8",
    )


def _select(
    data: dict[str, Any],
    group: str,
    python_version: str | None,
    platform: Literal["linux", "macos", "windows"] | None,
) -> dict[str, tuple[str, set[str]]]:
    environment = _target_environment(python_version, platform)
    if environment["python_full_version"] not in SpecifierSet(data["requires-python"]):
        msg = "target Python is outside the lock's requires-python range"
        raise ValueError(msg)
    selected: dict[str, tuple[str, set[str]]] = {}
    for package in data["packages"]:
        if not _matches(
            package.get("marker"), group, environment, override=python_version is not None or platform is not None
        ):
            continue
        name = canonicalize_name(package["name"], validate=True)
        version = str(Version(package["version"]))
        hashes = _hashes(package)
        if name in selected:
            current_version, current_hashes = selected[name]
            if current_version != version:
                msg = f"conflicting build pins for {name}: {current_version} and {version}"
                raise ValueError(msg)
            current_hashes.update(hashes)
        else:
            selected[name] = (version, hashes)
    if not selected:
        msg = f"build group {group!r} selects no packages"
        raise ValueError(msg)
    return selected


def _target_environment(
    python_version: str | None, platform: Literal["linux", "macos", "windows"] | None
) -> dict[str, str]:
    environment = {key: str(value) for key, value in default_environment().items()}
    if python_version is not None:
        try:
            version = Version(python_version)
        except InvalidVersion as error:
            msg = f"invalid target Python version: {python_version}"
            raise ValueError(msg) from error
        if (
            len(version.release) not in {2, 3}
            or version.is_prerelease
            or version.is_postrelease
            or version.local is not None
            or version.epoch
        ):
            msg = f"invalid target Python version: {python_version}"
            raise ValueError(msg)
        major, minor, *patch = version.release
        environment.update({
            "python_version": f"{major}.{minor}",
            "python_full_version": f"{major}.{minor}.{patch[0] if patch else 0}",
        })
    if platform is not None:
        environment.update({
            "sys_platform": {"linux": "linux", "macos": "darwin", "windows": "win32"}[platform],
            "os_name": "nt" if platform == "windows" else "posix",
            "platform_system": {"linux": "Linux", "macos": "Darwin", "windows": "Windows"}[platform],
        })
    return environment


def _matches(marker: str | None, group: str, environment: dict[str, str], *, override: bool) -> bool:
    if marker is None:
        return True
    if "dependency_groups" in marker and not any(
        selector in marker for selector in (f'"{group}" in dependency_groups', f"'{group}' in dependency_groups")
    ):
        return False
    if override and any(
        field in marker
        for field in (
            "platform_machine",
            "platform_release",
            "platform_version",
            "implementation_name",
            "implementation_version",
            "platform_python_implementation",
        )
    ):
        msg = f"target marker environment cannot evaluate {marker}"
        raise ValueError(msg)
    try:
        return Marker(marker).evaluate(
            environment={**environment, "dependency_groups": frozenset({group})}, context="lock_file"
        )
    except InvalidMarker as error:
        msg = f"invalid build package marker: {marker}"
        raise ValueError(msg) from error


def _hashes(package: dict[str, Any]) -> set[str]:
    files = [*([package["sdist"]] if "sdist" in package else []), *package.get("wheels", [])]
    if not files:
        msg = f"build package {package['name']} has no artifacts"
        raise ValueError(msg)
    hashes: set[str] = set()
    for file in files:
        digest = file.get("hashes", {}).get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != _SHA256_LENGTH
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            msg = f"build package {package['name']} has an artifact without a SHA256 hash"
            raise ValueError(msg)
        hashes.add(digest)
    return hashes


__all__ = [
    "write_build_constraints",
]
